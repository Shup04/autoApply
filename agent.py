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

    IMPORTANT TARGETING RULE:
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
       Keep it casual and short, but make it sound like someone who builds fast, learns fast, uses AI thoughtfully, and cares about building tools that materially improve expert workflows.

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
