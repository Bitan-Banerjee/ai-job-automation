# AI Job Application Pipeline

An end-to-end, fully autonomous AI agent that scrapes, filters, tailors, and applies to jobs on LinkedIn. 

Built with **Python**, **Playwright**, and **Google Gemini**, this pipeline doesn't just "spray and pray." It acts as a highly discerning personal recruiter: it evaluates jobs against your strict dealbreakers, scores them, rewrites your resume for each specific role, and handles dynamic application forms—all while respecting API rate limits and running completely hands-free.

---

## Key Features

- **Goal-Oriented Looping Agent:** Tell it to get 50 applications today, and it will continuously scrape, filter, and apply until it hits the target.
- **Zero-Token Sourcing Gatekeepers:** Smart Python regex filters instantly drop junk roles (e.g., Senior, QA, Frontend) and saturated jobs (>100 applicants) *before* wasting AI tokens.
- **A-F AI Scoring System:** Evaluates job descriptions against your `profile.json` dealbreakers and assigns a 0-100 match score.
- **Playwright PDF Engine:** Bypasses clunky `.docx` manipulation. Uses Gemini to rewrite your `base_resume.md` summary and bullets, injects them into an HTML/CSS template, and prints a pixel-perfect, ATS-optimized PDF for *every single job*.
- **Dynamic Form Solver:** Uses Gemini to read unseen LinkedIn "Easy Apply" questions, answers them on the fly, and saves the answers to a local memory bank (`job_qa_registry.json`) for future use.
- **Smart Checkpointing:** Network dropped? Run with `--resume` and it automatically detects where it left off based on local files.

---

## Prerequisites & Installation

