"""
frontend.py - Production Streamlit Frontend
AI Project Document Generator Agent
CampusX-style architecture
"""

import streamlit as st
import io
import time
from pathlib import Path
from backend import app, DocumentState

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="DocGen Agent",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────
# CUSTOM CSS — Refined Editorial Dark Theme
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&family=DM+Sans:wght@300;400;500&display=swap');

/* ── Base ── */
html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
    background-color: #0e0e12;
    color: #e8e6df;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: #13131a;
    border-right: 1px solid #2a2a38;
}
[data-testid="stSidebar"] * {
    color: #c8c5bc !important;
}

/* ── Title ── */
.hero-title {
    font-family: 'Playfair Display', serif;
    font-size: 2.8rem;
    font-weight: 900;
    color: #f5f0e8;
    letter-spacing: -0.5px;
    line-height: 1.15;
    margin-bottom: 0.2rem;
}
.hero-sub {
    font-size: 0.95rem;
    color: #7a7870;
    font-weight: 300;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    margin-bottom: 2rem;
}

/* ── Section headers ── */
.section-label {
    font-family: 'Playfair Display', serif;
    font-size: 1.1rem;
    font-weight: 700;
    color: #c8a96e;
    border-bottom: 1px solid #2a2a38;
    padding-bottom: 6px;
    margin-bottom: 16px;
    margin-top: 24px;
    letter-spacing: 0.3px;
}

/* ── Cards ── */
.info-card {
    background: #16161e;
    border: 1px solid #2a2a38;
    border-radius: 8px;
    padding: 16px 20px;
    margin-bottom: 12px;
}

