# HopStop — 3-Minute Video Pitch & Demo Recording Script
**IBM Z Datathon 2026 — Track 1: Real-Time AI for Critical Decisions**  
**Presenter:** Kabir Roy (B.Tech CSE, VIT Bhopal)  
**Target Duration:** 2 minutes 50 seconds (safe buffer under the strict 3:00 limit)  
**Speaking Rate:** 135 words/minute (clear, authoritative, measured)

---

## Quick Setup Before You Hit Record

1. **Start the local server:**
   ```bash
   python -m hopstop.server
   ```
2. **Open browser in Full Screen (F11):** Navigate to `http://127.0.0.1:8080`.
3. **Have tabs ready:**
   - Tab 1: `http://127.0.0.1:8080` (HopStop Live Analyst Console)
   - Tab 2: `submission/HopStop_System_Architecture.svg` (System Architecture Diagram)
   - Tab 3: Terminal with `pytest tests/test_hopstop.py` or Git repo page.
4. **Resolution:** 1080p (1920x1080) at 30 or 60 fps.

---

## Master Teleprompter & Visual Storyboard

| Timestamp | Visual on Screen | What Kabir Says (Word-for-Word Script) |
| :---: | :--- | :--- |
| **0:00 – 0:30**<br/>*(30 sec)* | **Camera on Kabir** (or split-screen with Title Slide / Pitch Deck Slide 1). | *"Hello judges. I'm Kabir Roy, a Computer Science student at VIT Bhopal. Today, when an online financial scam, phishing fraud, or extortion happens, stolen victim money doesn't stay in one place. Over instant payment rails like UPI, IMPS, and wire transfers, funds are rapidly funneled through layers of money-mule accounts across multiple banks in minutes.<br/><br/>Traditional bank AML runs in overnight batches—by then, funds have already crossed 3 to 5 hops and are lost forever. Meanwhile, static velocity rules flag normal corporate payroll batches as false positives. We need pre-settlement AI that stops the mule chain cold at Hop 1 or Hop 2."* |
| **0:30 – 1:05**<br/>*(35 sec)* | **Switch to Architecture Diagram** (`HopStop_System_Architecture.svg`). Smoothly zoom from Stream Ingress to IBM Z Enclave. | *"That is why I built **HopStop**—a real-time, pre-settlement graph-velocity interdiction engine co-located directly on IBM Z and LinuxONE.<br/><br/>Instead of making risky 30-millisecond roundtrips to external clouds, HopStop evaluates every payment on-platform in under **0.16 milliseconds**.<br/><br/>It combines an amortized $O(1)$ streaming feature engine with a dual-generation rotating Bloom filter, an IBM Z-tailored depth-2 GBDT and Snap ML scorer calibrated with Day-7 isotonic regression, and a tamper-evident HMAC-SHA256 hash-chained audit ledger powered by IBM Z CPACF hardware cryptography."* |
| **1:05 – 2:15**<br/>*(70 sec)* | **Switch to Live Browser Console** (`http://127.0.0.1:8080`).<br/><br/>1. Point to Top KPI cards.<br/>2. Click Scenario 1 (Mule Fan-Out).<br/>3. Click Scenario 4 (Corporate Payroll).<br/>4. Move the Alert-Budget Slider.<br/>5. Scroll to Multi-Hop Chain Topology. | *"Let's see HopStop live in action on our interactive console.<br/><br/>Across an unseen test split of over 15,000 transactions, HopStop achieves a **0.810 PR-AUC**—an **81% lift** over traditional rules—while holding end-to-end P99 latency under **0.4 milliseconds**.<br/><br/>[**Action: Click Scenario 1**] Watch this first payment: an INR 185,000 wire transfer. Within microseconds, HopStop issues a **HOLD** pre-settlement. Look at the exact TreeSHAP reason codes: rapid 96% credit-to-debit drain and high outbound velocity.<br/><br/>[**Action: Click Scenario 4**] Now, here is our core differentiator: a legitimate corporate payroll batch of INR 42,000 to five employees. Traditional velocity rules falsely freeze this account because of high fan-out. But HopStop safely issues an **ALLOW** in under 0.05 milliseconds, because the 15-minute pass-through ratio is zero and our 128-kilobyte Bloom filter recognizes the employees as known corporate payees.<br/><br/>[**Action: Drag Alert-Budget Slider**] Risk teams can slide our alert-budget calibrator between 0.5% and 2.5% daily capacity. Even at a tight 1.0% alert budget, HopStop stops **84% of all laundering chains by Hop 2**, protecting victims and empowering emergency freezes under India's 1930 Cybercrime Helpline."* |
| **2:15 – 2:45**<br/>*(30 sec)* | **Switch to Terminal / GitHub Repo.**<br/>Show `pytest tests/test_hopstop.py` (`22 passed`) and `git log`. | *"Everything in HopStop is engineered for production rigor. We have **22 automated unit and tamper tests** passing in our CI pipeline—verifying strict $O(1)$ temporal causality with zero future leakage, exact TreeSHAP local additivity, and single-byte cryptographic tamper detection across all 15,232 chained decisions.<br/><br/>HopStop is packaged with a native LinuxONE container definition, Snap ML integration, and an open Apache-2.0 license."* |
| **2:45 – 3:00**<br/>*(15 sec)* | **Camera back on Kabir** (or closing summary slide with GitHub link). | *"By pairing causal streaming graph features with the uncompromising speed and security of IBM Z and Snap ML, HopStop turns mainframe core banking from a passive record-keeper into an active pre-settlement shield.<br/><br/>Thank you for your time, and I look forward to your questions!"* |

---

## Pro-Tips for Delivering the Best Pitch

1. **Smile and speak with conviction:** You built a legitimate, mathematically sound, 22-test-verified system. Own the narrative!
2. **Move the mouse deliberately:** When clicking on Scenarios 1 and 4, pause for 1 second so the viewer sees the red **HOLD** and green **ALLOW** badges and the TreeSHAP feature bars animate.
3. **Show the topology stage:** Make sure the viewer sees the red barrier at Hop 1 and the green "BLOCKED_UPSTREAM" downstream hops—judges love this visual proof of saving victim funds.
4. **Keep it under 3:00:** The script above is 395 words. Spoken naturally with pauses, it will clock in around **2 minutes 45 seconds**, perfectly within the competition rules.
