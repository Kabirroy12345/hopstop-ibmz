r"""IBM Z / LinuxONE Hardware Probe, Snap ML Integration & Exact TreeSHAP Engine.

Key capabilities:
1. Accurate s390x Hardware & Facility Probe (`detect_ibmz_environment()`):
   - Facility 165 (`nnpa`): IBM Telum / Telum II Neural Network Processing Assist via
     `/proc/cpuinfo` and `libzdnn.so` (`zdnn_is_nnpa_installed()`).
   - Facility 17 / 76 / 77 / 146 (`msa`): Message-Security-Assist (CPACF hardware crypto).
   - Facility 158 (`prot_virt`): IBM Secure Execution for Linux (Ultravisor).
2. Real Snap ML + Portable Depth-2 Tensor-Tree GBDT (`SnapMLAcceleratedScorer`):
   - When `snapml` is installed on the host, trains a `snapml.BoostingMachineClassifier`
     and calls `optimize_trees(tree_format='auto')` to target the Telum NNPA or
     compressed CPU tensor-trees.
   - Always maintains and exports portable JSON depth-2 trees (`save_json` / `load_json`,
     replacing insecure `.pkl` files) so models can be inspected or imported across
     x86_64 and s390x hosts, and explicitly reports which backend ran (`active_backend`).
3. Exact Path-Dependent TreeSHAP for Depth-2 Trees (`explain_instance()`):
   - Computes exact Shapley values $\phi_j(x)$ across all 4 leaves of each depth-2 tree
     using empirical node cover weights recorded during training.
   - Satisfies the exact Shapley additivity identity:
     $\sum_{j=1}^{12} \phi_j(x) + \text{expected\_value} = \text{raw\_log\_odds}(x)$
     and naturally produces signed (positive and negative) feature attributions.
4. Baselines on the Same 12 Features:
   - `LogisticRegressionBaseline`: Weighted L2-regularized logistic regression trained
     on the exact same 12 causal features.
   - `VelocityRulesBaseline`: Traditional static velocity-rules baseline.
"""
from __future__ import annotations

import ctypes
import importlib.util
import json
import math
import platform
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from hopstop.feature_engine import FEATURE_NAMES, get_hmac_key_status


REASON_LABELS: Dict[str, str] = {
    "fan_in_1h": "Inbound Fan-In Burst (1h)",
    "fan_out_1h": "Outbound Fan-Out Dispersal (1h)",
    "fan_in_24h": "24h Inbound Counterparty Surge",
    "fan_out_24h": "24h Outbound Counterparty Surge",
    "pass_through_ratio_15m": "Rapid 15m Pass-Through Ratio",
    "pass_through_ratio_1h": "High 1h Pass-Through Ratio",
    "time_since_last_credit_log": "Immediate Post-Credit Dispersal",
    "rapid_turnover_flag": "Rapid Credit-to-Debit Drain",
    "counterparty_novelty": "First-Time Counterparty Transfer",
    "amount_zscore": "Anomalous Transfer Size (Z-Score)",
    "out_tx_velocity_1h": "High Outgoing Transfer Velocity (1h)",
    "payment_format_risk": "High-Risk Instant Rail (Wire/ACH)",
}


