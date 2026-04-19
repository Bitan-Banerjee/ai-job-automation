# AI Assistant Context & Developer Journal

> **⚠️ SYSTEM INSTRUCTION FOR AI ASSISTANT:** 
> Update this `AI_CONTEXT.md` file to save our progress **after every 5 prompts** (or when explicitly requested). Log any new decisions, problems faced, solutions engineered, and minute details so no context is ever lost between sessions.

## 🧑‍💻 Developer Profile & Preferences
- **Workflow:** Prefers iterative, step-by-step development and testing. **Crucially, when asked to solve a problem or build a feature, discuss the overarching structure and plan first. Do NOT output line-by-line code fixes immediately—wait for user approval on the plan.**
- **Evaluation Strategy:** Optimizes for **Recall** (catching every possible good job) over strict **Precision** (willing to accept a few false positives to ensure no dream jobs are missed).
- **Infrastructure:** Highly prioritizes free, local, open-source models (like Llama 3.2 and Gemma 4) to avoid cloud API rate limits and costs. Will use Cloud APIs (like Gemini) only if batched efficiently to respect strict free-tier limits. **(Gemini Free Tier Hard Caps: 5 Requests Per Minute (RPM), 20 Requests Per Day (RPD))**.
- **Hardware Context:** Running on an Apple Silicon Mac. Parallel execution of large local models (9B+ parameters like Gemma 4) causes memory/context-switching bottlenecks, whereas small models or batched cloud requests handle parallelization well.