You will need Python 3.10+ and a Google AI Studio API Key (Free Tier is fully supported due to built-in fallback routing).

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/AiAutomation.git
cd AiAutomation
```

### 2. Install Dependencies
The project relies on Playwright for browser automation and the official Google GenAI SDK.
```bash
pip3 install playwright google-genai python-dotenv
```

### 3. Install Headless Browsers
Playwright requires browser binaries to navigate LinkedIn:
```bash
playwright install chromium
```

---

## Configuration

Before running the bot, you must set up your credentials and personal data.

### 1. Environment Variables
Create a `.env` file in the root directory:
```env
LINKEDIN_EMAIL="your.email@example.com"
LINKEDIN_PASSWORD="your_password"
GEMINI_API_KEY="your_google_gemini_api_key"
# Optional: Add backup keys to automatically bypass daily free-tier rate limits
GEMINI_API_KEY_2="your_second_gemini_key"
```

### 2. Configure Your Profile
Edit `config/profile.json`. This tells the AI exactly what you are looking for and what your hard dealbreakers are.
```json
{
  "target_role": "Data Engineer",
  "candidate_experience": "3.8 years (Open to 0-5 years)",
  "core_skills": ["Python", "SQL", "PySpark", "AWS"],
  "dealbreakers": [
    "DB1: Job strictly requires MORE than 5 years of experience.",
    "DB2: Job requires training or building AI/ML models.",
    "DB3: Job requires Azure or GCP, but does NOT mention AWS."
  ]
}
```

### 3. Set Your Master Resume
Edit `base_resume.md` in the root directory. Put your actual, highly-detailed career history here using standard Markdown. The AI will use this as the "Source of Truth" when tailoring PDFs.

*(Note: Do not delete `templates/cv-template.html`, as it provides the CSS styling for your PDFs!)*

---

## Usage

The entire pipeline is orchestrated by `main.py`.

### Standard Run (Goal-Oriented)
To start the agent and have it loop until it successfully applies to 50 jobs today:
```bash
python3 scripts/main.py --target 50
```

### Quick Test Run
To run a single, small batch without looping:
```bash
python3 scripts/main.py --jobs 25 --max-loops 1
```

### Resume from Interruption
If the script crashes or your internet drops, don't start over! Use the resume flag to automatically detect local files and pick up exactly where it left off:
```bash
python3 scripts/main.py --resume
```

### Automating with Cron (macOS/Linux)
To run the bot completely hands-free every morning at 9:00 AM, add this to your `crontab -e`:
```bash
0 9 * * * cd /path/to/AiAutomation && /usr/local/bin/python3 scripts/main.py --target 50
```

---

## How It Works (The 5 Stages)

### [STAGE 1] Sourcing (`linkedin_scraper.py`)
*   Logs into LinkedIn and searches for your target role using exact phrase matching (e.g., `"%22Data Engineer%22"`).
*   Filters for roles posted in the last 72 hours.
*   Applies a fast Python "Title Gatekeeper" to instantly drop frontend, QA, or senior management roles.
*   Drops jobs with >100 applicants to ensure high-probability targets.
*   Saves raw data to `data/jobs.json`.

### [STAGE 2] Filtering (`match_job_gemini.py`)
*   Batches 10 jobs at a time and sends them to the Gemini API.
*   Uses a robust **Fallback Router** (`gemini-flash-latest` -> `gemini-2.5-flash` -> `gemini-flash-lite-latest`) to completely bypass free-tier rate limits and 503 server errors.
*   Evaluates the jobs against your `profile.json` dealbreakers.
*   Approves valid jobs, scores them (0-100), and saves to `data/matched_jobs.json`.

### [STAGE 3] Tailoring (`tailor_resume.py`)
*   Reads your `base_resume.md`.
*   Asks Gemini to rephrase your summary and bullet points to highlight the exact keywords found in the specific job description (without hallucinating new experience).
*   Outputs raw HTML, injects it into `templates/cv-template.html`, and uses Playwright to print an ATS-friendly PDF.
*   Saves the PDF to a time-stamped archive (e.g., `outputs/resumes/2026/04/18/Resume_Company.pdf`).

### [STAGE 4] Applying (`auto_apply.py`)
*   Playwright navigates to the approved jobs scoring >80.
*   Clicks "Easy Apply" and uploads the *specific* tailored PDF for that company.
*   If it encounters a form question it hasn't seen before, it batches the questions, asks Gemini for the answers based on your profile, and saves them to `data/job_qa_registry.json`.
*   Submits the application.

### [STAGE 5] Logging (`export_tracker.py` & `TeeLogger`)
*   Appends the successfully applied jobs to a master database at `Job_Applications_Tracker.csv`.
*   Includes the Date, Company, Title, URL, AI Score, and the absolute path to the PDF used.
*   Throughout the entire process, console output is simultaneously written to `logs/YYYY/MM/DD/run.log` for easy debugging.

---

## Directory Structure

```text
AiAutomation/
├── scripts/
│   ├── main.py                 # Master Orchestrator & Looping Agent
│   ├── linkedin_scraper.py     # Playwright Sourcing
│   ├── match_job_gemini.py     # AI Dealbreaker Filtering
│   ├── tailor_resume.py        # PDF Generation
│   ├── auto_apply.py           # Playwright Application Submitter
│   ├── export_tracker.py       # CSV Database Writer
│   └── update_registry.py      # Setup script for QA memory
├── config/
│   └── profile.json            # Target role and AI dealbreakers
├── templates/
│   └── cv-template.html        # CSS styling for generated PDFs
├── data/                       # Ephemeral short-term memory (Gitignored)
│   ├── jobs.json
│   ├── matched_jobs.json
│   ├── job_qa_registry.json
│   └── linkedin_session.json
├── outputs/                    # Time-stamped PDF cold storage (Gitignored)
├── logs/                       # Time-stamped terminal logs (Gitignored)
├── .env                        # Credentials (Gitignored)
├── base_resume.md              # Master CV (Source of Truth)
└── Job_Applications_Tracker.csv# Master application database
```

---

## Disclaimer
This tool automates interactions with LinkedIn. Please use responsibly and ensure you comply with LinkedIn's Terms of Service. The AI generates application answers and resumes on your behalf; you should routinely audit `job_qa_registry.json` and the generated PDFs to ensure absolute accuracy.