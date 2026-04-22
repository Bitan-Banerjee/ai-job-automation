# AI Assistant Context & Developer Journal

> **⚠️ SYSTEM INSTRUCTION FOR AI ASSISTANT:**
> Update `AI_CONTEXT.md` every 5 prompts. Log decisions, problems, solutions, details. No context loss between sessions.

## 🧑‍💻 Developer Profile & Preferences
- **Workflow:** Iterative, step-by-step. Plan first, code second. Wait for approval.
- **Evaluation Strategy:** Optimize for **Recall**. Accept false positives to catch dream jobs.
- **Infrastructure:** Prioritize local open-source models (Llama 3.2, Gemma 2). Use Cloud APIs (Gemini) batched. **(Gemini Free Tier: 5 RPM, 20 RPD)**.
- **Hardware Context:** Apple Silicon Mac. Parallel large models (9B+) = bottleneck. Small models / batched cloud = OK.

## 🐛 Debugging Philosophy (Diagnose First)
- **No Blind Fixes:** No assumptions on UI/locator failures.
- **Evidence Collection:** Write diagnostic code (`page.screenshot()`, `page.content()`). Analyze before fix.
- **The Debugging Loop:** When a complex UI issue (like the Naukri Chatbot) is identified:
  1. Create/Update a standalone `debug_<platform>.py` script.
  2. Implement aggressive element dumping and logging.
  3. Integrate Gemini calls directly into the debug script to verify end-to-end flow.
  4. **The Proof Mandate:** You MUST successfully complete at least one application and verify "Success" or "Already Applied" states in the debug script before merging the fix into the production code.
  5. **State Integrity Mandate:** Detection of success is useless if the system state (failed jobs list, tracker) is not updated. A task is only complete when the job is removed from the failed list and logged in the tracker.
  6. Continue the "Fix -> Run -> Evidence -> Fix" cycle autonomously without asking permission for debug script changes or terminal commands.

## 🧠 Job Matching Evolution
...
### 8. Naukri Chatbot Integration (The Breakthrough)
- **Problem:** Naukri shifted to dynamic single-question chatbots that use `contenteditable` DIVs and binary "pills" instead of standard forms. Previous logic saw them as "ghost panels".
- **Solution:** 
  - specialized extraction targeting `.chatbot_MessageContainer`.
  - Prioritizing pill-clicking over text input for binary questions.
  - Aggressive event dispatching (`change`, `click`) to trigger state updates in modern UI frameworks.
  - Detection of the green "Applied" button as a primary success indicator.

