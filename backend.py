"""
backend.py - Production LangGraph Agent for Project Document Generator
Architecture: CampusX-style backend/frontend separation
"""

import os
import io
import re
import json
import base64
import requests
import tempfile
from pathlib import Path
from typing import TypedDict, Optional, Literal, List, Dict, Any

# LangChain / LangGraph
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings

# Document parsing
import fitz  # PyMuPDF
from docx import Document as DocxDocument
from docx.shared import Pt, Inches, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# ─────────────────────────────────────────────
# STATE DEFINITION
# ─────────────────────────────────────────────

class DocumentState(TypedDict):
    # ── Path routing ──
    has_reference: Optional[bool]
    path_decided: bool

    # ── Reference doc path (Path A) ──
    reference_file_bytes: Optional[bytes]
    reference_file_type: Optional[str]          # "pdf" | "docx"
    reference_structure: Optional[Dict]         # extracted formatting blueprint

    # ── Manual details (Path B) ──
    manual_details: Optional[Dict]              # all collected formatting details

    # ── Content notes (both paths) ──
    content_file_bytes_list: Optional[List[bytes]]
    content_file_types: Optional[List[str]]
    rag_chunks: Optional[List[str]]
    vectorstore_ready: bool

    # ── Document outline ──
    doc_outline: Optional[List[str]]            # ordered list of section names
    current_section_index: int
    section_contents: Optional[Dict[str, str]]  # section → generated content

    # ── Image config ──
    add_images: bool
    unsplash_access_key: Optional[str]
    section_images: Optional[Dict[str, str]]    # section → image_url

    # ── Final output ──
    docx_bytes: Optional[bytes]
    error_message: Optional[str]
    status_log: List[str]                       # real-time progress messages

    # ── LLM config ──
    groq_api_key: Optional[str]


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def get_llm(api_key: str, model: str = "llama-3.3-70b-versatile"):
    return ChatGroq(api_key=api_key, model=model, temperature=0.3)


def extract_text_from_pdf(file_bytes: bytes) -> str:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text


def extract_text_from_docx(file_bytes: bytes) -> tuple[str, Dict]:
    """Returns (raw_text, formatting_blueprint)"""
    doc = DocxDocument(io.BytesIO(file_bytes))
    
    text_parts = []
    formatting = {
        "body_font_name": "Times New Roman",
        "body_font_size": 12,
        "heading1_font_size": 16,
        "heading2_font_size": 14,
        "heading3_font_size": 12,
        "line_spacing": 1.5,
        "margin_top": 1.0,
        "margin_bottom": 1.0,
        "margin_left": 1.25,
        "margin_right": 1.0,
        "heading_bold": True,
        "body_alignment": "justify",
    }
    
    # Try to extract actual formatting from styles
    try:
        normal_style = doc.styles["Normal"]
        if normal_style.font.name:
            formatting["body_font_name"] = normal_style.font.name
        if normal_style.font.size:
            formatting["body_font_size"] = int(normal_style.font.size.pt)
    except Exception:
        pass

    try:
        h1_style = doc.styles["Heading 1"]
        if h1_style.font.size:
            formatting["heading1_font_size"] = int(h1_style.font.size.pt)
    except Exception:
        pass

    # Extract section names from headings
    sections_found = []
    for para in doc.paragraphs:
        text_parts.append(para.text)
        if para.style.name.startswith("Heading"):
            sections_found.append(para.text.strip())
    
    if sections_found:
        formatting["detected_sections"] = sections_found

    return "\n".join(text_parts), formatting


def fetch_unsplash_image(query: str, access_key: str) -> Optional[str]:
    """Returns image URL or None"""
    try:
        url = "https://api.unsplash.com/search/photos"
        params = {"query": query, "per_page": 1, "orientation": "landscape"}
        headers = {"Authorization": f"Client-ID {access_key}"}
        r = requests.get(url, params=params, headers=headers, timeout=8)
        data = r.json()
        if data.get("results"):
            return data["results"][0]["urls"]["regular"]
    except Exception:
        pass
    return None