/* ── Path badges ── */
.path-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 500;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}
.path-a { background: #1e3a2a; color: #6fcf97; border: 1px solid #6fcf97; }
.path-b { background: #2a1e38; color: #bb86fc; border: 1px solid #bb86fc; }

/* ── Inputs ── */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stSelectbox"] select,
[data-testid="stTextArea"] textarea {
    background: #1c1c24 !important;
    border: 1px solid #2e2e40 !important;
    color: #e8e6df !important;
    border-radius: 6px !important;
}

/* ── File uploader ── */
[data-testid="stFileUploader"] {
    background: #16161e;
    border: 1.5px dashed #3a3a52;
    border-radius: 8px;
    padding: 8px;
}

/* ── Buttons ── */
.stButton > button {
    background: linear-gradient(135deg, #c8a96e, #e6c97e) !important;
    color: #0e0e12 !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 600 !important;
    border: none !important;
    border-radius: 6px !important;
    padding: 0.6rem 2rem !important;
    font-size: 0.95rem !important;
    letter-spacing: 0.3px !important;
    transition: all 0.2s ease !important;
}
.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 20px rgba(200,169,110,0.3) !important;
}

/* ── Progress log ── */
.log-box {
    background: #0a0a10;
    border: 1px solid #1e1e2e;
    border-radius: 8px;
    padding: 14px 18px;
    font-family: 'DM Mono', monospace;
    font-size: 0.82rem;
    color: #7fffb2;
    max-height: 280px;
    overflow-y: auto;
    line-height: 1.8;
}

/* ── Success box ── */
.success-box {
    background: #0d2318;
    border: 1px solid #27ae60;
    border-radius: 8px;
    padding: 16px 20px;
    color: #6fcf97;
    font-weight: 500;
    margin-top: 16px;
}

/* ── Divider ── */
hr { border-color: #1e1e2e !important; }

/* ── Streamlit radio ── */
.stRadio label { color: #c8c5bc !important; }

/* ── Column layout ── */
.col-divider {
    border-left: 1px solid #1e1e2e;
    height: 100%;
    margin: 0 12px;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# SIDEBAR — API Keys
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔑 API Configuration")
    groq_key = st.text_input(
        "Groq API Key",
        type="password",
        placeholder="gsk_...",
        help="Get free key at console.groq.com"
    )
    unsplash_key = st.text_input(
        "Unsplash Access Key",
        type="password",
        placeholder="Your Unsplash key",
        help="Get free key at unsplash.com/developers"
    )

    st.divider()
    st.markdown("### ⚙️ Generation Settings")
    add_images = st.toggle("Add images per section", value=True)
    model_choice = st.selectbox(
        "Groq Model",
        ["llama-3.3-70b-versatile", "llama3-70b-8192", "mixtral-8x7b-32768"],
        index=0,
        help="70b models give best quality"
    )

    st.divider()
    st.markdown("### 📖 About")
    st.caption(
        "AI-powered academic project document generator. "
        "Uses LangGraph agentic pipeline + RAG to produce "
        "professionally formatted Word documents."
    )
    st.caption("Built with LangGraph · Groq · Streamlit")


# ─────────────────────────────────────────────
# MAIN HEADER
# ─────────────────────────────────────────────
col_title, col_badge = st.columns([3, 1])
with col_title:
    st.markdown('<div class="hero-title">DocGen Agent</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-sub">Agentic AI · Project Document Generator</div>', unsafe_allow_html=True)
with col_badge:
    st.markdown("<br>", unsafe_allow_html=True)
    st.caption("🟢 LangGraph Pipeline Active")

st.divider()

# ─────────────────────────────────────────────
# PATH SELECTION
# ─────────────────────────────────────────────
st.markdown('<div class="section-label">STEP 1 — Document Source</div>', unsafe_allow_html=True)

path_col1, path_col2 = st.columns(2)
with path_col1:
    st.markdown('<span class="path-badge path-a">PATH A</span>', unsafe_allow_html=True)
    st.markdown("**Have a reference document?**  \nAgent will extract structure, fonts, margins and replicate the format exactly.")
with path_col2:
    st.markdown('<span class="path-badge path-b">PATH B</span>', unsafe_allow_html=True)
    st.markdown("**No reference?**  \nAgent will ask you for every formatting detail — font, size, margins, spacing, sections.")

has_reference = st.radio(
    "Choose your path",
    options=["Yes, I have a reference document (Path A)", "No reference, I'll specify details (Path B)"],
    index=0,
    label_visibility="collapsed"
)
is_path_a = "Path A" in has_reference

st.divider()

# ─────────────────────────────────────────────
# PATH A — Reference Upload
# ─────────────────────────────────────────────
reference_file = None
if is_path_a:
    st.markdown('<div class="section-label">STEP 2A — Upload Reference Document</div>', unsafe_allow_html=True)
    st.markdown('<div class="info-card">Upload a PDF or DOCX that has the exact format/structure you want. The agent will extract headings, fonts, margins and replicate it.</div>', unsafe_allow_html=True)
    reference_file = st.file_uploader(
        "Reference Document (PDF or DOCX)",
        type=["pdf", "docx"],
        key="ref_upload",
        label_visibility="collapsed"
    )
    if reference_file:
        st.success(f"✅ Reference loaded: `{reference_file.name}` ({reference_file.size // 1024} KB)")

# ─────────────────────────────────────────────
# PATH B — Manual Formatting Details
# ─────────────────────────────────────────────
manual_details = {}
if not is_path_a:
    st.markdown('<div class="section-label">STEP 2B — Document Formatting Details</div>', unsafe_allow_html=True)

    with st.expander("📐 Page & Font Setup", expanded=True):
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            manual_details["body_font_name"] = st.selectbox(
                "Body Font",
                ["Times New Roman", "Arial", "Calibri", "Georgia", "Garamond"],
                index=0
            )
        with fc2:
            manual_details["body_font_size"] = st.number_input("Body Font Size (pt)", min_value=8, max_value=16, value=12)
        with fc3:
            manual_details["line_spacing"] = st.selectbox("Line Spacing", [1.0, 1.15, 1.5, 2.0], index=2)

        hc1, hc2, hc3 = st.columns(3)
        with hc1:
            manual_details["heading1_font_size"] = st.number_input("Heading 1 Size (pt)", min_value=12, max_value=24, value=16)
        with hc2:
            manual_details["heading2_font_size"] = st.number_input("Heading 2 Size (pt)", min_value=10, max_value=20, value=14)
        with hc3:
            manual_details["heading3_font_size"] = st.number_input("Heading 3 Size (pt)", min_value=10, max_value=18, value=12)

    with st.expander("📏 Margins (inches)", expanded=True):
        mc1, mc2, mc3, mc4 = st.columns(4)
        with mc1:
            manual_details["margin_top"]    = st.number_input("Top", min_value=0.5, max_value=3.0, value=1.0, step=0.25)
        with mc2:
            manual_details["margin_bottom"] = st.number_input("Bottom", min_value=0.5, max_value=3.0, value=1.0, step=0.25)
        with mc3:
            manual_details["margin_left"]   = st.number_input("Left", min_value=0.5, max_value=3.0, value=1.25, step=0.25)
        with mc4:
            manual_details["margin_right"]  = st.number_input("Right", min_value=0.5, max_value=3.0, value=1.0, step=0.25)

    with st.expander("📑 Document Sections", expanded=True):
        st.markdown("Select sections to include in your document:")
        default_sections = [
            "Abstract", "Introduction", "Literature Review",
            "System Architecture", "Methodology", "Implementation",
            "Results and Discussion", "Conclusion", "Future Scope", "References"
        ]
        selected_sections = []
        cols_sec = st.columns(2)
        for i, sec in enumerate(default_sections):
            with cols_sec[i % 2]:
                if st.checkbox(sec, value=sec in ["Abstract", "Introduction", "Methodology", "Results and Discussion", "Conclusion", "References"]):
                    selected_sections.append(sec)
        
        custom_section = st.text_input("Add custom section (optional)", placeholder="e.g., Hardware Requirements")
        if custom_section.strip():
            selected_sections.append(custom_section.strip())

        manual_details["sections"] = selected_sections

st.divider()

# ─────────────────────────────────────────────
# COMMON — Project Details
# ─────────────────────────────────────────────
st.markdown('<div class="section-label">STEP 3 — Project Information</div>', unsafe_allow_html=True)

pi_col1, pi_col2 = st.columns(2)
with pi_col1:
    manual_details["project_title"]  = st.text_input("Project Title *", placeholder="e.g. Smart Attendance System using Face Recognition")
    manual_details["college_name"]   = st.text_input("College / University Name", placeholder="e.g. JNTU Hyderabad")
    manual_details["department"]     = st.text_input("Department", placeholder="e.g. Computer Science & Engineering")
    manual_details["project_domain"] = st.text_input("Project Domain / Subject", placeholder="e.g. Machine Learning, Web Development")

with pi_col2:
    manual_details["student_name"]   = st.text_input("Student Name(s)", placeholder="e.g. Varun Kumar")
    manual_details["roll_number"]    = st.text_input("Roll Number", placeholder="e.g. 21BD1A0542")
    manual_details["guide_name"]     = st.text_input("Project Guide Name", placeholder="e.g. Dr. Ravi Shankar")
    manual_details["academic_year"]  = st.text_input("Academic Year", value="2024-25")

st.divider()

# ─────────────────────────────────────────────
# CONTENT NOTES UPLOAD
# ─────────────────────────────────────────────
st.markdown('<div class="section-label">STEP 4 — Upload Your Content Notes (Optional but Recommended)</div>', unsafe_allow_html=True)
st.markdown('<div class="info-card">Upload your rough notes, syllabus PDFs, previous reports, or any reference material. The RAG pipeline will extract relevant content for each section automatically.</div>', unsafe_allow_html=True)

content_files = st.file_uploader(
    "Content notes (PDF, DOCX, or TXT) — multiple files allowed",
    type=["pdf", "docx", "txt"],
    accept_multiple_files=True,
    key="content_upload",
    label_visibility="collapsed"
)
if content_files:
    st.info(f"📎 {len(content_files)} file(s) uploaded for RAG content extraction")

st.divider()

# ─────────────────────────────────────────────
# GENERATE BUTTON
# ─────────────────────────────────────────────
st.markdown('<div class="section-label">STEP 5 — Generate Document</div>', unsafe_allow_html=True)

gen_col1, gen_col2 = st.columns([2, 3])
with gen_col1:
    generate_btn = st.button("🚀 Generate Project Document", use_container_width=True)

# Validation
if generate_btn:
    errors = []
    if not groq_key:
        errors.append("❌ Groq API Key is required (add in sidebar)")
    if add_images and not unsplash_key:
        errors.append("⚠️ Unsplash key missing — images will be skipped")
    if not manual_details.get("project_title"):
        errors.append("❌ Project Title is required (Step 3)")
    if is_path_a and not reference_file:
        errors.append("❌ Please upload a reference document (Path A selected)")
    if not is_path_a and not manual_details.get("sections"):
        errors.append("❌ Please select at least one section (Step 2B)")

    hard_errors = [e for e in errors if e.startswith("❌")]
    soft_warns  = [e for e in errors if e.startswith("⚠️")]

    for w in soft_warns:
        st.warning(w)
    for e in hard_errors:
        st.error(e)

    if not hard_errors:
        # ── BUILD STATE ──
        content_bytes_list = []
        content_types_list = []
        if content_files:
            for cf in content_files:
                content_bytes_list.append(cf.read())
                ext = cf.name.split(".")[-1].lower()
                content_types_list.append(ext)

        ref_bytes = None
        ref_type  = None
        if is_path_a and reference_file:
            ref_bytes = reference_file.read()
            ref_type  = reference_file.name.split(".")[-1].lower()

        initial_state: DocumentState = {
            "has_reference":           is_path_a,
            "path_decided":            True,
            "reference_file_bytes":    ref_bytes,
            "reference_file_type":     ref_type,
            "reference_structure":     None,
            "manual_details":          manual_details,
            "content_file_bytes_list": content_bytes_list,
            "content_file_types":      content_types_list,
            "rag_chunks":              [],
            "vectorstore_ready":       False,
            "doc_outline":             None,
            "current_section_index":   0,
            "section_contents":        {},
            "add_images":              add_images and bool(unsplash_key),
            "unsplash_access_key":     unsplash_key if add_images else None,
            "section_images":          {},
            "docx_bytes":              None,
            "error_message":           None,
            "status_log":              ["🚀 Agent pipeline started..."],
            "groq_api_key":            groq_key,
        }

        # ── LIVE PROGRESS ──
        st.markdown("---")
        st.markdown("**⚡ Agent Progress Log**")
        log_placeholder = st.empty()
        progress_bar    = st.progress(0)

        def render_log(logs):
            log_html = "<div class='log-box'>" + "<br>".join(logs) + "</div>"
            log_placeholder.markdown(log_html, unsafe_allow_html=True)

        render_log(initial_state["status_log"])

        # ── RUN GRAPH ──
        try:
            final_state = None
            step_count  = 0
            total_steps = len(manual_details.get("sections") or ["Abstract","Intro","Methodology","Results","Conclusion","References"]) + 4

            for step_output in app.stream(initial_state):
                step_count += 1
                for node_name, node_state in step_output.items():
                    if isinstance(node_state, dict):
                        logs = node_state.get("status_log", [])
                        render_log(logs)
                        final_state = node_state
                progress_bar.progress(min(step_count / total_steps, 0.95))
                time.sleep(0.1)

            progress_bar.progress(1.0)

            if final_state and final_state.get("docx_bytes"):
                docx_bytes = final_state["docx_bytes"]
                fname = f"{manual_details['project_title'].replace(' ', '_')}_ProjectReport.docx"

                st.markdown("""
                <div class="success-box">
                    ✅ Document generated successfully! Click below to download.
                </div>
                """, unsafe_allow_html=True)

                st.download_button(
                    label="⬇️ Download Project Document (.docx)",
                    data=docx_bytes,
                    file_name=fname,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True
                )

                # Stats
                sc1, sc2, sc3 = st.columns(3)
                sections_done = len(final_state.get("section_contents") or {})
                images_added  = len(final_state.get("section_images") or {})
                doc_size_kb   = len(docx_bytes) // 1024
                with sc1: st.metric("Sections Generated", sections_done)
                with sc2: st.metric("Images Inserted", images_added)
                with sc3: st.metric("Document Size", f"{doc_size_kb} KB")

            else:
                st.error("❌ Document generation failed. Check your API keys and try again.")

        except Exception as e:
            st.error(f"❌ Pipeline error: {str(e)}")
            st.exception(e)
