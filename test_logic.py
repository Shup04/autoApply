import json
import os

# Define mock file paths
PROCESSED_FILE = "processed_jobs_test.json"
JOBS_FILE = "jobs_mock.json"

def setup_test_data():
    # 1. Create a mock jobs file with 3 jobs
    mock_jobs = [
        {"title": "Job A", "company": "Company 1", "url": "url_1"},
        {"title": "Job B", "company": "Company 2", "url": "url_2"},
        {"title": "Job C", "company": "Company 3", "url": "url_3"}
    ]
    with open(JOBS_FILE, 'w') as f:
        json.dump(mock_jobs, f)

    # 2. Initialize processed file with only ONE of those jobs (Job A)
    with open(PROCESSED_FILE, 'w') as f:
        json.dump(["url_1"], f)

def load_processed():
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, 'r') as f:
            return json.load(f)
    return []

def run_test():
    setup_test_data()
    processed_urls = load_processed()
    
    with open(JOBS_FILE, 'r') as f:
        jobs = json.load(f)

    print(f"--- Starting Test (Processed URLs: {processed_urls}) ---")
    
    for job in jobs:
        if job['url'] in processed_urls:
            print(f"✅ CORRECTLY SKIPPED: {job['title']} (Already Processed)")
        else:
            print(f"🚀 WOULD PROCESS: {job['title']} (New Job Found)")
            # Simulate saving the job after "processing"
            processed_urls.append(job['url'])
            with open(PROCESSED_FILE, 'w') as f:
                json.dump(processed_urls, f)
            print(f"   [Added {job['url']} to processed list]")

if __name__ == "__main__":
    run_test()
    # Cleanup test files after verification
    # os.remove(PROCESSED_FILE)
    # os.remove(JOBS_FILE)
