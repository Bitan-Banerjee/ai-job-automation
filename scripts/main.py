import sys
import os
import time
import argparse
import csv
import json
from datetime import datetime

try:
    from linkedin_scraper import scrape_linkedin_jobs
    from match_job_gemini import match_jobs_batched
    from auto_apply import auto_apply
    from tailor_resume import tailor_resumes
    from export_tracker import export_to_excel
except ImportError as e:
    print(f"❌ Failed to import a necessary script. Make sure all scripts are in the /scripts folder. Error: {e}")
    sys.exit(1)

class TeeLogger(object):
    def __init__(self, filename, stream):
        self.terminal = stream
        self.log = open(filename, "a", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()

    def flush(self):
        self.terminal.flush()
        self.log.flush()

def setup_logging():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    now = datetime.now()
    log_dir = os.path.join(base_dir, 'logs', now.strftime("%Y"), now.strftime("%m"), now.strftime("%d"))
    os.makedirs(log_dir, exist_ok=True)
    log_filename = os.path.join(log_dir, f"run_{now.strftime('%H-%M-%S')}.log")
    sys.stdout = TeeLogger(log_filename, sys.stdout)
    sys.stderr = TeeLogger(log_filename, sys.stderr)
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
        
        # Wipe intermediate files to start fresh, but keep seen_jobs.json
        for f_name in ['jobs.json', 'matched_jobs.json']:
            f_path = os.path.join(base_dir, 'data', f_name)
            if os.path.exists(f_path):
                os.remove(f_path)
        
        success = run_pipeline(max_jobs=jobs_to_scrape, start_stage=1)
        
        if not success:
            print("⚠️ Loop encountered a critical error. Resting for 60s before next attempt...")
            time.sleep(60)
    else:
        print(f"\n⚠️ Reached max loops ({max_loops}). Did not hit quota. Resting until tomorrow.")

def determine_start_stage():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    jobs_path = os.path.join(base_dir, 'data', 'jobs.json')
    matched_path = os.path.join(base_dir, 'data', 'matched_jobs.json')
    
    if os.path.exists(matched_path):
        try:
            with open(matched_path, 'r') as f:
                approved = json.load(f).get('approved_jobs', [])
            if not approved:
                return 5
            if all(j.get('status') == 'applied' for j in approved):
                return 5
            if any(not j.get('tailored_resume_path') for j in approved):
                return 3
            return 4
        except:
            return 1
    elif os.path.exists(jobs_path):
        return 2
    return 1

def run_pipeline(max_jobs=25, start_stage=1):
    """
    Orchestrates the end-to-end job application pipeline from scraping to applying.
    """
    print("🚀🚀🚀 STARTING AI JOB APPLICATION PIPELINE 🚀🚀🚀")
    print(f"📍 Starting from STAGE {start_stage}")
    print("-" * 50)
    
    if start_stage <= 1:
        # --- STAGE 1: SOURCING ---
        try:
            print("\n[STAGE 1/5] 🌐 Scraping fresh jobs from LinkedIn...")
            print(f"    Targeting up to {max_jobs} NEW jobs (Scanning up to 20 pages deeply).")
            scrape_linkedin_jobs(keyword="Data Engineer", location="India", max_pages=20, max_jobs=max_jobs)
            print("[STAGE 1/5] ✅ Scraping complete.")
            time.sleep(2)
        except Exception as e:
            print(f"\n[CRITICAL FAILURE] 🔥 Pipeline failed at STAGE 1: SOURCING.")
            print(f"  └─ Error: {e}")
            return False
        print("-" * 50)

    if start_stage <= 2:
        # --- STAGE 2: FILTERING ---
        try:
            print("\n[STAGE 2/5] 🧠 Filtering jobs with Gemini AI...")
            match_jobs_batched()
            print("[STAGE 2/5] ✅ Filtering complete.")
            time.sleep(2)
        except Exception as e:
            print(f"\n[CRITICAL FAILURE] 🔥 Pipeline failed at STAGE 2: FILTERING.")
            print(f"  └─ Error: {e}")
            return False
        print("-" * 50)

    if start_stage <= 3:
        # --- STAGE 3: TAILORING RESUMES ---
        try:
            print("\n[STAGE 3/5] ✍️ Tailoring resumes for approved jobs...")
            tailor_resumes()
            print("[STAGE 3/5] ✅ Tailoring complete.")
            time.sleep(2)
        except Exception as e:
            print(f"\n[CRITICAL FAILURE] 🔥 Pipeline failed at STAGE 3: TAILORING.")
            print(f"  └─ Error: {e}")
            return False
        print("-" * 50)

    if start_stage <= 4:
        # --- STAGE 4: APPLYING ---
        try:
            print("\n[STAGE 4/5] 🤖 Deploying Auto-Apply Bot...")
            auto_apply()
            print("[STAGE 4/5] ✅ Auto-Applying complete.")
        except Exception as e:
            print(f"\n[CRITICAL FAILURE] 🔥 Pipeline failed at STAGE 4: APPLYING.")
            print(f"  └─ Error: {e}")
            return False
        print("-" * 50)

    if start_stage <= 5:
        # --- STAGE 5: LOGGING ---
        try:
            print("\n[STAGE 5/5] 📊 Exporting daily applications to Excel tracker...")
            export_to_excel()
            print("[STAGE 5/5] ✅ Export complete.")
        except Exception as e:
            print(f"\n[WARNING] ⚠️ Pipeline finished, but failed to export to Excel: {e}")
        print("-" * 50)
        
    print("\n🎉🎉🎉 PIPELINE COMPLETED SUCCESSFULLY! 🎉🎉🎉")
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
        stage = args.start_stage
        if args.resume:
            stage = determine_start_stage()
            print(f"🔍 Resume flag detected. Auto-determined starting stage: {stage}")
        run_pipeline(max_jobs=args.jobs, start_stage=stage)
    else:
        # Default behavior: run the daily quota goal-oriented loop
        run_daily_quota_loop(target_quota=args.target, max_loops=args.max_loops)