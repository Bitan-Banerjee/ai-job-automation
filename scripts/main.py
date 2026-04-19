import sys
import os
import time
import argparse
import csv
import json
from datetime import datetime

try:
    from linkedin_scraper import scrape_linkedin_jobs
    from naukri_scraper import scrape_naukri_jobs
    from match_job_gemini import match_jobs_batched
    from auto_apply import auto_apply
    from naukri_auto_apply import naukri_apply
    from tailor_resume import tailor_resumes
    from export_tracker import export_to_excel
except ImportError as e:
    print(f"❌ Failed to import a necessary script. Make sure all scripts are in the /scripts folder. Error: {e}")
    sys.exit(1)

class TeeLogger(object):
    def __init__(self, stream, *files):
        self.terminal = stream
        self.files = files

    def write(self, message):
        self.terminal.write(message)
        for f in self.files:
            f.write(message)
            f.flush()

    def flush(self):
        self.terminal.flush()
        for f in self.files:
            f.flush()

def setup_logging():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    now = datetime.now()
    
    # 1. Setup daily archive log
    log_dir = os.path.join(base_dir, 'logs', now.strftime("%Y"), now.strftime("%m"), now.strftime("%d"))
    os.makedirs(log_dir, exist_ok=True)
    log_filename = os.path.join(log_dir, f"run_{now.strftime('%H-%M-%S')}.log")
    
    # 2. Setup a static Markdown mirror for the AI context
    latest_filename = os.path.join(base_dir, "latest_run.md")
    with open(latest_filename, "w", encoding="utf-8") as f:
        f.write(f"# Pipeline Run: {now.strftime('%Y-%m-%d %H:%M:%S')}\n\n```text\n")
        
    log_file = open(log_filename, "a", encoding="utf-8")
    latest_file = open(latest_filename, "a", encoding="utf-8")
    
    sys.stdout = TeeLogger(sys.stdout, log_file, latest_file)
    sys.stderr = TeeLogger(sys.stderr, log_file, latest_file)
    return log_filename

def get_todays_application_count():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tracker_path = os.path.join(base_dir, 'Job_Applications_Tracker.csv')
    if not os.path.exists(tracker_path):
        return 0
        
    today = datetime.now().strftime("%Y-%m-%d")
    count = 0
    try:
        with open(tracker_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader, None)
            if not headers: return 0
            if "Date Applied" not in headers or "Status" not in headers: return 0
            
            date_idx = headers.index("Date Applied")
            status_idx = headers.index("Status")
            
            for row in reader:
                if len(row) > max(date_idx, status_idx):
                    if row[date_idx] == today and "Applied" in row[status_idx]:
                        count += 1
    except Exception:
        pass
    return count

def run_daily_quota_loop(target_quota=50, max_loops=4):
    print(f"\n🎯 DAILY QUOTA MODE ACTIVATED: Target {target_quota} Applications")
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    for attempt in range(1, max_loops + 1):
        current_count = get_todays_application_count()
        print(f"\n📊 Current Applications Today: {current_count} / {target_quota}")
        
        if current_count >= target_quota:
            print("✅ Daily quota met! Shutting down gracefully.")
            break
            
        remaining = target_quota - current_count
        # Estimate scrape volume: assume ~10-15% match rate.
        jobs_to_scrape = min(remaining * 8, 150)
        
        print(f"\n🔄 --- PIPELINE LOOP {attempt}/{max_loops} (Attempting to find {remaining} more matches) ---")
        
        # Quarantine failed/skipped applications before wiping
        failed_path = os.path.join(base_dir, 'data', 'failed_applications.json')
        for prefix in ['linkedin', 'naukri']:
            matched_path = os.path.join(base_dir, 'data', f'{prefix}_matched_jobs.json')
            if os.path.exists(matched_path):
                try:
                    with open(matched_path, 'r') as f:
                        approved_jobs = json.load(f).get('approved_jobs', [])
                    
                    failed_jobs = [j for j in approved_jobs if j.get('status') != 'applied']
                    if failed_jobs:
                        all_failed = []
                        if os.path.exists(failed_path):
                            with open(failed_path, 'r') as f:
                                all_failed = json.load(f).get('failed_jobs', [])
                        all_failed.extend(failed_jobs)
                        with open(failed_path, 'w') as f:
                            json.dump({"failed_jobs": all_failed}, f, indent=4)
                        print(f"  📥 Quarantined {len(failed_jobs)} failed/skipped {prefix} applications.")
                except Exception as e:
                    print(f"  ⚠️ Failed to quarantine {prefix} jobs: {e}")

        # Wipe intermediate files to start fresh, but keep seen_jobs.json
        for prefix in ['linkedin', 'naukri']:
            for suffix in ['_jobs.json', '_matched_jobs.json']:
                f_path = os.path.join(base_dir, 'data', f"{prefix}{suffix}")
                if os.path.exists(f_path):
                    os.remove(f_path)
        
        # Run Naukri Pipeline
        naukri_success = run_naukri_pipeline(max_jobs=jobs_to_scrape, start_stage=1)
        
        # Check quota again before running LinkedIn
        current_count = get_todays_application_count()
        if current_count >= target_quota:
            print("✅ Daily quota met after Naukri! Skipping LinkedIn.")
            break
            
        remaining = target_quota - current_count
        jobs_to_scrape = min(remaining * 8, 150)
        
        # Run LinkedIn Pipeline
        linkedin_success = run_linkedin_pipeline(max_jobs=jobs_to_scrape, start_stage=1)
        
        if not linkedin_success and not naukri_success:
            print("⚠️ Both pipelines encountered critical errors. Resting for 60s before next attempt...")
            time.sleep(60)
    else:
        print(f"\n⚠️ Reached max loops ({max_loops}). Did not hit quota. Resting until tomorrow.")

