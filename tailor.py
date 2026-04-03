import json
from data import RESUME_DATA

# The "Agent" prompt to ensure it sounds like you
PROMPT_TEMPLATE = """
You are Bradley Schmidt, a 4th-year SWE student at Thompson Rivers University and electrical apprentice.
Tone: Casual, enthusiast, direct, "passionate scientist" attitude.
Avoid corporate buzzwords. Mention your childhood Arduino if it fits.

Job Title: {job_title}
Job Description: {job_desc}

1. Select the top 3 projects from the list below that match the job best.
2. Write a 4-sentence cover letter draft in Bradley's casual voice.
3. Write a 2-sentence "Sniper" email to the recruiter.

Projects List: {projects_list}
"""

def tailor_for_job(job_index):
    with open("jobs_with_descriptions.json", "r") as f:
        jobs = json.load(f)
    
    current_job = jobs[job_index]
    
    # Logic to select projects based on tags (can be done with LLM or simple filtering)
    selected_projects = RESUME_DATA['projects'][:3] # Placeholder for agent logic
    
    # Next: Use OpenAI/Anthropic API to generate the Cover Letter and Email 
    # based on the PROMPT_TEMPLATE above.
    
    return selected_projects, "Draft Cover Letter...", "Draft Email..."