def detect_ibmz_environment() -> Dict[str, Any]:
    """Probes host architecture, s390x CPU facilities, libzdnn NNPA status, and Snap ML availability."""
    arch = platform.machine().lower()
    is_s390x = "s390x" in arch

    nnpa_installed = False
    zdnn_status = "libzdnn not loaded (non-s390x host; using portable CPU tensor-tree engine)"
    for libname in ("libzdnn.so", "libzdnn.so.0", "/usr/lib64/libzdnn.so"):
        try:
            lib = ctypes.CDLL(libname)
            fn = getattr(lib, "zdnn_is_nnpa_installed", None)
            if fn is not None:
                fn.restype = ctypes.c_bool
                nnpa_installed = bool(fn())
                zdnn_status = (
                    "Telum/Telum II NNPA active via libzdnn"
                    if nnpa_installed
                    else "libzdnn loaded; NNPA facility 165 not exposed to guest (CPU fallback)"
                )
                break
        except OSError:
            continue

    # Parse /proc/cpuinfo on Linux for s390x facility bits:
    #   - 165: NNPA (Telum Integrated Accelerator for AI)
    #   - 17, 76, 77, 146: MSA (Message-Security-Assist / CPACF hardware crypto)
    #   - 158: Secure Execution for Linux (Ultravisor / prot_virt)
    facilities: List[str] = []
    cpuinfo_path = Path("/proc/cpuinfo")
    if cpuinfo_path.exists():
        try:
            txt = cpuinfo_path.read_text(encoding="utf-8", errors="ignore")
            for line in txt.splitlines():
                if "facilities" in line.lower():
                    facilities = line.split(":", 1)[-1].strip().split()
                    break
        except OSError:
            pass

    if "165" in facilities and not nnpa_installed:
        nnpa_installed = True
        zdnn_status = "Facility 165 (NNPA) detected in /proc/cpuinfo"

    cpacf_msa_detected = any(f in facilities for f in ("17", "76", "77", "146"))
    secure_exec_detected = "158" in facilities or Path("/sys/firmware/uv").exists()

    snapml_spec = importlib.util.find_spec("snapml")
    snapml_available = snapml_spec is not None
    snapml_version: Optional[str] = None
    if snapml_available:
        try:
            import importlib.metadata

            snapml_version = importlib.metadata.version("snapml")
        except Exception:
            snapml_version = "installed"

    hmac_info = get_hmac_key_status()

    return {
        "architecture": arch or "unknown",
        "processor": platform.processor() or arch or "unknown",
        "os_platform": f"{platform.system()} {platform.release()}",
        "python_version": platform.python_version(),
        "is_s390x": is_s390x,
        "nnpa_facility_165_available": nnpa_installed,
        "zdnn_status": zdnn_status,
        "cpacf_msa_facility_detected": cpacf_msa_detected,
        "secure_execution_facility_158": secure_exec_detected,
        "snapml_installed": snapml_available,
        "snapml_version": snapml_version,
        "hmac_pseudonymization": hmac_info["mode"],
    }


@dataclass
class Depth2Tree:
    """Depth-2 regression tree with empirical node cover fractions for exact TreeSHAP."""

    root_feat: int
    root_thresh: float
    left_feat: int
    left_thresh: float
    right_feat: int
    right_thresh: float
    leaf_ll: float
    leaf_lr: float
    leaf_rl: float
    leaf_rr: float
    # Empirical routing probabilities recorded during training for exact path-dependent TreeSHAP
    w_left: float = 0.5
    w_ll_given_l: float = 0.5
    w_rl_given_r: float = 0.5

    def predict_one(self, x: List[float]) -> float:
        if x[self.root_feat] <= self.root_thresh:
            return self.leaf_ll if x[self.left_feat] <= self.left_thresh else self.leaf_lr
        else:
            return self.leaf_rl if x[self.right_feat] <= self.right_thresh else self.leaf_rr

    @property
    def expected_value(self) -> float:
        """Exact expected value E[T(X)] under empirical training node cover."""
        w_l = self.w_left
        w_r = 1.0 - w_l
        p_ll = w_l * self.w_ll_given_l
        p_lr = w_l * (1.0 - self.w_ll_given_l)
        p_rl = w_r * self.w_rl_given_r
        p_rr = w_r * (1.0 - self.w_rl_given_r)
        return p_ll * self.leaf_ll + p_lr * self.leaf_lr + p_rl * self.leaf_rl + p_rr * self.leaf_rr

    def shap_contributions(self, x: List[float], phi: List[float]) -> None:
        """Accumulates exact path-dependent TreeSHAP values for this depth-2 tree into `phi`.

        Guarantees exact additivity: sum(phi_tree) == self.predict_one(x) - self.expected_value.
        """
        w_l = self.w_left
        w_r = 1.0 - w_l
        w_ll = self.w_ll_given_l
        w_lr = 1.0 - w_ll
        w_rl = self.w_rl_given_r
        w_rr = 1.0 - w_rl

        i_root_l = 1.0 if x[self.root_feat] <= self.root_thresh else 0.0
        i_root_r = 1.0 - i_root_l
        i_left_l = 1.0 if x[self.left_feat] <= self.left_thresh else 0.0
        i_left_r = 1.0 - i_left_l
        i_right_l = 1.0 if x[self.right_feat] <= self.right_thresh else 0.0
        i_right_r = 1.0 - i_right_l

        # Helper for a single leaf path (root_feat, child_feat, leaf_val, w_root, w_child, ind_root, ind_child)
        def _accum_leaf(
            f0: int,
            f1: int,
            val: float,
            wr: float,
            wc: float,
            ir: float,
            ic: float,
        ) -> None:
            p_leaf = wr * wc
            if f0 == f1:
                phi[f0] += val * (ir * ic - p_leaf)
            else:
                phi[f0] += val * (0.5 * (ir * wc - p_leaf) + 0.5 * (ir * ic - wr * ic))
                phi[f1] += val * (0.5 * (wr * ic - p_leaf) + 0.5 * (ir * ic - ir * wc))

        _accum_leaf(self.root_feat, self.left_feat, self.leaf_ll, w_l, w_ll, i_root_l, i_left_l)
        _accum_leaf(self.root_feat, self.left_feat, self.leaf_lr, w_l, w_lr, i_root_l, i_left_r)
        _accum_leaf(self.root_feat, self.right_feat, self.leaf_rl, w_r, w_rl, i_root_r, i_right_l)
        _accum_leaf(self.root_feat, self.right_feat, self.leaf_rr, w_r, w_rr, i_root_r, i_right_r)