def download_image_bytes(url: str) -> Optional[bytes]:
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.content
    except Exception:
        pass
    return None


def set_doc_margins(doc: DocxDocument, top=1.0, bottom=1.0, left=1.25, right=1.0):
    for section in doc.sections:
        section.top_margin = Inches(top)
        section.bottom_margin = Inches(bottom)
        section.left_margin = Inches(left)
        section.right_margin = Inches(right)


def add_page_numbers(doc: DocxDocument):
    """Add page numbers to footer"""
    for section in doc.sections:
        footer = section.footer
        footer_para = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
        footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = footer_para.add_run()
        fldChar1 = OxmlElement('w:fldChar')
        fldChar1.set(qn('w:fldCharType'), 'begin')
        instrText = OxmlElement('w:instrText')
        instrText.set(qn('xml:space'), 'preserve')
        instrText.text = 'PAGE'
        fldChar2 = OxmlElement('w:fldChar')
        fldChar2.set(qn('w:fldCharType'), 'end')
        run._r.append(fldChar1)
        run._r.append(instrText)
        run._r.append(fldChar2)


# ─────────────────────────────────────────────
# LANGGRAPH NODES
# ─────────────────────────────────────────────

def node_extract_reference_structure(state: DocumentState) -> DocumentState:
    """Path A: Extract formatting blueprint from reference document"""
    log = state.get("status_log", [])
    log.append("📄 Analyzing reference document structure...")

    file_bytes = state["reference_file_bytes"]
    file_type = state["reference_file_type"]

    if file_type == "docx":
        raw_text, formatting = extract_text_from_docx(file_bytes)
    else:
        raw_text = extract_text_from_pdf(file_bytes)
        formatting = {
            "body_font_name": "Times New Roman",
            "body_font_size": 12,
            "heading1_font_size": 16,
            "heading2_font_size": 14,
            "heading3_font_size": 12,
            "line_spacing": 1.5,
            "margin_top": 1.0,
            "margin_bottom": 1.0,
            "margin_left": 1.25,
            "margin_right": 1.0,
        }

    # Use LLM to extract section structure from raw text
    llm = get_llm(state["groq_api_key"])
    prompt = f"""You are a document structure analyzer.
Given the following text extracted from a project document reference, identify:
1. All section/chapter headings in order
2. Approximate font and formatting style used

Return ONLY valid JSON like:
{{
  "sections": ["Abstract", "Introduction", "Literature Review", ...],
  "title_page_elements": ["Title", "College Name", "Department", "Date"],
  "has_table_of_contents": true,
  "has_references_section": true
}}

Document text (first 3000 chars):
{raw_text[:3000]}
"""
    resp = llm.invoke([HumanMessage(content=prompt)])
    try:
        json_match = re.search(r'\{.*\}', resp.content, re.DOTALL)
        structure_info = json.loads(json_match.group()) if json_match else {}
    except Exception:
        structure_info = {"sections": ["Abstract", "Introduction", "Methodology", "Results", "Conclusion", "References"]}

    formatting.update(structure_info)
    log.append(f"✅ Detected {len(formatting.get('sections', []))} sections from reference")

    return {**state, "reference_structure": formatting, "status_log": log}


def node_build_rag(state: DocumentState) -> DocumentState:
    """Build FAISS vector store from uploaded content notes"""
    log = state.get("status_log", [])
    log.append("🔍 Building RAG index from your content notes...")

    all_text = ""
    bytes_list = state.get("content_file_bytes_list") or []
    types_list = state.get("content_file_types") or []

    for fb, ft in zip(bytes_list, types_list):
        if ft == "pdf":
            all_text += extract_text_from_pdf(fb) + "\n\n"
        elif ft == "docx":
            text, _ = extract_text_from_docx(fb)
            all_text += text + "\n\n"
        else:
            # plain text
            all_text += fb.decode("utf-8", errors="ignore") + "\n\n"

    if not all_text.strip():
        log.append("⚠️ No content found in uploaded files. Will generate from topic only.")
        return {**state, "rag_chunks": [], "vectorstore_ready": False, "status_log": log}

    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)
    chunks = splitter.split_text(all_text)
    state["rag_chunks"] = chunks
    log.append(f"✅ RAG index built with {len(chunks)} chunks")

    return {**state, "rag_chunks": chunks, "vectorstore_ready": True, "status_log": log}


