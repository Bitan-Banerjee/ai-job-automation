import os
import json
import time
from dotenv import load_dotenv
from google import genai

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'))

try:
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
except Exception as e:
    print(f"Failed to initialize Gemini Client: {e}")
    client = None

SCRAPED_PATH = os.path.join(BASE_DIR, 'data', 'jobs.json')
MATCHED_PATH = os.path.join(BASE_DIR, 'data', 'matched_jobs.json')
PROFILE_PATH = os.path.join(BASE_DIR, 'config', 'profile.json')

BATCH_SIZE = 10  # Balanced for Gemini Flash to handle reasoning tokens safely
DELAY_BETWEEN_BATCHES = 15  # 15 seconds delay to stay safely under the 5 RPM limit

def passes_basic_filter(title):
    title_lower = title.lower()
    red_flags = ['director', 'manager', 'vp', 'lead', 'head']
    for flag in red_flags:
        if flag in title_lower.split():
            return False
    return True

def evaluate_job_batch(batch_jobs, profile_data):
    if not client:
        return {}
        
    # Create a compact payload for the AI to read
    jobs_payload = []
    for i, job in enumerate(batch_jobs):
        jobs_payload.append({
            "id": str(i),
            "title": job.get('title'),
            "company": job.get('company'),
            "description": job.get('description', '')
        })

    dealbreakers_text = "\n    ".join(profile_data.get('dealbreakers', []))
    skills_text = ", ".join(profile_data.get('core_skills', []))

    prompt = f"""
    You are an expert technical recruiter. 
    
    Candidate Profile:
    Target Role: {profile_data.get('target_role')}
    Candidate Experience: {profile_data.get('candidate_experience')}
    Core Skills: {skills_text}
    
    CRITICAL DEALBREAKERS (Reject if ANY are true):
    {dealbreakers_text}

    Evaluate the following batch of jobs. 
    Return ONLY a valid JSON object mapping the "id" to an object containing your step-by-step reasoning against the dealbreakers, a "score" from 0 to 100 based on skill alignment, and the final "match" boolean.
    
    Format exactly like this:
    {{
      "0": {{"reasoning": "Job needs 2-4 years exp. Mentions AWS.", "score": 85, "match": true}},
      "1": {{"reasoning": "Job requires 8+ years experience, violating DB1.", "score": 0, "match": false}}
    }}

    Jobs to evaluate:
    '''
    {json.dumps(jobs_payload)}
    '''
    """
    
    fallback_models = ['gemini-flash-latest', 'gemini-2.5-flash', 'gemini-flash-lite-latest']
    for model_name in fallback_models:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            text = response.text.strip()
            if text.startswith("```json"): text = text[7:-3].strip()
            elif text.startswith("```"): text = text[3:-3].strip()
            return json.loads(text)
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                print(f"  ⚠️ 429 Rate Limit hit on {model_name}. Switching to next model...")
                continue
            elif "404" in error_str or "NOT_FOUND" in error_str:
                print(f"  ⚠️ Model {model_name} not found. Switching to next model...")
                continue
            elif "503" in error_str or "UNAVAILABLE" in error_str:
                print(f"  ⚠️ 503 Service Unavailable on {model_name}. Switching to next model...")
                continue
            else:
                print(f"  ⚠️ API Error on batch with {model_name}: {error_str}")
                return {}
    print("  ❌ All fallback models exhausted due to rate limits.")
    return {}

def match_jobs_batched():
    start_time = time.time()
    if not os.path.exists(SCRAPED_PATH):
        print(f"❌ Missing {SCRAPED_PATH}.")
        return
        
    if not os.path.exists(PROFILE_PATH):
        print(f"❌ Missing {PROFILE_PATH}. Please create profile.json in the root directory.")
        return
        
    try:
        with open(PROFILE_PATH, 'r') as f:
            profile_data = json.load(f)
    except json.JSONDecodeError:
        print(f"❌ Error: {PROFILE_PATH} is empty or contains invalid JSON.")
        return
        
    try:
        with open(SCRAPED_PATH, 'r') as f:
            jobs = json.load(f).get('jobs', [])
    except json.JSONDecodeError:
        print(f"❌ Error: {SCRAPED_PATH} is empty or contains invalid JSON.")
        return
        
    # Pre-filter to save API calls
    valid_jobs = [j for j in jobs if passes_basic_filter(j.get('title', ''))]
    
    print(f"🔍 Evaluating {len(valid_jobs)} jobs using Gemini Batched API (Batch Size: {BATCH_SIZE})...")
    approved_jobs = []
    
    for i in range(0, len(valid_jobs), BATCH_SIZE):
        batch = valid_jobs[i:i + BATCH_SIZE]
        print(f"\n📦 Sending Batch {i//BATCH_SIZE + 1} ({len(batch)} jobs) to Gemini...")
        
        results = evaluate_job_batch(batch, profile_data)
        
        for job_idx_str, data in results.items():
            idx = int(job_idx_str)
            if idx < len(batch):
                company = batch[idx].get('company', 'Unknown')
                title = batch[idx].get('title', 'Unknown')
                
                # Extract boolean and reasoning safely
                if isinstance(data, dict):
                    is_match = str(data.get("match", "false")).lower() == "true"
                    reason = data.get("reasoning", "No reasoning provided.")
                    score = data.get("score", 0)
                else:
                    is_match = str(data).lower() == "true"
                    reason = "No reasoning provided."
                    score = 0
                
                if is_match:
                    print(f"  ✅ MATCHED (Score: {score}): {company} - {title}")
                    print(f"     └ 📝 {reason}")
                    batch[idx]['ai_score'] = score
                    approved_jobs.append(batch[idx])
                else:
                    print(f"  ❌ REJECTED (Score: {score}): {company} - {title}")
                    print(f"     └ 📝 {reason}")
        
        # Respect the 5 RPM rate limit (if there are more batches to process)
        if i + BATCH_SIZE < len(valid_jobs):
            print(f"  ⏳ Sleeping for {DELAY_BETWEEN_BATCHES}s to respect API rate limits...")
            time.sleep(DELAY_BETWEEN_BATCHES)
            
    os.makedirs(os.path.dirname(MATCHED_PATH), exist_ok=True)
    with open(MATCHED_PATH, 'w') as f:
        json.dump({"approved_jobs": approved_jobs}, f, indent=4)
        
    print(f"\n🎉 Done! Approved {len(approved_jobs)} jobs. Saved to {MATCHED_PATH}")
    print(f"⏱️ Total runtime: {time.time() - start_time:.2f} seconds")

if __name__ == "__main__":
    match_jobs_batched()