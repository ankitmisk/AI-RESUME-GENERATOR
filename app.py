import streamlit as st
import os
import io
import re
import base64
import time
from urllib.parse import urlparse
import langchain
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from tavily import TavilyClient
import pytesseract as pyt
import numpy as np
from langchain_core.messages import SystemMessage, HumanMessage
from langchain.agents import create_agent

# =====================================================================
# NEW: page config + light UI/UX polish for the Streamlit app itself
# (Nothing below removes/changes your original logic — it only wraps
#  it and adds the two requested features.)
# =====================================================================
st.set_page_config(page_title="AI Resume Generator", page_icon="🧾", layout="wide")

st.markdown(
    """
    <style>
        .block-container {padding-top: 2rem; padding-bottom: 3rem;}
        .stButton>button {
            border-radius: 10px; padding: 0.6rem 1.2rem; font-weight: 600;
            border: none; background: linear-gradient(90deg,#4f46e5,#7c3aed); color: white;
        }
        .stButton>button:hover {opacity: 0.9;}
        .stDownloadButton>button {
            border-radius: 10px; font-weight: 600; width: 100%;
        }
        .app-subtitle {color:#64748b; margin-top:-10px; margin-bottom:1.2rem;}
        .resume-frame {
            border: 1px solid #e2e8f0; border-radius: 14px; padding: 0px;
            box-shadow: 0 4px 18px rgba(0,0,0,0.06); overflow:hidden;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================FRONTEND==================
st.title("AI RESUME GENERATOR")
st.markdown('<p class="app-subtitle">Generate a polished, dynamic HTML resume with AI — with your photo, in seconds.</p>', unsafe_allow_html=True)

GOOGLE_API_KEY = st.sidebar.text_input("Google Api Key", type='password')
GROQ_API_KEY = st.sidebar.text_input("GROQ Api Key", type='password')
TAVILY_API_KEY = st.sidebar.text_input("TAVILY Api Key", type='password')
if not GOOGLE_API_KEY:
    st.warning("Provide Google API key")

st.sidebar.divider()
st.sidebar.subheader("👤 Profile Photo")

# ---------------------------------------------------------------------
# FEATURE 1: Photo upload -> base64 data URI so it can be embedded
# directly inside the generated HTML resume (no external hosting needed,
# works offline, and survives PDF/DOCX/JPEG export since it's inline).
# ---------------------------------------------------------------------
user_photo = st.sidebar.file_uploader("Upload your photo", type=["jpg", "jpeg", "png"])
photo_data_uri = None
if user_photo is not None:
    photo_bytes = user_photo.getvalue()
    mime = user_photo.type or "image/jpeg"
    photo_data_uri = f"data:{mime};base64,{base64.b64encode(photo_bytes).decode()}"
    st.sidebar.image(photo_bytes, caption="Preview", width=140)

# A neutral silhouette avatar used only if the user doesn't upload a photo,
# so the resume layout never breaks / shows a broken image icon.
_DEFAULT_AVATAR_SVG = """<svg xmlns='http://www.w3.org/2000/svg' width='140' height='140'>
<rect width='100%' height='100%' fill='#e2e8f0'/>
<circle cx='70' cy='52' r='28' fill='#94a3b8'/>
<ellipse cx='70' cy='118' rx='44' ry='34' fill='#94a3b8'/>
</svg>"""
DEFAULT_AVATAR_URI = "data:image/svg+xml;base64," + base64.b64encode(_DEFAULT_AVATAR_SVG.encode()).decode()

# ============= MODEL and AGENT CODE====================
# tool 1
def search_latest_news_jobs(query):
    """This function helps to get
    latest news or latest jobs
    related to user given query
    using tavily"""
    from tavily import TavilyClient
    client = TavilyClient(api_key=TAVILY_API_KEY)
    return client.search(query)


# ---------------------------------------------------------------------
# NEW: dedicated job-search helper (separate from the agent's tool above)
# used to populate the "Latest Jobs" panel under the generated resume.
# ---------------------------------------------------------------------
def fetch_latest_jobs(designation: str, extra_context: str = "", max_results: int = 10):
    """Search Tavily for the latest job openings matching the given
    designation/role (and optional extra context pulled from the resume
    details), returning up to max_results results with title/url/snippet."""
    client = TavilyClient(api_key=TAVILY_API_KEY)
    query = f"latest job openings hiring now for {designation} {extra_context}".strip()
    response = client.search(
        query=query,
        search_depth="advanced",
        max_results=max_results,
        include_answer=False,
    )
    return response.get("results", [])[:max_results]


def _source_domain(url: str) -> str:
    try:
        netloc = urlparse(url).netloc
        return netloc.replace("www.", "") or url
    except Exception:
        return url


# Step 4: Model and Agent creation — created lazily (only once a key is
# present) so the app doesn't crash on load before the sidebar is filled.
def get_models():
    model1 = ChatGoogleGenerativeAI(
        model="gemini-3.5-flash-lite",
        google_api_key=GOOGLE_API_KEY
    )
    model2 = None
    if GROQ_API_KEY:
        model2 = ChatGroq(
            model="qwen/qwen3.6-27b",
            api_key=GROQ_API_KEY
        )
    return model1, model2


def get_agent(model1):
    # ============Agent with tool==============
    return create_agent(
        model=model1,  # can be model2 also,
        tools=[search_latest_news_jobs],
    )


# Let's Generate Prompt for Resume using model
def prompt_generator(model1):
    prompt = """You are a helpful AI Resume
  maker, I want you to use chain-of-thoughts
  and give detailed prompt for model
  where user want to generate resume
  for fresher or experienced one
  in HTML format, you have to give proper
  set of instructions, and make sure to keep
  design professional"""
    response = model1.invoke(prompt)
    try:
        prompt_ans = response.content[-1]['text']
    except (TypeError, KeyError, IndexError):
        prompt_ans = response.content if isinstance(response.content, str) else str(response.content)
    file_name = 'prompt.txt'
    with open(file_name, 'w') as f:
        f.write(prompt_ans)


# Final_Agent
# Tool 2
def prompt_reader():
    with open('prompt.txt', 'r') as f:
        prompt = f.read()
    return prompt


def extract_html(raw_code: str) -> str:
    """Strip markdown code fences (```html ... ```) if the model wraps its output."""
    match = re.search(r"```(?:html)?\s*(.*?)```", raw_code, re.DOTALL)
    return match.group(1).strip() if match else raw_code.strip()


# ---------------------------------------------------------------------
# Footer injected into the generated resume itself (separate from the
# app UI) — subtle, print-safe, and only added once.
# ---------------------------------------------------------------------
def inject_footer(html_code: str) -> str:
    if "ai-resume-footer" in html_code:
        return html_code
    footer_block = """
<style>
.ai-resume-footer{margin-top:32px;padding:14px 24px;text-align:center;
font-size:11px;color:#94a3b8;border-top:1px solid #e2e8f0;font-family:inherit;}
@media print{.ai-resume-footer{page-break-inside:avoid;}}
</style>
<div class="ai-resume-footer">Generated with AI Resume Generator</div>
"""
    if "</body>" in html_code:
        return html_code.replace("</body>", footer_block + "</body>")
    return html_code + footer_block


def inject_photo(html_code: str, data_uri: str) -> str:
    """Replace the placeholder the agent was instructed to leave for the photo."""
    if "{PROFILE_PHOTO_PLACEHOLDER}" in html_code:
        return html_code.replace("{PROFILE_PHOTO_PLACEHOLDER}", data_uri)
    # Fallback: if the model forgot the placeholder entirely, inject a
    # circular avatar image right after <body ...> so the photo still shows.
    if "<body" in html_code and "resume-profile-photo" not in html_code:
        avatar_html = (
            f'<img id="resume-profile-photo" src="{data_uri}" '
            'style="width:130px;height:130px;border-radius:50%;object-fit:cover;'
            'display:block;margin:12px auto;box-shadow:0 2px 10px rgba(0,0,0,0.15);" />'
        )
        return re.sub(r"(<body[^>]*>)", r"\1" + avatar_html, html_code, count=1)
    return html_code


profile_url = "https://s7d1.scene7.com/is/image/wbcollab/India_PM_Narendra_Modi-2?qlt=75&resMode=sharp2"
# Change this when required new resume by user, pass details
user_info = st.text_input("Give your information: ")

# NEW: designation drives both the resume content and the job search below.
designation = st.text_input("Job Designation / Target Role", value="Python Developer")
jobs_count = st.radio("Show top jobs", options=[5, 10], index=0, horizontal=True)

# user_query now instructs the model to leave a clear placeholder for the
# photo instead of trying to pass the raw uploaded file object (which
# can't be interpreted by the LLM as an image).
user_query = f"""Give Resume for {designation}.
    user details : {user_info}
    IMPORTANT PHOTO INSTRUCTION: Include a profile photo <img> tag near the
    top/header of the resume with id="resume-profile-photo" and
    src="{{PROFILE_PHOTO_PLACEHOLDER}}" (use this exact literal placeholder
    text as the src value, do NOT invent a URL). Style it as a circular
    avatar, e.g. width:130px;height:130px;border-radius:50%;object-fit:cover.
    Do not add any footer text yourself, it will be added separately.
    """

if "resume_html" not in st.session_state:
    st.session_state.resume_html = None
if "jobs" not in st.session_state:
    st.session_state.jobs = None

if st.button("Generate Resume"):
    if not GOOGLE_API_KEY:
        st.error("Please provide your Google API key in the sidebar first.")
    else:
        with st.spinner("Agent creating Resume..."):
            model1, model2 = get_models()
            prompt_generator(model1)
            final_prompt = user_query and (open('prompt.txt').read())  # keep prompt.txt flow
            final_prompt = "I want complete Professional\nResume with Dynamic Design using Advanced CSS and JS\nand must show user input details\nSystem instructions: Only Give HTML code as output" + prompt_reader()
            final_query = final_prompt + user_query

            agent = get_agent(model1)
            response = agent.invoke({'messages': [{'role': 'user', "content": final_query}]})
            try:
                code = response['messages'][-1].content[-1]['text']
            except (TypeError, KeyError, IndexError):
                raw = response['messages'][-1].content
                code = raw if isinstance(raw, str) else str(raw)

            code = extract_html(code)
            code = inject_photo(code, photo_data_uri if photo_data_uri else DEFAULT_AVATAR_URI)
            code = inject_footer(code)

            st.session_state.resume_html = code

            # NEW: fetch latest matching jobs for the given designation
            if TAVILY_API_KEY:
                try:
                    with st.spinner("Searching latest job openings..."):
                        st.session_state.jobs = fetch_latest_jobs(
                            designation, extra_context=user_info, max_results=jobs_count
                        )
                except Exception as e:
                    st.session_state.jobs = None
                    st.warning(f"Could not fetch job listings: {e}")
            else:
                st.session_state.jobs = None

        st.success("Resume generated!")

# =====================================================================
# Render resume + FEATURE 2: multi-format downloads (HTML / PDF / DOCX / JPEG)
# =====================================================================
if st.session_state.resume_html:
    code = st.session_state.resume_html

    st.markdown('<div class="resume-frame">', unsafe_allow_html=True)
    st.html(code)
    st.markdown('</div>', unsafe_allow_html=True)

    st.divider()
    st.subheader("⬇️ Download your resume")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.download_button(
            "HTML", data=code.encode("utf-8"),
            file_name="resume.html", mime="text/html", width="stretch",
        )

    with col2:
        if st.button("Prepare PDF", width="stretch"):
            try:
                from weasyprint import HTML
                pdf_bytes = HTML(string=code).write_pdf()
                st.session_state["_pdf_bytes"] = pdf_bytes
            except Exception as e:
                st.error(f"PDF export needs the 'weasyprint' package (pip install weasyprint). Details: {e}")
        if st.session_state.get("_pdf_bytes"):
            st.download_button(
                "Download PDF", data=st.session_state["_pdf_bytes"],
                file_name="resume.pdf", mime="application/pdf", width="stretch",
            )

    with col3:
        if st.button("Prepare DOCX", width="stretch"):
            try:
                from htmldocx import HtmlToDocx
                from docx import Document
                doc = Document()
                HtmlToDocx().add_html_to_document(code, doc)
                buf = io.BytesIO()
                doc.save(buf)
                st.session_state["_docx_bytes"] = buf.getvalue()
            except Exception as e:
                st.error(f"Word export needs 'python-docx' and 'htmldocx' (pip install python-docx htmldocx). Details: {e}")
        if st.session_state.get("_docx_bytes"):
            st.download_button(
                "Download DOCX", data=st.session_state["_docx_bytes"],
                file_name="resume.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                width="stretch",
            )

    with col4:
        if st.button("Prepare JPEG", width="stretch"):
            try:
                import imgkit
                options = {'format': 'jpg', 'encoding': "UTF-8", 'quality': 94}
                st.session_state["_jpg_bytes"] = imgkit.from_string(code, False, options=options)
            except Exception as e:
                st.error(
                    "JPEG export needs 'imgkit' plus the wkhtmltoimage system binary "
                    f"(pip install imgkit, then install wkhtmltopdf/wkhtmltoimage). Details: {e}"
                )
        if st.session_state.get("_jpg_bytes"):
            st.download_button(
                "Download JPEG", data=st.session_state["_jpg_bytes"],
                file_name="resume.jpg", mime="image/jpeg", width="stretch",
            )

    st.caption(
        "Tip: PDF and JPEG exports render the exact same HTML/CSS you see above, "
        "so your theme/colors/fonts are preserved. Word export has more limited "
        "CSS support (a Word-document limitation), so minor styling differences may appear there."
    )

    # ===================================================================
    # NEW: Latest matching jobs (via Tavily) shown below the resume result
    # ===================================================================
    st.divider()
    st.subheader(f"💼 Latest Job Openings — {designation}")

    if not TAVILY_API_KEY:
        st.info("Add your TAVILY API key in the sidebar to see live job listings here.")
    else:
        refresh_col, _ = st.columns([1, 4])
        with refresh_col:
            if st.button("🔄 Refresh Job Search", width="stretch"):
                try:
                    with st.spinner("Searching latest job openings..."):
                        st.session_state.jobs = fetch_latest_jobs(
                            designation, extra_context=user_info, max_results=jobs_count
                        )
                except Exception as e:
                    st.warning(f"Could not fetch job listings: {e}")

        jobs = st.session_state.jobs
        if not jobs:
            st.caption("No job listings fetched yet — click 'Generate Resume' or 'Refresh Job Search'.")
        else:
            for job in jobs[:jobs_count]:
                title = job.get("title", "Untitled listing")
                url = job.get("url", "#")
                snippet = (job.get("content") or "").strip()
                if len(snippet) > 220:
                    snippet = snippet[:220].rsplit(" ", 1)[0] + "..."
                source = _source_domain(url)

                with st.container(border=True):
                    jcol1, jcol2 = st.columns([5, 1])
                    with jcol1:
                        st.markdown(f"**{title}**")
                        if snippet:
                            st.caption(snippet)
                        st.markdown(f"<span style='color:#64748b;font-size:12px;'>Source: {source}</span>", unsafe_allow_html=True)
                    with jcol2:
                        st.link_button("Apply ↗", url, width="stretch")