def node_plan_outline(state: DocumentState) -> DocumentState:
    """Decide final section order based on path"""
    log = state.get("status_log", [])
    log.append("📋 Planning document outline...")

    if state["has_reference"]:
        sections = state["reference_structure"].get(
            "sections",
            ["Abstract", "Introduction", "Literature Review", "Methodology", "Results", "Conclusion", "References"]
        )
    else:
        md = state["manual_details"]
        sections = md.get("sections", ["Abstract", "Introduction", "Methodology", "Results", "Conclusion", "References"])

    log.append(f"📑 Outline: {' → '.join(sections)}")
    return {**state, "doc_outline": sections, "current_section_index": 0, "section_contents": {}, "status_log": log}


def node_generate_section(state: DocumentState) -> DocumentState:
    """Generate content for current section using RAG"""
    log = state.get("status_log", [])
    outline = state["doc_outline"]
    idx = state["current_section_index"]
    section = outline[idx]

    log.append(f"✍️ Writing section: {section} ({idx+1}/{len(outline)})")

    llm = get_llm(state["groq_api_key"])
    rag_chunks = state.get("rag_chunks") or []

    # Get topic from details
    if state["has_reference"]:
        details = state.get("manual_details") or {}
    else:
        details = state.get("manual_details") or {}
    
    project_title = details.get("project_title", "Project")
    project_domain = details.get("project_domain", "Computer Science")

    # RAG context: find relevant chunks
    context = ""
    if rag_chunks:
        # Simple keyword matching for context retrieval
        keywords = section.lower().split()
        relevant = [c for c in rag_chunks if any(kw in c.lower() for kw in keywords)]
        context = "\n\n".join(relevant[:4]) if relevant else "\n\n".join(rag_chunks[:3])

    system_prompt = f"""You are an expert academic technical writer for engineering project reports.
Write a detailed, well-structured section for a {project_domain} project report titled: "{project_title}".

Guidelines:
- Write in formal academic English
- Use specific technical details relevant to the project
- Minimum 250-400 words per section
- Use proper paragraph structure
- Include technical depth appropriate for a final year engineering project
- Do NOT include section headings in your response (they will be added separately)
- Do NOT use markdown formatting like ** or ##
"""

    user_prompt = f"""Write the "{section}" section for the project report.

Project Title: {project_title}
Domain: {project_domain}

Reference content from user's notes:
{context if context else "No notes provided. Generate based on project title and domain."}

Write only the body content of this section. No headings. No bullet points. Only well-structured paragraphs.
"""

    resp = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
    content = resp.content.strip()

    section_contents = state.get("section_contents") or {}
    section_contents[section] = content

    return {
        **state,
        "section_contents": section_contents,
        "current_section_index": idx + 1,
        "status_log": log
    }


def node_fetch_images(state: DocumentState) -> DocumentState:
    """Fetch images from Unsplash per section"""
    log = state.get("status_log", [])

    if not state.get("add_images") or not state.get("unsplash_access_key"):
        log.append("🖼️ Skipping image fetch")
        return {**state, "section_images": {}, "status_log": log}

    log.append("🖼️ Fetching images from Unsplash...")
    outline = state["doc_outline"]
    details = state.get("manual_details") or {}
    project_title = details.get("project_title", "technology")
    section_images = {}

    # Only fetch images for key sections (not abstract/references)
    skip_sections = {"abstract", "references", "bibliography", "acknowledgements", "table of contents"}
    for section in outline:
        if section.lower() in skip_sections:
            continue
        query = f"{project_title} {section} technology"
        url = fetch_unsplash_image(query, state["unsplash_access_key"])
        if url:
            section_images[section] = url
            log.append(f"  ✅ Image found for: {section}")

    return {**state, "section_images": section_images, "status_log": log}


