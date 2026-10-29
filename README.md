# autoApply

A personal software co-op job-search workflow: collect relevant postings, tailor a résumé and cover letter from an existing factual profile, deliver the documents through Telegram, and track what happens next.

Despite the name, this project **prepares applications; it does not submit them**. The user reviews the documents, applies through the employer's process, and records the outcome. A separate outreach command produces an email draft for manual sending.

## The idea

The repeated work is finding suitable roles, deciding which existing projects best support an application, rewriting those details for the posting, and remembering what has already been done. The code connects those steps around one job record.

The tailoring prompt in [agent.py](agent.py) goes beyond matching keywords: it asks for project selection based on the company's mission and engineering style, uses a master factual profile, and takes writing examples from `persona.txt`. It explicitly forbids inventing facts and outcomes. These are instructions to the model, not a guarantee that its output is accurate; document review remains part of the workflow.

The source filters and Telegram ordering reflect a concrete search: software internships/co-ops, with British Columbia prioritized before Alberta and other Canadian locations. The April 2026 history progresses from university-board scraping and document generation to additional sources, deduplication, and status/note management. The final changes preserve whether a job was ever applied to and fix posting URLs in Telegram.

## How it fits together

```text
Job-source adapters -> posting cache -> full descriptions
                                           |
Profile + writing examples -> AI tailoring -> LaTeX PDFs
                                           |
                           Telegram alert + application record
                                           |
                        Human review/application/status updates
```

- [job_sources.py](job_sources.py) provides `company_boards` (configured Lever/Greenhouse boards), `jobbank`, `linkedin` (public listings, without login), and `symplicity` (the configured university board). Search terms, location filters, and limits live here; board selections are in `company_boards.json`.
- [main.py](main.py) runs scraping, description fetching, document generation, notification, and processed-item recording. Title/company fingerprints connect records across these steps.
- [agent.py](agent.py) combines the posting, `data.py`'s `RESUME_DATA`, and `persona.txt`; renders `template.tex` through Jinja2; and invokes `pdflatex`. The configured tailoring model is `gpt-5.4`.
- [telegram_bot.py](telegram_bot.py) is a separate polling process for listing, searching, notes, and status changes. It accepts commands only from the configured chat.
- [manage_jobs.py](manage_jobs.py) provides local summaries, status changes, manual records, and maintenance commands. [outreach.py](outreach.py) saves an AI-generated outreach draft and updates its job record; it does not send email.

## Setup

Run commands from the repository root: document generation uses relative paths. Python 3.10+ is required by the source syntax; there is no dependency manifest or pinned, verified environment. The imported third-party packages are:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install requests python-dotenv openai Jinja2 playwright
python -m playwright install chromium
```

Browser-backed sources also need Chromium's operating-system dependencies. Install a LaTeX distribution with `pdflatex` and the packages named in [template.tex](template.tex), including the FiraSans font package.

Configure these names in the environment or a local `.env` file:

| Name | Used for |
| --- | --- |
| `OPENAI_API_KEY` | Tailoring and optional outreach generation |
| `TELEGRAM_TOKEN` | Telegram bot API |
| `TELEGRAM_CHAT_ID` | Alert destination and permitted command chat |
| `TRU_USERNAME`, `TRU_PASSWORD` | Only the configured Symplicity source |

Search overrides include `LINKEDIN_SEARCH_TERMS`, `LINKEDIN_LOCATIONS`, `JOBBANK_SEARCH_TERMS`, `JOBBANK_PROVINCES`, and the `COMPANY_BOARD_*` settings in `job_sources.py`. List overrides use `|` separators. Check the existing factual profile, voice examples, template/contact details, board configuration, and source filters before adapting this personal workflow. Keep credentials out of Git.

## Running and tracking

```sh
# One live preparation cycle, selecting a source:
python main.py company_boards

# All registered sources, including Symplicity:
python main.py

# Separate Telegram polling process:
python telegram_bot.py

# Local overview of tracked applications:
python manage_jobs.py summary
```

Source arguments select scraping/enrichment work. They do **not** isolate document generation to that source: `main.py` still considers unprocessed jobs in the combined description cache.

Useful Telegram commands include `/list prepared bc`, `/show 12`, `/note 12 Follow up next week`, `/applied 12`, and `/summary`; substitute an actual tracked ID. Prepared, applied, interview, rejected, offer, and archived are distinct states. Hiding a record also attempts to delete its stored Telegram messages.

Live cycles fetch external listings, send the profile/writing examples and posting text to OpenAI, incur model usage, and send documents to Telegram. They update `scraped_jobs.json`, `jobs_with_descriptions.json`, `processed_jobs.json`, and `application_status.json`. The bot keeps polling state in `telegram_bot_state.json`; generated files live in `resumes/`, `cover_letters/`, and `build/`. Preserve existing state and artifacts before restarting or using maintenance/reset commands.

## Current limits

PDF errors can currently be caught inside `agent.py` without failing the outer cycle. `main.py` may then mark the job prepared/processed, while the notifier skips missing attachments. Verify the actual PDFs; fix that success/failure boundary before relying on unattended preparation.

The worker and bot also rewrite shared JSON without locking, so simultaneous updates can overwrite one another. Existing data loss has not been established. Current provider compatibility, browser selectors, and end-to-end PDF generation were not freshly exercised for this documentation update; the commands above describe the implemented entry points.
