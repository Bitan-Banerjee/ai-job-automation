import sys
import os
import time

try:
    from linkedin_scraper import scrape_linkedin_jobs
    from match_job_gemini import match_jobs_batched
    from auto_apply import auto_apply
except ImportError as e:
    print(f"❌ Failed to import a necessary script. Make sure all scripts are in the /scripts folder. Error: {e}")
    sys.exit(1)

def run_pipeline():
    """
    Orchestrates the end-to-end job application pipeline from scraping to applying.
    """
    print("🚀🚀🚀 STARTING AI JOB APPLICATION PIPELINE 🚀🚀🚀")
    print("-" * 50)
    
    # --- STAGE 1: SOURCING ---
    try:
        print("\n[STAGE 1/3] 🌐 Scraping fresh jobs from LinkedIn...")
        # Scrape first 2 pages, up to 25 jobs max for a daily run
        scrape_linkedin_jobs(keyword="Data Engineer", location="India", max_pages=2, max_jobs=25)
        print("[STAGE 1/3] ✅ Scraping complete.")
        time.sleep(2)
    except Exception as e:
        print(f"\n[CRITICAL FAILURE] 🔥 Pipeline failed at STAGE 1: SOURCING.")
        print(f"  └─ Error: {e}")
        sys.exit(1)

    print("-" * 50)

    # --- STAGE 2: FILTERING ---
    try:
        print("\n[STAGE 2/3] 🧠 Filtering jobs with Gemini AI...")
        match_jobs_batched()
        print("[STAGE 2/3] ✅ Filtering complete.")
        time.sleep(2)
    except Exception as e:
        print(f"\n[CRITICAL FAILURE] 🔥 Pipeline failed at STAGE 2: FILTERING.")
        print(f"  └─ Error: {e}")
        sys.exit(1)

    print("-" * 50)

    # --- STAGE 3: APPLYING ---
    try:
        print("\n[STAGE 3/3] 🤖 Deploying Auto-Apply Bot...")
        auto_apply()
        print("[STAGE 3/3] ✅ Auto-Applying complete.")
    except Exception as e:
        print(f"\n[CRITICAL FAILURE] 🔥 Pipeline failed at STAGE 3: APPLYING.")
        print(f"  └─ Error: {e}")
        sys.exit(1)

    print("-" * 50)
    print("\n🎉🎉🎉 PIPELINE COMPLETED SUCCESSFULLY! 🎉🎉🎉")

if __name__ == "__main__":
    run_pipeline()