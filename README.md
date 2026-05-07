# 📄 DocGen Agent — AI Project Document Generator

An agentic AI app that generates fully formatted academic project documents using **LangGraph + RAG + Groq + Streamlit**.

---

## 🚀 Deploy on Streamlit Cloud (10 minutes)

### Step 1 — Create GitHub repo
1. Go to github.com → New Repository
2. Name it `docgen-agent` → Create

### Step 2 — Upload files
Upload these files to your repo:
```
docgen-agent/
├── frontend.py          ← main app
├── backend.py           ← LangGraph agent
├── requirements.txt
└── .streamlit/
    └── config.toml
```

### Step 3 — Deploy
1. Go to **share.streamlit.io**
2. Sign in with GitHub
3. Click **New App**
4. Repo: `your-username/docgen-agent`
5. Main file: `frontend.py`
6. Click **Deploy** ✅

Your link will be: `https://docgen-agent.streamlit.app`

---

## 🔑 API Keys Needed
| Key | Where to get |
|-----|-------------|
| Groq API Key | console.groq.com (free) |
| Unsplash Access Key | unsplash.com/developers (free) |

Both are entered in the app sidebar — no `.env` file needed.

---

## 🧠 Tech Stack
- **LangGraph** — agentic state machine
- **Groq** — LLaMA 3.3 70B (free tier)
- **RAG** — FAISS + HuggingFace embeddings
- **python-docx** — Word document generation
- **Unsplash API** — section images
- **Streamlit** — frontend UI
