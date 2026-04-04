import json
import os
import subprocess
import re
from dotenv import load_dotenv
import jinja2
from openai import OpenAI
from data import RESUME_DATA

# Initialize client and force .env override
load_dotenv(override=True)
client = OpenAI()

def get_tailored_content(job_desc):
    with open("persona.txt", "r") as f:
        my_voice_examples = f.read()

    prompt = f"""
    You are Bradley Schmidt, an engineering student. 
    
    JOB DESCRIPTION:
    {job_desc}

    YOUR MASTER DATABASE:
    {json.dumps(RESUME_DATA, indent=2)}

    TASKS:
    1. Read the Job Description and identify the core technical requirements.
    2. Curate a "Technical Skills" dictionary. Select the 10-15 most relevant skills from 'master_skills' and group them into 3 to 4 logical categories (e.g., "Languages", "Core", "Hardware", "Tools").
    3. Select 3 to 4 of the most relevant projects.
    4. PAGE LENGTH BUDGET: You have a strict budget of EXACTLY 14 to 16 bullet points total to distribute across your Projects and Experience. 
       - If you select 4 projects, write fewer bullets per project (2-3).
       - If you select 3 projects, write more bullets per project (3-4).
       - Base all bullets ONLY on the 'master_facts'. Tailor keywords to the job description.
    5. Write a 3-sentence summary for the top of the resume.
    6. Draft a casual, high-impact cover letter mimicking this tone: {my_voice_examples}

    OUTPUT INSTRUCTIONS:
    Return ONLY a raw JSON object with EXACTLY these keys:
    "summary" (string),
    "skills" (A JSON object where keys are the category names and values are comma-separated strings of skills. Example: {{ "Languages": "C++, Rust", "Hardware": "ESP32, PCB Design" }}),
    "cover_letter" (string),
    "tailored_projects" (Array of 3-4 objects, each with "title" (string), "tech" (string), and "bullets" (array of strings)),
    "tailored_experience" (Array of 2 objects, each with "company" (string), "role" (string), "dates" (string), and "bullets" (array of strings))
    """

    # Using the gpt-5.4 responses syntax
    response = client.responses.create(
        model="gpt-5.4",
        input=prompt
    )
    
    raw_output = response.output_text.strip()
    
    # Robustly extract JSON in case the AI wraps it in markdown blocks
    match = re.search(r'\{.*\}', raw_output, re.DOTALL)
    if match:
        raw_output = match.group(0)
        
    try:
        return json.loads(raw_output)
    except Exception as e:
        print(f"Failed to parse JSON. Raw output was:\n{raw_output}")
        raise e

def escape_for_latex(text):
    """Automatically escapes %, &, #, $, and _ if they aren't already escaped."""
    if not isinstance(text, str): 
        return text
    text = re.sub(r'(?<!\\)&', r'\\&', text)
    text = re.sub(r'(?<!\\)%', r'\\%', text)
    text = re.sub(r'(?<!\\)\$', r'\\$', text)
    text = re.sub(r'(?<!\\)#', r'\\#', text)
    text = re.sub(r'(?<!\\)_', r'\\_', text)
    return text

def sanitize_context(data, is_root=True):
    """Recursively cleans text, escaping inner keys but leaving root keys alone for Jinja."""
    if isinstance(data, dict):
        if is_root:
            # Leave top-level keys (like 'selected_projects') alone so Jinja can find them
            return {k: sanitize_context(v, is_root=False) for k, v in data.items()}
        else:
            # Safely escape nested keys (like 'Frontend & Mobile') that actually print to the PDF
            return {escape_for_latex(k) if isinstance(k, str) else k: sanitize_context(v, is_root=False) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_context(v, is_root=False) for v in data]
    elif isinstance(data, str):
        return escape_for_latex(data)
    return data

def compile_latex(template_path, output_name, context):
    # Configure Jinja2 to use LaTeX-safe delimiters to stop LunarVim from crashing
    latex_env = jinja2.Environment(
        block_start_string='((*',
        block_end_string='*))',
        variable_start_string='(((',
        variable_end_string=')))',
        comment_start_string='((=',
        comment_end_string='=))',
        trim_blocks=True,
        autoescape=False,
        loader=jinja2.FileSystemLoader(os.path.abspath('.'))
    )
    
    template = latex_env.get_template(template_path)
    rendered_tex = template.render(context)
    
    tex_file = f"{output_name}.tex"
    with open(tex_file, 'w') as f:
        f.write(rendered_tex)
    
    try:
        subprocess.run(['pdflatex', '-interaction=nonstopmode', tex_file], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"   [✓] SUCCESS: Generated {output_name}.pdf")
    except subprocess.CalledProcessError:
        print(f"   [!] ERROR: LaTeX compilation failed for {tex_file}.")

def run_sniper(job_index):
    with open("jobs_with_descriptions.json", "r") as f:
        jobs = json.load(f)
    
    job = jobs[job_index]
    print(f"Sniper engaged: Tailoring for {job['title']} at {job['company']}...")
    
    # Get AI decision
    decision = get_tailored_content(job['full_description'])
    
    # Check if the AI followed instructions for the tailored structures
    if 'tailored_projects' not in decision:
        print("   [!] ERROR: AI failed to generate 'tailored_projects'. Check your prompt format.")
        return
        
    # Prepare LaTeX context directly from the AI's generated bullets
    context = {
        "summary": decision.get('summary', ''),
        "skills": decision.get('skills', {}), # Use {} fallback for dicts
        "selected_projects": decision.get('tailored_projects', decision.get('projects', [])),
        "experience": decision.get('tailored_experience', decision.get('experience', []))
    }

    # Clean the context to prevent LaTeX crashing on special characters
    context = sanitize_context(context)
    
    # Format the output filename nicely
    file_label = job['company'].split()[0].replace(",", "").replace(".", "")
    
    # Print the PDF
    compile_latex("template.tex", f"Resume_Schmidt_{file_label}", context)
    
    # Save the Cover Letter for manual review
    with open(f"CL_Schmidt_{file_label}.txt", "w") as f:
        f.write(decision.get('cover_letter', ''))
    print(f"   [✓] SUCCESS: Cover letter saved to CL_Schmidt_{file_label}.txt")
    print("\nReview the .txt file and the PDF. If they look good, you are ready to apply.")

if __name__ == "__main__":
    # Test on the first job (e.g., BenchSci)
    run_sniper(0)