## 📱 Social Media Strategy & Post Generation
- **X (Twitter):** 2 hashtags. 1 broad (#BuildInPublic), 1 niche (#AIAutomation).
- **LinkedIn:** 3-5 hashtags. Suggest 1-2 @mentions.
- **Optimization:** Professional, engaging. No generic tags.

## 🚀 Project Overview
End-to-end AI job automation pipeline:
1. **Sourcing:** `linkedin_scraper.py` (Playwright, logins, pagination).
2. **Filtering:** Match jobs vs Profile/Dealbreakers.
3. **Tailoring:** `tailor_resume.py` (Gemini, rewrite resume).
4. **Applying:** `auto_apply.py` (Playwright, AI answer questions, submit).

## 🧠 Job Matching Evolution
Iterated architectures for Speed, Accuracy, Cost.

### 1. Llama 3.2 (Fast but Flawed)
- **Metrics:** 25 jobs | 440s | 15 Approved | 10 Rejected.
- **Pitfalls:** 3B models suffer "attention collapse".
  - **Schema Hallucinations:** Copy prompt, not extract tech.
  - **Context Traps:** Confuse noise with requirements.
  - **Logic Failures:** Contradict reasoning.

### 2. Gemma 2 (Accurate but Slow)
- **Metrics:** 25 jobs | 3011s | 17 Approved | 8 Rejected.
- **Problem:** Good comprehension, but concurrent jobs choked Mac memory.

### 3. Gemini Batched API (Fast but "Lazy")
- **Approach:** Batch 15 jobs per payload.
- **Problem:** No reasoning step = lazy matching, high false positives (missed exp requirements).

### 4. Hybrid Llama Improvements (`test_hybrid_match.py`)
Split into 4 Micro-Agents:
1. **Few-Shot Prompting:** Stop hallucinations.
2. **Constrained Decoding:** Strict JSON Schemas.
3. **Context Distillation:** Strip noise before LLM.
4. **Self-Consistency:** 3x parallel runs, majority vote.
5. **Reflexion:** Auditor agent double-checks.
6. **Chain of Thought (CoT):** Step-by-step logic.
- **Verdict:** Multi-agent script 622s/25 jobs. 3B models lack multi-variable synthesis.

### 5. Dual-Model Hybrid (Llama -> Gemma)
- **Problem:** Apple Silicon VRAM thrashing switching between 3B and 9B models.
- **Conclusion:** Single pass with Gemma 2 (9B) more efficient.

### 6. Local Optimization (Gemma on Apple Silicon)
- **Prompt-Level Batching:** 5 jobs/payload. Maximize GPU, stop thrashing.
- **Prompt Caching:** Static prefix (Profile/Rules) at top.
- **Apple MLX Framework:** Native inference, huge speedup.
- **Quantization:** `Q4_K_M` halves memory bandwidth.
- **Speculative Decoding:** Small model drafts, large model verifies.

## 📍 Current State
- **Llama experiment:** Concluded. 3B models fail synthesis.
- **Gemma 2 (`match_job.py`):** Accurate, slow for 1000+ jobs.
- **Gemini Batch (`match_job_gemini.py`):** Production path. Needs reasoning.
- **Auto Apply (`auto_apply.py`):** Use local Gemma 2 for form questions.
- **Naukri Updater:** Deprecated. Anti-bot WAF issues.

### Update: Local Pipeline Upgraded (Batching + MLX)
- `match_job.py` use **Prompt-Level Batching** + **Prefix Caching**.
  - **Result:** 25 jobs / 19 mins (2.6x speedup).
  - **Pitfall:** Context bleeding between jobs.
- `match_job_mlx.py` use **MLX** framework.
- **Nomenclature:** `gemma4` (Ollama) = **Gemma 2 (9B)**. MLX use `mlx-community/gemma-2-9b-it-4bit`.

### Update: MLX Troubleshooting
- **Sleep Issue:** Use `caffeinate` for downloads.
- **HF Throttling:** Use `HF_TOKEN` in `.env`.
- **Cache Lock:** Delete `.cache/huggingface/hub/.locks`.
- **Kwarg Error:** Remove `temp=0.0` from `generate()`.
- **GPU Timeout (8GB RAM):** Disabled Speculative Decoding.
- **OOM:** Reduced `BATCH_SIZE` to 1.
- **OOM Final:** Switch to `mlx-community/gemma-2-2b-it-4bit` for stability.

### 7. Further Local Optimizations
- **Deterministic Pre-filtering:** Regex/keyword rejection before LLM.
- **Early Exit:** Fast LLM first, slow CoT only if borderline.
- **Asynchronous I/O:** `asyncio` for disk writes.

## 🎯 Next Steps
1. **Direct ATS Scraper:** Zero-token scraper for Greenhouse/Lever.
2. **Deep Research Mode:** Pre-interview prep.

## 📈 Recent Architectural Upgrades
1. **Profile Decoupling:** `config/profile.json` for job targets.
2. **Token-Efficient Scoring:** 0-100 score in Gemini filtering.
3. **Playwright PDF Engine:**
   - Use `base_resume.md`.
   - `tailor_resume.py` rewrite markdown -> HTML -> PDF via Chromium.
   - Fix: Regex extraction to stop hallucinated wrappers.
4. **Sourcing:** Exact phrase match, wider window, relevance gatekeeper, applicant cap (<100).
5. **Orchestrator:** `main.py` loop until 50 applications met.
6. **Application Quarantine:** Save failed apps to `failed_applications.json`.
7. **Directory Cleanup:** Root at `/AiAutomation/`.
8. **Naukri Integration:** `naukri_scraper.py`, `naukri_auto_apply.py`.
9. **Hub/Spoke:** Decoupled pipelines, state isolation.
10. **Multi-Key Router:** Fallback for Gemini API keys.
11. **Static Logger:** `latest_run.md` for AI assistant.
12. **Early Score Rejection:** Reject `< 80` score in Stage 2.

## 🚨 Latest Run Logs
```text
# Pipeline Run: 2026-04-20 10:28:05
```