## 📱 Social Media Strategy & Post Generation
When drafting or refining posts for X (Twitter) or LinkedIn, act as a Tech/AI Social Media Strategist and automatically append a "Tags & Optimization" section at the end.
- **X (Twitter) Rules:** Exactly 2 hashtags at the very end (1 broad like #BuildInPublic, 1 niche like #AIAutomation or #DataEngineering).
- **LinkedIn Rules:** Exactly 3-5 hashtags (mixing industry-specific and professional growth). Suggest 1-2 contextually relevant influential accounts or Company Pages to @mention to increase reach.
- **Optimization:** NEVER use generic tags (e.g., #Happy, #Work). Prioritize tags used by the #BuildInPublic and #AI communities. Maintain a professional yet engaging tone for LinkedIn.

## � Project Overview
Building a highly advanced, end-to-end AI job application automation pipeline:
1. **Sourcing:** `linkedin_scraper.py` (Playwright-based, handles logins, pagination, and seen-job tracking).
2. **Filtering:** AI-powered matching scripts to evaluate raw job descriptions against a strict Candidate Profile with specific "Dealbreakers".
3. **Tailoring:** `tailor_resume.py` (Uses Gemini to rewrite the base resume to match the approved job).
4. **Applying:** `auto_apply.py` (Playwright-based bot that dynamically asks the AI to answer unseen application questions, saves them to a registry/memory, and submits the form).

## 🧠 The Job Matching Evolution (Challenges & Solutions)
We iterated through several architectures to find the perfect balance of Speed, Accuracy, and Cost.

### 1. The Llama 3.2 Baseline (Fast but Flawed)
- **25-Job Benchmark Metrics:** Runtime: ~440 seconds (7.3 mins) | Approved: 15 | Rejected: 10
- **Specific Pitfalls:** Small models (3B) suffer from "attention collapse". 
  - **Schema Hallucinations:** Blindly copied prompt instructions (e.g., outputting `['list']` instead of extracting the actual tech stack).
  - **Context Traps:** Swept up in noise, confusing "founders have 10+ years experience" with the actual candidate requirements.
  - **Logic Failures:** Struggled heavily with negative constraints and frequently contradicted its own reasoning.

### 2. The Gemma 4 Approach (Accurate but Slow)
- **25-Job Benchmark Metrics:** Runtime: 3011 seconds (~50 mins) | Approved: 17 | Rejected: 8
- **Problem:** Local `gemma4` had flawless reading comprehension and perfectly evaluated the dealbreakers. However, processing jobs concurrently choked the Mac's unified memory, taking ~50 minutes for 25 jobs.

### 3. The Gemini Batched API (Lightning Fast but "Lazy")
- **25-Job Benchmark Metrics:** Runtime: 62.8 seconds | Approved: 19 | Rejected: 6
- **Approach:** Created `match_job_gemini.py` to batch 15 jobs per payload, outputting only `true/false` to bypass the strict 5 RPM / 20 RPD free-tier limits.
- **Problem:** Extremely fast, but removing the "Reasoning" step caused the LLM to get lazy and miss strict dealbreakers, resulting in the highest False Positive rate (e.g., explicitly passing roles demanding 6+ years of experience).

### 4. Architectural Improvements on Llama (`test_hybrid_match.py`)
- **Approach:** To overcome Llama 3.2's severe pitfalls and make it accurate, we split the evaluation into 4 distinct Micro-Agents.
- **The 6 AI Researcher Techniques Applied:**
  1. **Few-Shot Prompting (In-Context Learning):** Added explicit Input->Output examples to the prompts to stop schema hallucinations.
  2. **Constrained Decoding:** Passed strict JSON Schemas directly to `ollama.chat(format=schema)` to physically prevent the LLM from outputting invalid JSON types.
  3. **Context Distillation:** Built a Python function to strip noise ("founded in", "raised $") *before* the LLM reads the text, preventing it from falling for founder experience traps.
  4. **Self-Consistency (Majority Voting):** Ran the final Evaluator 3 times in parallel at `temperature=0.6` and took the majority vote to eliminate random hallucinated paths.
  5. **Reflexion:** Added a QA "Auditor" agent that double-checks the Experience Extractor's output against common traps before passing it downstream.
  6. **Chain of Thought (CoT):** Added a `"thought_process"` field to the JSON schemas so the models generate their step-by-step logic *before* committing to final integers/booleans.
- **The Final Verdict (The Parameter Ceiling):** The fully-loaded multi-agent script took ~622 seconds (10.3 mins) for 25 jobs. While CoT and Reflexion perfectly fixed the Experience/Domain extraction, the Final Evaluator suffered from "Reasoning Collapse." It could not reliably compare the extracted JSON against the English rules without outputting circular, contradictory logic. 
- **Conclusion:** 3B parameter models are excellent for heavily-guided single-task extraction, but lack the parameter depth for multi-variable synthesis and evaluation.

### 5. The Dual-Model Hybrid Concept (Llama -> Gemma)
- **Approach:** Proposed using Llama 3.2 for the extraction micro-agents, and handing the structured JSON to Gemma 4 for the final evaluation.
- **The Bottleneck (VRAM Thrashing):** On Apple Silicon unified memory, constantly switching between a 3B model and a 9B model per job causes massive disk I/O overhead. The computer spends more time loading/unloading gigabytes of weights than processing tokens.
- **Conclusion:** On consumer hardware, a single pass with one highly capable model (Gemma 4) is more computationally efficient than a multi-model handoff.

### 6. Advanced Local Optimization (Gemma on Apple Silicon)
- **Prompt-Level Batching:** Instead of Python multi-threading (which causes VRAM context switching), pack 5 job descriptions into a single JSON payload for one Gemma prompt. This maximizes GPU utilization and prevents thrashing.
- **Prompt Caching (Prefix Optimization):** Place the static Candidate Profile and Rules at the very top of the prompt. Modern engines cache the Key-Value (KV) matrix for this prefix, meaning the NPU only has to calculate the new job description tokens.
- **Apple MLX Framework:** Moving away from Ollama (`llama.cpp`) to Apple's native `MLX` framework for local inference can unlock massive speedups on M-series chips.
- **Extreme Quantization:** Ensuring the model is running at `Q4_K_M` (4-bit quantization). It halves the memory bandwidth requirement (the main bottleneck on Apple Silicon) with near-zero reasoning degradation.
- **Speculative Decoding:** A token-level hybrid approach where a tiny model drafts tokens and Gemma verifies them simultaneously (engine-level, not script-level).

## 📍 Current State
- The **Multi-Agent Llama pipeline** experiment is concluded. It proved small models fail at final synthesis even with advanced scaffolding.
- The **Gemma 4** pipeline (`match_job.py`) remains the most accurate local monolithic solution, but is too slow for 1,000+ job runs on current hardware.
- The **Gemini Batch** pipeline (`match_job_gemini.py`) is the chosen production path for speed, but needs its reasoning capability restored to fix false positives.
- The **Auto Apply** bot (`auto_apply.py`) was successfully refactored to use local `gemma4` to prevent API rate limits when answering new form questions.

### Update: Local Pipeline Upgraded (Batching + MLX)
- Refactored `match_job.py` to use **Prompt-Level Batching** (5 jobs per payload) and **Prefix Caching**, eliminating VRAM thrashing and resolving the 50-minute slow runtime issue with Ollama.
  - **Batched Gemma Result:** Processed 25 jobs in 1145 seconds (~19 minutes). This is a **2.6x speedup** over the concurrent method. 
  - **Accuracy:** Very high. It successfully rejected the TCS (6+ yrs), Datum (8+ yrs), and PwC (5-10 yrs) roles. 
  - **Minor Pitfall (Context Bleeding):** Packing 5 jobs into one context window caused slight detail cross-contamination. It hallucinated that the Capgemini job was focused on DBT/SQL and missed the "Mathematics" dealbreaker.
- Created `match_job_mlx.py` to implement native Apple Silicon inference using the `mlx-lm` framework.
- Implemented **Extreme Quantization (4-bit)** and **Speculative Decoding (Gemma 2B drafting for Gemma 9B)** within the MLX script to push generation speed to the physical limits of the M-series chip.
- **Model Nomenclature Clarification:** The local Ollama tag `gemma4` (9.6GB) maps to Google's official **Gemma 2 (9B parameter)** model. The MLX script uses `mlx-community/gemma-2-9b-it-4bit`, guaranteeing the exact same reasoning intelligence but running on a natively optimized hardware framework.
  - **Speed/Efficiency:** MLX vastly outperforms Ollama on Apple Silicon due to zero server overhead and speculative decoding.
  - **Accuracy:** Identical between both scripts.

### Update: MLX Model Download Troubleshooting
- **Problem:** The initial download of the MLX Gemma models (approx. 5.2GB + 1.5GB) hung because the MacBook went to sleep, dropping the network connection mid-download.
- **Solution:** Instructed the use of macOS's native `caffeinate` command (`caffeinate python3 scripts/match_job_mlx.py`) to prevent system sleep during the large initial Hugging Face weights download.
- **Problem 2:** Hugging Face throttled/blocked the unauthenticated download, causing it to hang at `0.00B`.
- **Solution 2:** Generated a free `HF_TOKEN` on Hugging Face, added it to the `.env` file, and updated `match_job_mlx.py` to use `load_dotenv` so the `mlx_lm` downloader could authenticate and bypass the rate limits.
- **Problem 3:** The download remained permanently stuck waiting to acquire a lock (`.locks` file) due to a corrupted cache lock from the previous sleep interruption.
- **Solution 3:** Instructed the user to explicitly delete the hidden `.cache/huggingface/hub/.locks` directory and use the new, robust `hf download` tool to fetch the models.
- **Problem 4:** The MLX script threw an error during batch generation: `speculative_generate_step() got an unexpected keyword argument 'temp'`.
- **Solution 4:** Removed the `temp=0.0` kwarg from the `generate()` call in `match_job_mlx.py`, as MLX's speculative decoding function handles temperature arguments differently in its current version. Allowed it to fall back to default deterministic sampling.
- **Problem 5:** The MLX script crashed with a `[METAL] Command buffer execution failed: Caused GPU Timeout Error` and a memory warning.
- **Solution 5:** Identified that the MacBook Air has 8GB of unified memory (with a ~5.5GB GPU wire limit). Loading both the 9B model (5GB) and the 2B draft model (1.5GB) caused massive disk swapping and a GPU timeout. Disabled Speculative Decoding to fit the pipeline safely within the hardware limits.
- **Problem 6:** MLX script crashed again with `[METAL] Command buffer execution failed: Insufficient Memory`.
- **Solution 6:** Even without the draft model, the 9B model weights (4958 MB) plus the KV cache for a batch of 5 jobs exceeded the 5.5GB limit. Reduced `BATCH_SIZE` to 1 to minimize the KV cache footprint during generation.
- **Problem 7:** MLX script crashed a final time with OOM even at `BATCH_SIZE = 1`. 
- **Solution 7:** Concluded that the 9B model is physically too large for an 8GB Mac to reliably run generation without overflowing the KV cache. Switched the main model to `mlx-community/gemma-2-2b-it-4bit` (1.5GB footprint) for safe, stable execution.

### Update: Review of Local Speed Architectures
- Confirmed that `match_job_mlx.py` successfully utilizes Prompt-Level Batching alongside the other 4 speed optimizations (Prefix Caching, MLX Native Framework, 4-bit Quantization, and Speculative Decoding) to ensure maximum throughput on Apple Silicon.

### 7. Further Local Speed Optimizations (Beyond LLM Inference)
- **Deterministic Pre-filtering:** Using fast Python logic (regex, keyword spotting) to reject obvious dealbreakers *before* involving the LLM, saving expensive inference calls for jobs that pass initial checks.
- **Early Exit / Conditional AI Invocation:** A two-stage AI approach where a faster, less robust LLM prompt is used first. Only if the decision is borderline or complex is the job passed to the full, robust (and slower) CoT/Reflexion LLM pipeline.
- **Asynchronous File I/O:** Using Python's `asyncio` to write results to disk in the background, preventing blocking the main thread from preparing the next LLM batch.

## 🎯 Next Steps
1. **Build Direct ATS Scraper:** Develop a zero-token python scraper for Applicant Tracking Systems (e.g., Greenhouse/Lever) to bypass LinkedIn entirely, acting as a new Sourcing module.
2. **Add "Deep Research" Mode (Optional):** Pre-interview prep generation based on the `career-ops` repository pattern.

## 📈 Recent Architectural Upgrades (Inspired by Career-Ops)
To make the system more robust and token-efficient, we adapted several patterns from the `santifer/career-ops` repository:
1. **Profile Decoupling:** Extracted the hardcoded Candidate Profile and Dealbreakers from `match_job_gemini.py` into a standalone `config/profile.json` configuration file. This allows changing job targets without touching Python code.
2. **Token-Efficient Scoring:** Upgraded the Gemini filtering prompt to not only output a boolean `match`, but also a `score` from 0-100 based on skill alignment. This costs 0 extra API calls but allows sorting jobs by quality. Added this AI Score to the `export_tracker.py` CSV.
3. **Playwright PDF Engine (Resume Tailoring):** 
   - Abandoned Python `.docx` manipulation due to formatting issues.
   - Shifted to a web-based architecture: The candidate's master resume is now a simple `base_resume.md` file.
   - `tailor_resume.py` uses Gemini to rewrite the markdown summary and bullet points, outputs raw HTML, injects it into a CSS-styled `cv-template.html`, and uses Playwright's headless Chromium to instantly print an ATS-optimized, pixel-perfect PDF.
   - **PDF Rendering Fix:** Added Regex extraction and template validation to `tailor_resume.py` to prevent "empty white pages" caused by LLMs hallucinating `<html>`/`<body>` wrapper tags, or the HTML template losing its `{{content}}` placeholder.
4. **Sourcing Optimizations:** Upgraded `linkedin_scraper.py` to use exact phrase matching (`%22`) in the URL, widened the search window to 3 days (`r259200`), added a zero-token `is_title_relevant` Python gatekeeper, and implemented an Applicant Cap logic to immediately drop jobs with >100 applicants.
5. **Goal-Oriented Orchestrator:** Upgraded `main.py` into a robust `while` loop that reads `Job_Applications_Tracker.csv` and repeatedly runs the pipeline (up to 4 times) until the daily quota of 50 successful applications is met.
6. **Application Quarantine:** Added a safety mechanism to `main.py` loop that intercepts `matched_jobs.json` before deletion, saving any jobs missing the `"status": "applied"` tag to a permanent `failed_applications.json` file so tricky forms aren't lost between loops.
7. **Directory Cleanup:** Migrated all active code to `/Users/bitanbanerjee/Coding/GitHub_Repos/AiAutomation/` to properly version control the project via Git while ignoring ephemeral data and environment variables.
8. **Naukri Multi-Platform Integration:** Abstracted the sourcing and application stages in `main.py` to allow swapping between LinkedIn and Naukri. Built `naukri_scraper.py` and `naukri_auto_apply.py` stubs to test the pipeline (bypassing the PDF tailoring step) using the existing agnostic Gemini matching and CSV logging engine.
9. **Hub and Spoke Architecture:** Fully decoupled LinkedIn and Naukri pipelines in `main.py` (`run_linkedin_pipeline` and `run_naukri_pipeline`). Parameterized all core utilities (`match_job_gemini.py`, `tailor_resume.py`, etc.) to accept dynamic `scraped_path` and `matched_path` arguments, ensuring perfect state isolation.
10. **Multi-Key Fallback Router:** Upgraded all AI scripts to accept multiple API keys (`GEMINI_API_KEY`, `GEMINI_API_KEY_2`, etc.). If one account hits the hard 1,500 RPD free-tier limit, the router automatically swaps to the next key. Added hard exceptions when all keys are exhausted to halt the pipeline and prevent silent data loss.
11. **Static Markdown Logger:** Upgraded `TeeLogger` to simultaneously output to a static `latest_run.md` file in the root directory, allowing the AI coding assistant to read crash logs automatically without manual copy-pasting.
12. **Early Score Rejection:** Moved the `>= 80` score threshold directly into Stage 2 (`match_job_gemini.py`) so low-scoring jobs are rejected immediately, saving API tokens that would have been wasted tailoring PDFs.