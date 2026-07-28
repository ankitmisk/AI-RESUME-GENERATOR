# AI Resume Generator

Generate a professional, dynamically-designed HTML resume with AI — complete
with your photo, one-click export to HTML/PDF/DOCX/JPEG, and a live "latest
job openings" panel for your target role.

## Features

- **AI-generated resume** — an agent (Gemini, with optional Groq model and a
  Tavily search tool) writes a full HTML/CSS resume from the details you type in.
- **Your photo, embedded** — upload a photo and it's baked directly into the
  resume as a base64 image, so it survives every export format (no broken
  links, no external hosting needed).
- **Download in 4 formats** — HTML, PDF, DOCX (Word), and JPEG, all rendered
  from the same HTML/CSS so your theme is preserved (Word has some inherent
  CSS limitations — see Notes below).
- **Built-in footer** — a subtle, print-safe footer is added automatically to
  every generated resume.
- **Latest job openings** — using Tavily search, the app pulls the top 5 or
  10 live job listings matching your target designation, each with a title,
  short snippet, source domain, and an "Apply" link.

## Requirements

- Python 3.10+
- API keys:
  - **Google API key** (required) — for the Gemini model that writes the resume.
  - **Groq API key** (optional) — for an alternate model.
  - **Tavily API key** (optional) — enables the "Latest Job Openings" panel and
    the agent's web-search tool.

## Setup

```bash
# 1. Create and activate a virtual environment (recommended)
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install Python dependencies
pip install -r requirements.txt
```

### Extra system dependencies for export features

| Format | Library        | Also needs                                                    |
|--------|----------------|----------------------------------------------------------------|
| PDF    | `weasyprint`   | Linux may need `sudo apt-get install libpango-1.0-0 libpangocairo-1.0-0` |
| DOCX   | `python-docx`, `htmldocx` | nothing extra |
| JPEG   | `imgkit`       | the `wkhtmltoimage` system binary (see below)                 |

**Installing `wkhtmltopdf`/`wkhtmltoimage` (needed for JPEG export):**

- **Linux (Debian/Ubuntu):** `sudo apt-get install wkhtmltopdf`
- **macOS:** `brew install --cask wkhtmltopdf`
- **Windows:** download the installer from https://wkhtmltopdf.org/downloads.html

If a format's library/binary isn't installed, that specific download button
will show a clear on-screen error instead of crashing the app — the other
formats keep working.

## Running the app

```bash
streamlit run app.py
```

Then, in the browser tab that opens:

1. Enter your **Google API key** in the sidebar (required). Add Groq/Tavily
   keys if you want the alternate model or job search.
2. Upload a **profile photo** (optional — a placeholder avatar is used if skipped).
3. Fill in **your information** and your **target job designation**.
4. Click **Generate Resume**.
5. Review the resume, then download it as **HTML / PDF / DOCX / JPEG**.
6. Scroll down to see the **Latest Job Openings** for your designation, with
   direct apply links — use **Refresh Job Search** to re-run the search
   without regenerating the resume.

## Notes

- All exports (PDF/DOCX/JPEG) are generated on demand via "Prepare ..."
  buttons so the app doesn't do unnecessary work until you actually want a
  given format.
- DOCX export has more limited CSS support than PDF/JPEG — this is a
  limitation of the Word format itself, not the exporter.
- The resume, prepared exports, and job results are kept in Streamlit's
  session state so they don't disappear when you click a download button
  (Streamlit reruns the script on every interaction).
