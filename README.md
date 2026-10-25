# CareerOS AI

Multi-agent career platform: upload a resume, pick a target job, and get a match analysis, skill gaps,
a learning roadmap, interview practice, and a RAG chatbot grounded in your own documents.

**Stack:** Streamlit · LangGraph · LangChain · ChromaDB (RAG) · SQLAlchemy (SQLite/PostgreSQL) · PyMuPDF · Docker

## Quick start

100% open-source by default — no API keys, no cost:
LLM = open models via [Ollama](https://ollama.com), embeddings = MiniLM (ONNX), vector DB = ChromaDB, jobs = Remotive public API.

```bash
# 1. LLM (one time): install Ollama from ollama.com, then
ollama pull llama3.2          # small & fast; use qwen2.5:7b / llama3.1:8b if you have 8GB+ RAM

# 2. App
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

If Ollama is not running the app still works in rule-based fallback mode (lower quality).
Hosted providers (Anthropic, OpenAI, Groq...) are optional — see `.env.example`.

### Docker + PostgreSQL

```bash
cp .env.example .env
docker compose up --build        # app on http://localhost:8501, Postgres included
```

## How it works

```
Resume -> Resume Agent -> Validate --(incomplete)--> ask user for missing info
                              \--(complete)--> Job Agent -> Matching Agent -> Skill Gap Agent
                                               -> Career Planner -> Interview Agent -> Final Report
```

| Folder | What lives there |
|---|---|
| `app.py` | Streamlit UI: Dashboard, Resume, Jobs, AI Agents, Career Chat, Interview |
| `agents/` | resume, job, matching, skill_gap, planner, interview agents |
| `graph/workflow.py` | LangGraph `CareerState`, nodes, conditional routing (supervisor) |
| `rag/chatbot.py` | Chunk -> embed -> retrieve -> grounded answer with `[R1]`/`[J1]` source citations |
| `core/` | LLM wrapper, embeddings, ChromaDB store, SQLAlchemy models (9 tables), PDF/DOCX parser |
| `data/sample_jobs.json` | Offline sample jobs, used when Adzuna keys are not set |

**Matching** is not just keywords: each required skill is `Matched` (alias match or strong semantic
similarity), `Needs evidence` (weak similarity — add proof to your resume) or `Missing`.
Thresholds are tunable via `SEMANTIC_MATCH_THRESHOLD` / `SEMANTIC_WEAK_THRESHOLD`.

**RAG grounding:** if nothing relevant is retrieved, the bot says so instead of guessing.

## Live jobs
Create a free key at developer.adzuna.com and set `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `ADZUNA_COUNTRY` in `.env`.
Check Adzuna's docs if the response format changes.

## Tests
```bash
pip install pytest && pytest -q
```

## Build phases (from the guide)
1. Core app: Resume page + parser ✔
2. Job intelligence: Jobs page + matching ✔
3. RAG: Career Chat ✔
4. LangGraph: AI Agents page ✔
5. Advanced: Interview simulator, persistence, Docker ✔ (next ideas: RAGAS evaluation, auth, PDF report export)

## Security
Never commit `.env`. It is already in `.gitignore`.