def node_build_docx(state: DocumentState) -> DocumentState:
    """Build the final DOCX with all formatting applied"""
    log = state.get("status_log", [])
    log.append("📝 Assembling final Word document...")

    # Get formatting config
    if state["has_reference"]:
        fmt = state["reference_structure"] or {}
        details = state.get("manual_details") or {}
    else:
        details = state.get("manual_details") or {}
        fmt = details

    # Extract all formatting params with smart defaults
    body_font = fmt.get("body_font_name", details.get("body_font_name", "Times New Roman"))
    body_size = int(fmt.get("body_font_size", details.get("body_font_size", 12)))
    h1_size   = int(fmt.get("heading1_font_size", details.get("heading1_font_size", 16)))
    h2_size   = int(fmt.get("heading2_font_size", details.get("heading2_font_size", 14)))
    h3_size   = int(fmt.get("heading3_font_size", details.get("heading3_font_size", 12)))
    line_sp   = float(fmt.get("line_spacing", details.get("line_spacing", 1.5)))
    m_top     = float(fmt.get("margin_top", details.get("margin_top", 1.0)))
    m_bot     = float(fmt.get("margin_bottom", details.get("margin_bottom", 1.0)))
    m_left    = float(fmt.get("margin_left", details.get("margin_left", 1.25)))
    m_right   = float(fmt.get("margin_right", details.get("margin_right", 1.0)))

    project_title   = details.get("project_title", "Project Report")
    college_name    = details.get("college_name", "")
    department      = details.get("department", "")
    student_name    = details.get("student_name", "")
    roll_number     = details.get("roll_number", "")
    academic_year   = details.get("academic_year", "2024-25")
    guide_name      = details.get("guide_name", "")

    doc = DocxDocument()
    set_doc_margins(doc, m_top, m_bot, m_left, m_right)

    # ── Custom Styles ──
    def apply_run_formatting(run, font_name, font_size, bold=False, color=None):
        run.font.name = font_name
        run.font.size = Pt(font_size)
        run.bold = bold
        if color:
            run.font.color.rgb = RGBColor(*color)

    def add_heading(text, level=1):
        para = doc.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.LEFT
        run = para.add_run(text)
        size = {1: h1_size, 2: h2_size, 3: h3_size}.get(level, h2_size)
        apply_run_formatting(run, body_font, size, bold=True, color=(0, 0, 0))
        para.paragraph_format.space_before = Pt(12)
        para.paragraph_format.space_after = Pt(6)
        return para

    def add_body_para(text, alignment=WD_ALIGN_PARAGRAPH.JUSTIFY):
        para = doc.add_paragraph()
        para.alignment = alignment
        run = para.add_run(text)
        apply_run_formatting(run, body_font, body_size)
        from docx.shared import Pt as DPt
        from docx.oxml.ns import qn as dqn
        pPr = para._p.get_or_add_pPr()
        lsp = OxmlElement('w:jc')
        para.paragraph_format.line_spacing = Pt(body_size * line_sp)
        return para

    # ══════════════════════════════════════════
    # TITLE PAGE
    # ══════════════════════════════════════════
    doc.add_paragraph()
    doc.add_paragraph()

    if college_name:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(college_name.upper())
        apply_run_formatting(r, body_font, h1_size + 2, bold=True)

    if department:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(f"Department of {department}")
        apply_run_formatting(r, body_font, h2_size, bold=False)

    doc.add_paragraph()
    doc.add_paragraph()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("PROJECT REPORT")
    apply_run_formatting(r, body_font, h2_size, bold=True)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("on")
    apply_run_formatting(r, body_font, body_size)

    doc.add_paragraph()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(project_title)
    apply_run_formatting(r, body_font, h1_size + 2, bold=True)

    doc.add_paragraph()
    doc.add_paragraph()

    if student_name:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(f"Submitted by: {student_name}")
        apply_run_formatting(r, body_font, body_size)

    if roll_number:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(f"Roll No: {roll_number}")
        apply_run_formatting(r, body_font, body_size)

    if guide_name:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(f"Under the guidance of: {guide_name}")
        apply_run_formatting(r, body_font, body_size)

    doc.add_paragraph()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f"Academic Year: {academic_year}")
    apply_run_formatting(r, body_font, body_size)

    doc.add_page_break()

    # ══════════════════════════════════════════
    # TABLE OF CONTENTS (placeholder)
    # ══════════════════════════════════════════
    add_heading("TABLE OF CONTENTS", level=1)
    outline = state["doc_outline"]
    for i, section in enumerate(outline, 1):
        p = doc.add_paragraph()
        r = p.add_run(f"{i}. {section}")
        apply_run_formatting(r, body_font, body_size)

    doc.add_page_break()

    # ══════════════════════════════════════════
    # SECTIONS
    # ══════════════════════════════════════════
    section_contents = state.get("section_contents") or {}
    section_images   = state.get("section_images") or {}

    for section_name in outline:
        add_heading(section_name.upper(), level=1)

        content = section_contents.get(section_name, "")
        if content:
            paragraphs = [p.strip() for p in content.split("\n") if p.strip()]
            for para_text in paragraphs:
                add_body_para(para_text)

        # Insert image if available
        img_url = section_images.get(section_name)
        if img_url:
            img_bytes = download_image_bytes(img_url)
            if img_bytes:
                try:
                    img_stream = io.BytesIO(img_bytes)
                    p = doc.add_paragraph()
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    run = p.add_run()
                    run.add_picture(img_stream, width=Inches(5.5))
                    cap = doc.add_paragraph()
                    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    r = cap.add_run(f"Figure: {section_name}")
                    apply_run_formatting(r, body_font, body_size - 1, bold=False)
                    cap.paragraph_format.space_after = Pt(10)
                except Exception:
                    pass

        doc.add_paragraph()  # spacing between sections

    # Add page numbers
    add_page_numbers(doc)

    # Save to bytes
    buf = io.BytesIO()
    doc.save(buf)
    docx_bytes = buf.getvalue()

    log.append("✅ Document built successfully!")
    return {**state, "docx_bytes": docx_bytes, "status_log": log}