def determine_start_stage(prefix="linkedin"):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    jobs_path = os.path.join(base_dir, 'data', f'{prefix}_jobs.json')
    matched_path = os.path.join(base_dir, 'data', f'{prefix}_matched_jobs.json')
    
    if os.path.exists(matched_path):
        try:
            with open(matched_path, 'r') as f:
                approved = json.load(f).get('approved_jobs', [])
            if not approved:
                return 5
            if all(j.get('status') == 'applied' for j in approved):
                return 5
            if prefix == "linkedin" and any(not j.get('tailored_resume_path') for j in approved):
                return 3
            return 4
        except:
            return 1
    elif os.path.exists(jobs_path):
        return 2
    return 1

def run_linkedin_pipeline(max_jobs=25, start_stage=1):
    print("\n" + "="*50)
    print("🚀🚀🚀 STARTING LINKEDIN PIPELINE 🚀🚀🚀")
    print(f"📍 Starting from STAGE {start_stage}")
    print("=" * 50)
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    scraped_path = os.path.join(base_dir, 'data', 'linkedin_jobs.json')
    matched_path = os.path.join(base_dir, 'data', 'linkedin_matched_jobs.json')
    
    if start_stage <= 1:
        try:
            print("\n[STAGE 1/5] 🌐 Scraping fresh jobs from LinkedIn...")
            max_pages = (max_jobs // 25) + 2
            scrape_linkedin_jobs(keyword="Data Engineer", location="India", max_pages=max_pages, max_jobs=max_jobs, output_file=scraped_path)
            print("[STAGE 1/5] ✅ Scraping complete.")
            time.sleep(2)
        except Exception as e:
            print(f"\n[CRITICAL FAILURE] 🔥 LinkedIn Pipeline failed at STAGE 1: SOURCING.")
            print(f"  └─ Error: {e}")
            return False

    if start_stage <= 2:
        try:
            print("\n[STAGE 2/5] 🧠 Filtering jobs with Gemini AI...")
            match_jobs_batched(scraped_path=scraped_path, matched_path=matched_path)
            print("[STAGE 2/5] ✅ Filtering complete.")
            time.sleep(2)
        except Exception as e:
            print(f"\n[CRITICAL FAILURE] 🔥 LinkedIn Pipeline failed at STAGE 2: FILTERING.")
            print(f"  └─ Error: {e}")
            return False

    if start_stage <= 3:
        try:
            print("\n[STAGE 3/5] ✍️ Tailoring resumes for approved jobs...")
            tailor_resumes(matched_path=matched_path)
            print("[STAGE 3/5] ✅ Tailoring complete.")
            time.sleep(2)
        except Exception as e:
            print(f"\n[CRITICAL FAILURE] 🔥 LinkedIn Pipeline failed at STAGE 3: TAILORING.")
            print(f"  └─ Error: {e}")
            return False

    if start_stage <= 4:
        try:
            print("\n[STAGE 4/5] 🤖 Deploying Auto-Apply Bot...")
            auto_apply(matched_path=matched_path)
            print("[STAGE 4/5] ✅ Auto-Applying complete.")
        except Exception as e:
            print(f"\n[CRITICAL FAILURE] 🔥 LinkedIn Pipeline failed at STAGE 4: APPLYING.")
            print(f"  └─ Error: {e}")
            return False

    if start_stage <= 5:
        try:
            print("\n[STAGE 5/5] 📊 Exporting daily applications to Excel tracker...")
            export_to_excel(matched_path=matched_path)
            print("[STAGE 5/5] ✅ Export complete.")
        except Exception as e:
            print(f"\n[WARNING] ⚠️ Pipeline finished, but failed to export to Excel: {e}")
            
    return True

def run_naukri_pipeline(max_jobs=25, start_stage=1):
    print("\n" + "="*50)
    print("🚀🚀🚀 STARTING NAUKRI PIPELINE 🚀🚀🚀")
    print(f"📍 Starting from STAGE {start_stage}")
    print("=" * 50)
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    scraped_path = os.path.join(base_dir, 'data', 'naukri_jobs.json')
    matched_path = os.path.join(base_dir, 'data', 'naukri_matched_jobs.json')
    
    if start_stage <= 1:
        try:
            print("\n[STAGE 1/4] 🌐 Scraping fresh jobs from Naukri...")
            scrape_naukri_jobs(keyword="Data Engineer", location="India", max_jobs=max_jobs, output_file=scraped_path)
            print("[STAGE 1/4] ✅ Scraping complete.")
            time.sleep(2)
        except Exception as e:
            print(f"\n[CRITICAL FAILURE] 🔥 Naukri Pipeline failed at STAGE 1: SOURCING.\n  └─ Error: {e}")
            return False

    if start_stage <= 2:
        try:
            print("\n[STAGE 2/4] 🧠 Filtering jobs with Gemini AI...")
            match_jobs_batched(scraped_path=scraped_path, matched_path=matched_path)
            print("[STAGE 2/4] ✅ Filtering complete.")
            time.sleep(2)
        except Exception as e:
            print(f"\n[CRITICAL FAILURE] 🔥 Naukri Pipeline failed at STAGE 2: FILTERING.\n  └─ Error: {e}")
            return False

    if start_stage <= 4:
        try:
            print("\n[STAGE 3/4] 🤖 Deploying Naukri Auto-Apply Bot...")
            naukri_apply(matched_path=matched_path)
            print("[STAGE 3/4] ✅ Auto-Applying complete.")
        except Exception as e:
            print(f"\n[CRITICAL FAILURE] 🔥 Naukri Pipeline failed at STAGE 3: APPLYING.\n  └─ Error: {e}")
            return False

    if start_stage <= 5:
        try:
            print("\n[STAGE 4/4] 📊 Exporting daily applications to Excel tracker...")
            export_to_excel(matched_path=matched_path)
            print("[STAGE 4/4] ✅ Export complete.")
        except Exception as e:
            print(f"\n[WARNING] ⚠️ Pipeline finished, but failed to export to Excel: {e}")
        
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the AI Job Application Pipeline.")
    parser.add_argument("--jobs", type=int, default=25, help="Maximum number of jobs to scrape and process.")
    parser.add_argument("--target", type=int, default=50, help="Daily quota target for continuous looping.")
    parser.add_argument("--max-loops", type=int, default=4, help="Maximum number of loop iterations.")
    parser.add_argument("--resume", action="store_true", help="Auto-detect where the pipeline left off and resume.")
    parser.add_argument("--start-stage", type=int, default=1, choices=[1, 2, 3, 4, 5], help="Manually force the pipeline to start at a specific stage (1-5).")
    args = parser.parse_args()
    
    log_file = setup_logging()
    print(f"📝 Logging this run to: {log_file}")
    
    if args.resume or args.start_stage != 1:
        if args.resume:
            l_stage = determine_start_stage("linkedin")
            n_stage = determine_start_stage("naukri")
            if l_stage < 5:
                print(f"🔍 Resume flag detected. Starting LinkedIn at stage: {l_stage}")
                run_linkedin_pipeline(max_jobs=args.jobs, start_stage=l_stage)
            if n_stage < 5:
                print(f"🔍 Resume flag detected. Starting Naukri at stage: {n_stage}")
                run_naukri_pipeline(max_jobs=args.jobs, start_stage=n_stage)
        else:
            run_linkedin_pipeline(max_jobs=args.jobs, start_stage=args.start_stage)
            run_naukri_pipeline(max_jobs=args.jobs, start_stage=args.start_stage)
    else:
        # Default behavior: run the daily quota goal-oriented loop
        run_daily_quota_loop(target_quota=args.target, max_loops=args.max_loops)