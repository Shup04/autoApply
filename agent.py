import json
import os
import subprocess
import sys
import re
import shutil
from dotenv import load_dotenv
import jinja2
from openai import OpenAI
from data import RESUME_DATA
from utils import build_job_artifact_label

RESUME_DIR = "resumes"
CL_DIR = "cover_letters"
BUILD_DIR = "build"

for folder in [RESUME_DIR, CL_DIR, BUILD_DIR]:
    os.makedirs(folder, exist_ok=True)

# Initialize client and force .env override
load_dotenv(override=True)
client = OpenAI()

def get_tailored_content(job_desc):
    with open("persona.txt", "r") as f:
        my_voice_examples = f.read()

    resume_schema = {
        "type": "object",
        "properties": {
            "scratchpad": {"type": "string"},
            "summary": {"type": "string"},
            "skills": {
                "type": "object",
                "additionalProperties": {"type": "string"}
            },
            "cover_letter": {"type": "string"},
            "tailored_projects": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "tech": {"type": "string"},
                        "bullets": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["title", "tech", "bullets"],
                    "additionalProperties": False
                }
            },
            "tailored_experience": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "company": {"type": "string"},
                        "role": {"type": "string"},
                        "dates": {"type": "string"},
                        "bullets": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["company", "role", "dates", "bullets"],
                    "additionalProperties": False
                }
            }
        },
        "required": [
            "scratchpad",
            "summary",
            "skills",
            "cover_letter",
            "tailored_projects",
            "tailored_experience"
        ],
        "additionalProperties": False
    }

    prompt = f"""
    You are an Bradley Schmidt, an ambitious software engineering student and electrical apprentice applying for top-tier software engineering and electrical engineering roles.

    JOB DESCRIPTION:
    {job_desc}

    YOUR MASTER DATABASE:
    {json.dumps(RESUME_DATA, indent=2)}

    VOICE & STYLE REFERENCE (MIMIC THIS TONE):
    {my_voice_examples}

    IMPORTANT TARGETING RULES:
    This resume is being judged not only on keyword match, but on alignment with the company's operating philosophy and mission.
    You must optimize for:
    1. mission alignment
    2. operating-style alignment
    3. ATS cleanliness
    4. internal consistency
    5. recruiter readability

    TASKS:
    1. COMPANY IDEOLOGY ANALYSIS:
       Before writing anything, infer the company's core ideology from the job description and company context.
       Explicitly identify:
       - mission
       - operating style
       - preferred engineering traits
       - likely values signaled by their language
       Then map Bradley's strongest evidence to those traits.

    2. BENCHSCI-STYLE FIT RUBRIC:
       Score each possible project/experience item from 1-5 on:
       - mission relevance
       - AI / data / experimentation relevance
       - measurable impact
       - speed / iteration / ownership
       - transparency / collaboration
       Choose bullets and projects with the highest total score, not just the most impressive-sounding items.

    3. TECHNICAL SKILLS RULES:
       - Output skills only as normal resume text, never as JSON-looking arrays, brackets, quotes, or code-like syntax.
       - Every skill listed must either appear in a bullet OR be directly relevant to the target role.
       - If a technology appears in a selected bullet and is important enough to strengthen fit, include it in Technical Skills.
       - Never omit an important technology from Skills if it is featured prominently in Projects or Experience.
       - Prefer 10-15 skills total, grouped into 3-4 clean recruiter-friendly categories.

    4. PROJECT SELECTION RULES:
       Prefer projects that signal:
       - AI-enabled product thinking
       - data quality / validation / experimentation
       - scientific or research-adjacent rigor
       - measurable performance improvements
       - ability to work through ambiguity and iterate quickly
       - practical tools that augment users rather than replace them
       If two projects are similarly strong, prefer the one that sounds more relevant to helping experts make better decisions.

    5. SUMMARY RULES:
       - Write in third-person resume style only. Never use I, me, my, we, our.
       - Do not start with generic phrases like "hands-on experience" unless unavoidable.
       - Sentence 1 must define Bradley's strongest professional identity in a way that matches the target company's mission and engineering style.
       - Sentence 2 must prove that identity using AI, experimentation, validation, iteration, or measurable impact.
       - Sentence 3 must exactly state: "Actively seeking an 8-month software engineering co-op starting [Insert Logical Start Date based on job posting]."
       - The summary must sound like a high-agency builder, not a passive student.

    6. BULLET POINT ENGINEERING:
       - Write exactly 3 bullets per project and exactly 2 bullets per experience role.
       - Base all bullets ONLY on master_facts. Never invent new facts, domain experience, or outcomes.
       - Every bullet must start with a strong past-tense action verb.
       - Every bullet must show one of these patterns:
         a) built / improved / validated something useful
         b) reduced friction, time, or uncertainty
         c) improved quality, speed, reliability, or decision-making
         d) collaborated clearly and proactively in ambiguous work
       - Prefer bullets that imply Focus, Speed, Tenacity, Transparency, experimentation, accountability, and practical impact.
       - Avoid empty claims like "demonstrating strong problem solving" unless the bullet already proves it concretely.
       - Avoid vague filler like "hands-on", "helped with", "responsible for", "worked on", "supported" unless no stronger truthful verb exists.
       - Do not use the exact phrase "as measured by".
       - Use metrics naturally, but only when they materially strengthen the point.
       - At least 2 bullets across the whole resume must signal validation, testing, or evidence quality.
       - At least 2 bullets across the whole resume must signal speed, iteration, or performance improvement.
       - At least 1 bullet must signal proactive communication, collaboration, or transparency.

    7. MISSION-FIT FRAMING:
       For science, AI, data, or research companies, frame relevant facts around:
       - helping experts make better decisions
       - improving evidence quality
       - accelerating useful work
       - translating ambiguity into working systems
       - validating outputs rather than just shipping features
       Do not fake domain expertise, but maximize adjacency to the company's mission.

    8. FINAL QUALITY GATE:
       Before returning JSON, silently check all of the following:
       - no first-person pronouns anywhere
       - no bracketed or code-like formatting in skills
       - no contradiction between skills and bullet technologies
       - no duplicate ideas across bullets
       - no generic summary language if sharper language is possible
       - strongest mission-aligned material appears earliest
       - strongest quantified bullet appears in the top half of the resume
       - resume sounds like one coherent person, not stitched-together fragments

    9. SCRATCHPAD REQUIREMENT:
       In the "scratchpad" field, include:
       - the inferred company ideology
       - the selected evidence map
       - why each chosen project was selected
       - the final self-audit results from the quality gate

    10. COVER LETTER:
        - Write this in the FIRST PERSON (I, me, my).
        - Use the provided VOICE & STYLE REFERENCE as the primary guide for sentence structure, pacing, and word choice.
        - Keep it between 120 and 240 words.
        - Tone: Professional "Builder" (no fluff, high signal).
        - Content: Mention I'm a 4th-year Software Engineering student and an Electrical Apprentice. Focus on my obsession with building tools that solve expert-level problems (like the Ray Tracing performance or the data pipelines).
        - Closing: State I'm looking for a coop of whichever length the job posting is for (4-month, 8-month, etc.)

    OUTPUT INSTRUCTIONS:
    Return ONLY a raw JSON object with EXACTLY these keys:
    "scratchpad" (string),
    "summary" (string),
    "skills" (A JSON object where keys are category names and values are single strings of comma-separated skills. Example: {{ "Languages": "C++, Rust", "Hardware": "ESP32, PCB Design" }}),
    "cover_letter" (string),
    "tailored_projects" (array of 3 objects, each with "title" (string), "tech" (string), and "bullets" (array of strings)),
    "tailored_experience" (array of 2 objects, each with "company" (string), "role" (string), "dates" (string), and "bullets" (array of strings))
    """

    # Using the gpt-5.4 responses syntax
    response = client.responses.create(
        model="gpt-5.4",
        input=prompt,
        reasoning={"effort": "medium"}
    )
    
    raw_output = response.output_text.strip()
    
    # Robustly extract JSON in case the AI wraps it in markdown blocks
    match = re.search(r'\{.*\}', raw_output, re.DOTALL)
    if match:
        raw_output = match.group(0)
        
    try:
        return json.loads(raw_output)
    except Exception as e:
        repaired_output = raw_output.replace('\\"', '"')
        try:
            return json.loads(repaired_output)
        except Exception:
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
    
    tex_file_path = os.path.join(BUILD_DIR, f"{output_name}.tex")
    with open(tex_file_path, 'w') as f:
        f.write(template.render(context))
    
    try:
        # Use -output-directory to dump all the .aux, .log, .out files into build/
        subprocess.run([
            'pdflatex', 
            '-interaction=nonstopmode', 
            f'-output-directory={BUILD_DIR}', 
            tex_file_path
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Move ONLY the finished PDF to the resumes folder
        src_pdf = os.path.join(BUILD_DIR, f"{output_name}.pdf")
        dst_pdf = os.path.join(RESUME_DIR, f"{output_name}.pdf")
        shutil.move(src_pdf, dst_pdf)
        
        print(f"    [✓] SUCCESS: Generated {dst_pdf}")
    except Exception as e:
        print(f"    [!] ERROR: LaTeX failed: {e}")


def escape_cover_letter_for_latex(text):
    text = text.replace("\\n", "\n")
    paragraphs = [paragraph.strip() for paragraph in text.splitlines() if paragraph.strip()]
    escaped = [escape_for_latex(paragraph).replace("\n", " ") for paragraph in paragraphs]
    return "\n\n".join(escaped)


def compile_cover_letter_pdf(output_name, company, job_title, cover_letter_text):
    latex_content = rf"""\documentclass[11pt]{{article}}
\usepackage[margin=1in]{{geometry}}
\usepackage[T1]{{fontenc}}
\usepackage[utf8]{{inputenc}}
\usepackage{{lmodern}}
\usepackage{{parskip}}
\pagestyle{{empty}}
\begin{{document}}
\textbf{{Bradley Schmidt}}\\
\vspace{{0.5em}}
\textbf{{{escape_for_latex(company)}}}\\
\textit{{{escape_for_latex(job_title)}}}

{escape_cover_letter_for_latex(cover_letter_text).replace("\n\n", "\n\n\\par\n\n")}
\end{{document}}
"""
    tex_file_path = os.path.join(BUILD_DIR, f"{output_name}.tex")
    pdf_file_path = os.path.join(CL_DIR, f"{output_name}.pdf")

    with open(tex_file_path, "w") as file_handle:
        file_handle.write(latex_content)

    try:
        subprocess.run(
            [
                "pdflatex",
                "-interaction=nonstopmode",
                f"-output-directory={BUILD_DIR}",
                tex_file_path,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        shutil.move(os.path.join(BUILD_DIR, f"{output_name}.pdf"), pdf_file_path)
        print(f"    [✓] SUCCESS: Cover letter PDF saved to {pdf_file_path}")
        return pdf_file_path
    except Exception as exc:
        src_pdf = os.path.join(BUILD_DIR, f"{output_name}.pdf")
        if os.path.exists(src_pdf):
            shutil.move(src_pdf, pdf_file_path)
            print(f"    [!] WARNING: Cover letter PDF saved despite LaTeX warnings: {pdf_file_path}")
            return pdf_file_path
        print(f"    [!] ERROR: Cover letter PDF failed: {exc}")
        return None

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
    file_label = build_job_artifact_label(job["company"], job["title"])
    
    # Print the PDF
    compile_latex("template.tex", f"Resume_Schmidt_{file_label}", context)
    
    # Save the Cover Letter as text and PDF
    cl_filename = f"CL_Schmidt_{file_label}.txt"
    cl_path = os.path.join(CL_DIR, cl_filename)
    with open(cl_path, "w") as f:
        f.write(decision.get('cover_letter', ''))
    print(f"    [✓] SUCCESS: Cover letter saved to {cl_path}")
    compile_cover_letter_pdf(
        f"CL_Schmidt_{file_label}",
        job["company"],
        job["title"],
        decision.get("cover_letter", ""),
    )

if __name__ == "__main__":
    # Check if a URL was passed from main.py
    if len(sys.argv) > 1:
        target_url = sys.argv[1]
        
        # Load the jobs to find the correct index
        with open("jobs_with_descriptions.json", "r") as f:
            jobs = json.load(f)
        
        # Search for the job that matches the URL passed from main.py
        job_index = next((i for i, job in enumerate(jobs) if job['url'] == target_url), None)
        
        if job_index is not None:
            run_sniper(job_index)
        else:
            print(f"❌ Error: Could not find a job in the JSON matching URL: {target_url}")
            sys.exit(1)
    else:
        # Fallback to index 0 if no argument is provided (for manual testing)
        print("⚠️ No URL provided. Defaulting to first job in list...")
        run_sniper(0)