# ─────────────────────────────────────────────
# CONDITIONAL EDGES
# ─────────────────────────────────────────────

def route_after_path_decision(state: DocumentState) -> str:
    if state["has_reference"]:
        return "extract_reference_structure"
    else:
        return "build_rag"


def should_continue_generating(state: DocumentState) -> str:
    idx = state["current_section_index"]
    total = len(state["doc_outline"])
    if idx < total:
        return "generate_section"
    else:
        return "fetch_images"


# ─────────────────────────────────────────────
# GRAPH ASSEMBLY
# ─────────────────────────────────────────────

def build_graph():
    g = StateGraph(DocumentState)

    g.add_node("extract_reference_structure", node_extract_reference_structure)
    g.add_node("build_rag",                   node_build_rag)
    g.add_node("plan_outline",                node_plan_outline)
    g.add_node("generate_section",            node_generate_section)
    g.add_node("fetch_images",                node_fetch_images)
    g.add_node("build_docx",                  node_build_docx)

    # Entry point routing
    g.add_conditional_edges(
        "__start__",
        route_after_path_decision,
        {
            "extract_reference_structure": "extract_reference_structure",
            "build_rag": "build_rag",
        }
    )

    g.add_edge("extract_reference_structure", "build_rag")
    g.add_edge("build_rag", "plan_outline")
    g.add_edge("plan_outline", "generate_section")

    g.add_conditional_edges(
        "generate_section",
        should_continue_generating,
        {
            "generate_section": "generate_section",
            "fetch_images":     "fetch_images",
        }
    )

    g.add_edge("fetch_images", "build_docx")
    g.add_edge("build_docx", END)

    return g.compile()


# Compiled graph (imported by frontend)
app = build_graph()