class SnapMLAcceleratedScorer:
    """Gradient Boosted Decision Tree scorer with real Snap ML (`tree_format='auto'`) & portable JSON fallback."""

    MODEL_VERSION = "hopstop-gbdt-v2.1"

    def __init__(self, n_trees: int = 36, learning_rate: float = 0.18) -> None:
        self.n_trees = n_trees
        self.learning_rate = learning_rate
        self.base_log_odds: float = 0.0
        self.trees: List[Depth2Tree] = []
        self.feature_means: List[float] = [0.0] * len(FEATURE_NAMES)
        self.feature_stds: List[float] = [1.0] * len(FEATURE_NAMES)
        self.feature_weights: List[float] = [0.0] * len(FEATURE_NAMES)
        self.snapml_clf: Any = None
        self.active_backend: str = "uninitialized"

    @staticmethod
    def _sigmoid(z: float) -> float:
        if z >= 0:
            ez = math.exp(-min(z, 30.0))
            return 1.0 / (1.0 + ez)
        else:
            ez = math.exp(max(z, -30.0))
            return ez / (1.0 + ez)

    @property
    def expected_log_odds(self) -> float:
        """Exact baseline expected log-odds E[f(X)] across the tree ensemble."""
        return self.base_log_odds + sum(t.expected_value for t in self.trees)

    @staticmethod
    def _fit_best_split(
        X_cols: List[List[float]],
        indices: List[int],
        grad: List[float],
        hess: List[float],
        candidate_quantiles: List[List[float]],
        l2_reg: float = 5.0,
    ) -> Tuple[int, float, List[int], List[int]]:
        n_features = len(X_cols)
        total_g = sum(grad[i] for i in indices)
        total_h = sum(hess[i] for i in indices)
        base_gain = (total_g * total_g) / (total_h + l2_reg)

        best_gain = -1.0
        best_feat = 0
        best_thr = 0.0

        for f_idx in range(n_features):
            col = X_cols[f_idx]
            for thr in candidate_quantiles[f_idx]:
                g_l = 0.0
                h_l = 0.0
                for i in indices:
                    if col[i] <= thr:
                        g_l += grad[i]
                        h_l += hess[i]
                g_r = total_g - g_l
                h_r = total_h - h_l
                if h_l < 1.0 or h_r < 1.0:
                    continue
                gain = (g_l * g_l) / (h_l + l2_reg) + (g_r * g_r) / (h_r + l2_reg) - base_gain
                if gain > best_gain:
                    best_gain = gain
                    best_feat = f_idx
                    best_thr = thr

        col_b = X_cols[best_feat]
        left_idx = [i for i in indices if col_b[i] <= best_thr]
        right_idx = [i for i in indices if col_b[i] > best_thr]
        if not left_idx or not right_idx:
            mid = max(1, len(indices) // 2)
            left_idx = indices[:mid]
            right_idx = indices[mid:]
        return best_feat, best_thr, left_idx, right_idx

    def _try_fit_snapml(self, X: List[List[float]], y: List[int]) -> bool:
        """Attempts to train a native `snapml.BoostingMachineClassifier` and call `optimize_trees(tree_format='auto')`."""
        if importlib.util.find_spec("snapml") is None:
            self.snapml_clf = None
            return False
        try:
            import numpy as np  # type: ignore
            from snapml import BoostingMachineClassifier  # type: ignore

            X_np = np.asarray(X, dtype=np.float32)
            y_np = np.asarray(y, dtype=np.int32)
            clf = BoostingMachineClassifier(
                n_jobs=4,
                max_depth=2,
                num_round=self.n_trees,
                learning_rate=self.learning_rate,
                random_state=42,
            )
            clf.fit(X_np, y_np)
            clf.optimize_trees(tree_format="auto")
            self.snapml_clf = clf
            self.active_backend = "snapml.BoostingMachineClassifier(tree_format='auto')"
            return True
        except Exception:
            self.snapml_clf = None
            return False

    def fit(self, X: List[List[float]], y: List[int], pos_weight: float = 12.0) -> None:
        """Trains depth-2 GBDT ensemble with empirical node cover and initializes Snap ML when installed."""
        n = len(X)
        n_features = len(FEATURE_NAMES)

        for f in range(n_features):
            vals = [row[f] for row in X]
            mean_v = sum(vals) / max(1, n)
            var_v = sum((v - mean_v) ** 2 for v in vals) / max(1, n - 1)
            self.feature_means[f] = mean_v
            self.feature_stds[f] = max(1e-4, math.sqrt(var_v))

        pos_indices = [i for i, label in enumerate(y) if label == 1]
        neg_indices = [i for i, label in enumerate(y) if label == 0]
        step = max(1, len(neg_indices) // max(4000, len(pos_indices) * 8))
        sampled_neg = neg_indices[::step]
        train_idx = pos_indices + sampled_neg

        X_sub = [X[i] for i in train_idx]
        y_sub = [y[i] for i in train_idx]
        m = len(X_sub)
        X_cols = [[X_sub[i][f] for i in range(m)] for f in range(n_features)]

        candidate_quantiles: List[List[float]] = []
        for f in range(n_features):
            sorted_v = sorted(set(X_cols[f]))
            if len(sorted_v) <= 16:
                candidate_quantiles.append(sorted_v)
            else:
                grid = [i / 16.0 for i in range(1, 16)] + [0.96, 0.985]
                qs = [sorted_v[int(q * (len(sorted_v) - 1))] for q in grid]
                candidate_quantiles.append(sorted(set(qs)))

        pos_sum = sum(y_sub) * pos_weight
        neg_sum = (m - sum(y_sub)) * 1.0
        p0 = max(1e-4, min(1.0 - 1e-4, pos_sum / (pos_sum + neg_sum)))
        self.base_log_odds = math.log(p0 / (1.0 - p0))

        raw_preds = [self.base_log_odds] * m
        all_indices = list(range(m))
        l2_reg = 5.0
        self.trees = []
        feat_importance = [0.0] * n_features

        for _ in range(self.n_trees):
            grad = [0.0] * m
            hess = [0.0] * m
            for i in range(m):
                p = self._sigmoid(raw_preds[i])
                w = pos_weight if y_sub[i] == 1 else 1.0
                grad[i] = w * (p - y_sub[i])
                hess[i] = max(1e-5, w * p * (1.0 - p))

            r_feat, r_thr, l_idx, r_idx = self._fit_best_split(
                X_cols, all_indices, grad, hess, candidate_quantiles, l2_reg
            )
            l_feat, l_thr, ll_idx, lr_idx = self._fit_best_split(
                X_cols, l_idx, grad, hess, candidate_quantiles, l2_reg
            )
            ri_feat, ri_thr, rl_idx, rr_idx = self._fit_best_split(
                X_cols, r_idx, grad, hess, candidate_quantiles, l2_reg
            )

            def _leaf_val(idxs: List[int]) -> float:
                if not idxs:
                    return 0.0
                g_s = sum(grad[i] for i in idxs)
                h_s = sum(hess[i] for i in idxs)
                return -self.learning_rate * (g_s / (h_s + l2_reg))

            w_left = max(1e-4, min(1.0 - 1e-4, len(l_idx) / max(1, m)))
            w_ll_given_l = max(1e-4, min(1.0 - 1e-4, len(ll_idx) / max(1, len(l_idx))))
            w_rl_given_r = max(1e-4, min(1.0 - 1e-4, len(rl_idx) / max(1, len(r_idx))))

            tree = Depth2Tree(
                root_feat=r_feat,
                root_thresh=r_thr,
                left_feat=l_feat,
                left_thresh=l_thr,
                right_feat=ri_feat,
                right_thresh=ri_thr,
                leaf_ll=_leaf_val(ll_idx),
                leaf_lr=_leaf_val(lr_idx),
                leaf_rl=_leaf_val(rl_idx),
                leaf_rr=_leaf_val(rr_idx),
                w_left=w_left,
                w_ll_given_l=w_ll_given_l,
                w_rl_given_r=w_rl_given_r,
            )
            self.trees.append(tree)
            feat_importance[r_feat] += 2.0
            feat_importance[l_feat] += 1.0
            feat_importance[ri_feat] += 1.0

            for i in range(m):
                raw_preds[i] += tree.predict_one(X_sub[i])

        total_imp = max(1.0, sum(feat_importance))
        self.feature_weights = [v / total_imp for v in feat_importance]

        if not self._try_fit_snapml(X_sub, y_sub):
            self.active_backend = "portable_python_depth2_gbdt (snapml package not installed on host)"

    def raw_margin(self, features: List[float]) -> float:
        """Returns the raw log-odds margin before the logistic link function."""
        z = self.base_log_odds
        for t in self.trees:
            z += t.predict_one(features)
        return z

    def score_one(self, features: List[float]) -> float:
        """Scores a single transaction feature vector."""
        if self.snapml_clf is not None:
            try:
                import numpy as np  # type: ignore

                arr = np.asarray([features], dtype=np.float32)
                return float(self.snapml_clf.predict_proba(arr)[0, 1])
            except Exception:
                pass
        return self._sigmoid(self.raw_margin(features))

    def score_batch(self, feature_rows: List[List[float]]) -> List[float]:
        """Scores a micro-batch of transaction feature vectors."""
        if self.snapml_clf is not None:
            try:
                import numpy as np  # type: ignore

                arr = np.asarray(feature_rows, dtype=np.float32)
                probs = self.snapml_clf.predict_proba(arr)[:, 1]
                return [float(p) for p in probs]
            except Exception:
                pass
        return [self._sigmoid(self.raw_margin(row)) for row in feature_rows]

    def explain_instance(self, features: List[float]) -> List[float]:
        """Computes exact path-dependent TreeSHAP values (in log-odds units) for all 12 features.

        Satisfies exact additivity: sum(shap_values) + self.expected_log_odds == self.raw_margin(features).
        """
        phi = [0.0] * len(FEATURE_NAMES)
        for t in self.trees:
            t.shap_contributions(features, phi)
        return phi

    def top_reason_codes(self, features: List[float], top_k: int = 3) -> List[Dict[str, Any]]:
        """Returns the top-k features by exact TreeSHAP magnitude, preserving signed impact."""
        phi = self.explain_instance(features)
        margin = self.raw_margin(features)
        prob = self._sigmoid(margin)

        # For high-risk transactions (prob >= 0.5), prioritize positive risk-driving SHAP values;
        # for low-risk transactions (prob < 0.5, e.g., benign corporate payroll), prioritize negative
        # risk-suppressing SHAP values so analysts see why the transfer was cleared.
        indexed = list(enumerate(phi))
        if prob >= 0.5:
            indexed.sort(key=lambda item: item[1], reverse=True)
        else:
            indexed.sort(key=lambda item: item[1])

        reasons: List[Dict[str, Any]] = []
        for idx, shap_val in indexed[:top_k]:
            fname = FEATURE_NAMES[idx]
            val = features[idx]
            if fname == "time_since_last_credit_log":
                secs = int(max(1.0, math.expm1(val)))
                formatted_val = f"{secs}s after credit" if secs < 7200 else "No recent credit"
            elif "ratio" in fname:
                formatted_val = f"{val:.2f}x inflow"
            elif "flag" in fname or "novelty" in fname:
                formatted_val = "Yes" if val >= 0.5 else "No"
            else:
                formatted_val = f"{val:.2f}"
            reasons.append(
                {
                    "feature": fname,
                    "label": REASON_LABELS[fname],
                    "value": formatted_val,
                    "shap_log_odds": round(shap_val, 4),
                    "impact": f"{shap_val:+.3f}",
                }
            )
        return reasons

    def to_json_dict(self) -> Dict[str, Any]:
        """Serializes the trained model into a safe, portable JSON dictionary (no pickle)."""
        return {
            "model_version": self.MODEL_VERSION,
            "n_trees": self.n_trees,
            "learning_rate": self.learning_rate,
            "base_log_odds": self.base_log_odds,
            "expected_log_odds": self.expected_log_odds,
            "active_backend": self.active_backend,
            "feature_names": FEATURE_NAMES,
            "feature_means": self.feature_means,
            "feature_stds": self.feature_stds,
            "feature_weights": self.feature_weights,
            "trees": [asdict(t) for t in self.trees],
        }

    def save_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(self.to_json_dict(), f, indent=2)

    @classmethod
    def load_json(cls, path: Path) -> "SnapMLAcceleratedScorer":
        data = json.loads(path.read_text(encoding="utf-8"))
        scorer = cls(
            n_trees=int(data["n_trees"]),
            learning_rate=float(data["learning_rate"]),
        )
        scorer.base_log_odds = float(data["base_log_odds"])
        scorer.feature_means = [float(x) for x in data["feature_means"]]
        scorer.feature_stds = [float(x) for x in data["feature_stds"]]
        scorer.feature_weights = [float(x) for x in data["feature_weights"]]
        scorer.active_backend = str(data.get("active_backend", "portable_python_depth2_gbdt"))
        scorer.trees = [Depth2Tree(**t_dict) for t_dict in data["trees"]]
        return scorer


class LogisticRegressionBaseline:
    """Weighted L2-regularized Logistic Regression trained on the exact same 12 causal features."""

    def __init__(self, lr: float = 0.15, epochs: int = 120, l2: float = 0.01) -> None:
        self.lr = lr
        self.epochs = epochs
        self.l2 = l2
        self.means: List[float] = [0.0] * len(FEATURE_NAMES)
        self.stds: List[float] = [1.0] * len(FEATURE_NAMES)
        self.weights: List[float] = [0.0] * len(FEATURE_NAMES)
        self.bias: float = 0.0

    def fit(self, X: List[List[float]], y: List[int], pos_weight: float = 10.0) -> None:
        n = len(X)
        d = len(FEATURE_NAMES)
        for j in range(d):
            col = [row[j] for row in X]
            m_val = sum(col) / max(1, n)
            v_val = sum((v - m_val) ** 2 for v in col) / max(1, n - 1)
            self.means[j] = m_val
            self.stds[j] = max(1e-4, math.sqrt(v_val))

        pos_idx = [i for i, lbl in enumerate(y) if lbl == 1]
        neg_idx = [i for i, lbl in enumerate(y) if lbl == 0]
        step = max(1, len(neg_idx) // max(3000, len(pos_idx) * 6))
        sub_idx = pos_idx + neg_idx[::step]

        X_std = [
            [(X[i][j] - self.means[j]) / self.stds[j] for j in range(d)]
            for i in sub_idx
        ]
        y_sub = [y[i] for i in sub_idx]
        m = len(sub_idx)

        self.weights = [0.0] * d
        self.bias = -2.0

        for _ in range(self.epochs):
            grad_w = [0.0] * d
            grad_b = 0.0
            total_w = 0.0
            for row, lbl in zip(X_std, y_sub):
                z = self.bias + sum(self.weights[j] * row[j] for j in range(d))
                p = SnapMLAcceleratedScorer._sigmoid(z)
                w = pos_weight if lbl == 1 else 1.0
                err = w * (p - lbl)
                for j in range(d):
                    grad_w[j] += err * row[j]
                grad_b += err
                total_w += w
            inv = 1.0 / max(1.0, total_w)
            for j in range(d):
                self.weights[j] -= self.lr * (grad_w[j] * inv + self.l2 * self.weights[j])
            self.bias -= self.lr * (grad_b * inv)

    def score_one(self, features: List[float]) -> float:
        z = self.bias
        for j in range(len(FEATURE_NAMES)):
            z += self.weights[j] * ((features[j] - self.means[j]) / self.stds[j])
        return SnapMLAcceleratedScorer._sigmoid(z)


class VelocityRulesBaseline:
    """Traditional static velocity-rules engine used by legacy bank AML systems."""

    @staticmethod
    def score_one(features: List[float]) -> float:
        fan_in_1h = features[0]
        fan_out_1h = features[1]
        fan_out_24h = features[3]
        pt_15m = features[4]
        pt_1h = features[5]
        rapid_flag = features[7]
        amt_z = features[9]
        vel_1h = features[10]

        points = 0.0
        if fan_out_1h >= 3.0:
            points += 0.30
        if fan_in_1h >= 3.0:
            points += 0.22
        if fan_out_24h >= 5.0:
            points += 0.15
        if 0.65 <= pt_15m <= 1.50:
            points += 0.25
        elif pt_1h >= 0.85 and fan_out_1h >= 3.0:
            points += 0.12
        if rapid_flag >= 0.9:
            points += 0.20
        if amt_z >= 2.2:
            points += 0.18
        if vel_1h >= 3.0:
            points += 0.15
        return min(0.99, points)
