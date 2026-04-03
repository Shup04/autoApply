import json
import os
import subprocess
from dotenv import load_dotenv
import jinja2
from openai import OpenAI
from data import RESUME_DATA
import re

# Initialize client and force .env override
load_dotenv(override=True)
client = OpenAI()

def get_tailored_content(job_desc):
    with open("persona.txt", "r") as f:
        my_voice_examples = f.read()

    prompt = f"""
    You are Bradley Schmidt. 
    STYLE GUIDE:
    Reference these past cover letters for tone (casual, direct, "fix it when it breaks"). 
    EXAMPLES: {my_voice_examples}

    TASKS:
    1. Select exactly 3 project IDs from: {[p['id'] for p in RESUME_DATA['projects']]}
    2. Write a 3-sentence summary.
    3. Draft a casual, high-impact cover letter.

    JOB DESCRIPTION:
    {job_desc}

    OUTPUT INSTRUCTIONS:
    Return a valid JSON object with EXACTLY these keys: "project_ids", "summary", "cover_letter"
    """

    # Using standard chat completions with JSON mode guarantees a valid dictionary
    response = client.chat.completions.create(
        model="gpt-4o",
        response_format={ "type": "json_object" },
        messages=[
            {"role": "system", "content": "You are a helpful assistant designed to output JSON."},
            {"role": "user", "content": prompt}
        ]
    )
    
    raw_output = response.choices[0].message.content
    try:
        return json.loads(raw_output)
    except Exception as e:
        print(f"Failed to parse JSON. Raw output was: {raw_output}")
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

def sanitize_context(data):
    """Recursively cleans all text in the context dictionary."""
    if isinstance(data, dict):
        return {k: sanitize_context(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_context(v) for v in data]
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
    
    # Use .get() to avoid KeyError
    proj_ids = decision.get('project_ids', [])
    if not proj_ids:
        print("   [!] Warning: AI didn't return project_ids. Using default first 3.")
        proj_ids = [p['id'] for p in RESUME_DATA['projects'][:3]]

    selected_projects = [p for p in RESUME_DATA['projects'] if p['id'] in proj_ids]
    
    # Prepare LaTeX context
    context = {
        "summary": decision.get('summary', ''),
        "selected_projects": selected_projects,
        "experience": RESUME_DATA['experience']
    }

    # --- ADD THIS LINE TO FIX ALL COMPILATION CRASHES ---
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
