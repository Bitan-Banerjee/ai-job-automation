import os
import json
import re
from auto_apply import auto_apply
from naukri_auto_apply import naukri_apply
from utils.export_tracker import export_to_excel

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILED_PATH = os.path.join(BASE_DIR, 'data', 'failed_applications.json')
MAX_RETRIES = 999 

def load_safe_json(path):
    """Read JSON safely."""
    if not os.path.exists(path): return {}
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    try:
        return json.loads(content, strict=False)
    except Exception as e:
        try:
            # This regex looks for // that isn't preceded by : (to avoid https://)
            clean_content = re.sub(r'(?<!:)//.*', '', content)
            return json.loads(clean_content, strict=False)
        except:
            print(f"⚠️ Failed to parse {path}: {e}")
            return None

def retry_failed_jobs():
    if not os.path.exists(FAILED_PATH):
        print("✅ No failed applications found.")
        return

    data = load_safe_json(FAILED_PATH)
    if not data: return
    
    failed_jobs = data.get('failed_jobs', [])
    if not failed_jobs:
        print("✅ Failed applications list is empty.")
        return

    linkedin_jobs = [j for j in failed_jobs if 'linkedin.com' in j.get('url', '')]
    naukri_jobs = [j for j in failed_jobs if 'naukri.com' in j.get('url', '')]

    print(f"🔄 Retrying {len(linkedin_jobs)} LinkedIn and {len(naukri_jobs)} Naukri jobs.")
    
    # We will reconstruct the failed list after processing
    still_failed = []

    if linkedin_jobs:
        temp_path = os.path.join(BASE_DIR, 'data', 'linkedin_matched_jobs.json')
        with open(temp_path, 'w') as f: json.dump({"approved_jobs": linkedin_jobs}, f, indent=4)
        print("\n🚀 Retrying LinkedIn Jobs...")
        auto_apply(matched_path=temp_path)
        export_to_excel(matched_path=temp_path)
        
        try:
            with open(temp_path, 'r') as f: processed = json.load(f).get("approved_jobs", [])
            for j in processed:
                status = j.get('status')
                if status not in ['applied', 'skipped_low_score', 'expired']:
                    j['retry_count'] = j.get('retry_count', 0) + 1
                    still_failed.append(j)
                elif status == 'expired':
                    print(f"  🗑️ Removed expired LinkedIn job: {j.get('company')}")
            if os.path.exists(temp_path): os.remove(temp_path)
        except Exception: pass
        
    if naukri_jobs:
        temp_path = os.path.join(BASE_DIR, 'data', 'naukri_matched_jobs.json')
        with open(temp_path, 'w') as f: json.dump({"approved_jobs": naukri_jobs}, f, indent=4)
        print("\n🚀 Retrying Naukri Jobs...")
        naukri_apply(matched_path=temp_path)
        export_to_excel(matched_path=temp_path)
        
        try:
            with open(temp_path, 'r') as f: processed = json.load(f).get("approved_jobs", [])
            for j in processed:
                status = j.get('status')
                if status not in ['applied', 'skipped_low_score', 'expired']:
                    j['retry_count'] = j.get('retry_count', 0) + 1
                    still_failed.append(j)
                elif status == 'expired':
                    print(f"  🗑️ Removed expired Naukri job: {j.get('company')}")
            if os.path.exists(temp_path): os.remove(temp_path)
        except Exception: pass
        
    # Final check: Update failed_applications.json
    with open(FAILED_PATH, 'w') as f: json.dump({"failed_jobs": still_failed}, f, indent=4)
    
    recovered = len(failed_jobs) - len(still_failed)
    print(f"\n🎉 Retry complete! Recovered/Cleaned {recovered} applications. {len(still_failed)} still in failed list.")

if __name__ == "__main__":
    retry_failed_jobs()
