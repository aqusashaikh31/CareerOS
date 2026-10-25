"""CareerOS AI — Streamlit app.  Run:  streamlit run app.py"""
import pandas as pd
import streamlit as st

from agents.interview_agent import evaluate_answer, generate_questions
from agents.job_agent import parse_job_description, search_jobs
from core import db
from core.llm import llm_available
from core.resume_parser import extract_text
from agents.resume_agent import parse_resume
from graph.workflow import stream_workflow
from rag import chatbot

st.set_page_config(page_title="CareerOS AI", page_icon="🧭", layout="wide")
db.init_db()

CSS = """
<style>
.block-container {padding-top: 2rem;}
.cos-hero h1 {margin: 0; font-size: 2.1rem;}
.cos-hero p {margin: .2rem 0 1.2rem 0; opacity: .7;}
.cos-card {border: 1px solid rgba(128,128,128,.25); border-radius: 16px; padding: 18px 20px;
  background: linear-gradient(135deg, rgba(0,102,204,.14), rgba(0,180,160,.08)); min-height: 120px;}
.cos-card .num {font-size: .8rem; letter-spacing: .12em; opacity: .6;}
.cos-card .title {font-size: 1.25rem; font-weight: 700; margin: 2px 0;}
.cos-card .sub {opacity: .7; font-size: .9rem;}
.cos-card .count {font-size: 1.9rem; font-weight: 800; float: right; margin-top: -48px;}
.badge {padding: 2px 10px; border-radius: 999px; font-size: .78rem; font-weight: 600; white-space: nowrap;}
.b-Matched {background: rgba(46,160,67,.2); color: #2ea043;}
.b-Needs {background: rgba(210,153,34,.2); color: #d29922;}
.b-Missing {background: rgba(248,81,73,.2); color: #f85149;}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------- session bootstrap ----------------
S = st.session_state
for key, default in {
    "user_id": None, "user_name": "Guest", "resume_text": "", "profile": None, "jobs": [], "job": None,
    "state": None, "interview_id": None, "chat": [], "q_idx": 0, "eval": None,
}.items():
    S.setdefault(key, default)


def load_user(name: str):
    uid = db.get_or_create_user(name)
    if uid != S.user_id:
        S.user_id, S.user_name = uid, name
        S.profile = db.latest_profile(uid)
        S.resume_text = db.latest_resume_text(uid) or ""
        S.jobs = db.list_jobs(uid)
        S.job, S.state, S.interview_id, S.chat = None, None, None, []


with st.sidebar:
    st.markdown("## 🧭 CareerOS AI")
    name = st.text_input("Your name", value=S.user_name)
    load_user(name.strip() or "Guest")
    page = st.radio("Navigate", ["Dashboard", "Resume", "Jobs", "AI Agents", "Career Chat", "Interview"], label_visibility="collapsed")
    st.divider()
    if llm_available():
        st.success("LLM connected")
    else:
        st.warning("No LLM reachable — rule-based fallback mode. Start Ollama (`ollama serve`, `ollama pull llama3.2`) for full AI quality.")
    if S.job:
        st.caption(f"Target job: **{S.job['title']}** @ {S.job.get('company') or '—'}")


def badge(status: str) -> str:
    cls = {"Matched": "b-Matched", "Needs evidence": "b-Needs", "Missing": "b-Missing"}[status]
    return f'<span class="badge {cls}">{status}</span>'


def need(cond, msg):
    if not cond:
        st.info(msg)
        st.stop()


# ---------------- pages ----------------
def page_dashboard():
    st.markdown('<div class="cos-hero"><h1>CareerOS AI</h1><p>AI Career Intelligence · Dashboard</p></div>', unsafe_allow_html=True)
    c = db.dashboard_counts(S.user_id)
    cards = [("01", "Resume", "Profile analysis", c["resumes"]), ("02", "Jobs", "Job matching", c["jobs"]),
             ("03", "AI Agents", "Career analysis", c["plans"]), ("04", "Interview", "AI practice", c["answers"])]
    for col, (n, t, sub, cnt) in zip(st.columns(4), cards):
        col.markdown(f'<div class="cos-card"><div class="num">{n}</div><div class="title">{t}</div>'
                     f'<div class="sub">{sub}</div><div class="count">{cnt}</div></div>', unsafe_allow_html=True)
    st.markdown("### Progress")
    hist = db.match_history(S.user_id)
    if hist:
        df = pd.DataFrame(hist)
        left, right = st.columns([2, 3])
        left.metric("Latest match score", f"{df.iloc[0]['score']}%", delta=(f"{df.iloc[0]['score'] - df.iloc[1]['score']:+.1f}" if len(df) > 1 else None))
        right.dataframe(df.rename(columns={"job": "Job", "company": "Company", "score": "Match %", "at": "When"}), use_container_width=True, hide_index=True)
    else:
        st.info("No analysis yet. Start with **Resume** → **Jobs** → **AI Agents**.")


def page_resume():
    st.header("Resume Agent")
    up = st.file_uploader("Upload resume (PDF / DOCX / TXT)", type=["pdf", "docx", "txt"])
    if up and st.button("Analyze resume", type="primary"):
        with st.spinner("Reading and extracting profile..."):
            try:
                text = extract_text(up.getvalue(), up.name)
            except Exception as e:
                st.error(f"Could not read file: {e}")
                st.stop()
            if len(text) < 80:
                st.error("Very little text found. If this is a scanned PDF, upload a text-based version.")
                st.stop()
            rid = db.save_resume(S.user_id, up.name, text)
            profile = parse_resume(text)
            db.save_profile(S.user_id, rid, profile)
            chatbot.index_resume(S.user_id, rid, text)
            S.resume_text, S.profile = text, profile
        st.success("Profile saved. Other agents will reuse it — no need to re-upload.")
    need(S.profile, "Upload a resume to see your extracted profile.")
    p = S.profile
    a, b = st.columns(2)
    a.subheader(p.get("name") or "Candidate")
    a.write(f"**Email:** {p.get('email') or '—'}")
    a.write(f"**Education:** {p.get('education') or '—'}")
    a.write("**Skills:** " + (", ".join(p.get("skills", [])) or "—"))
    if p.get("certifications"):
        a.write("**Certifications:** " + "; ".join(p["certifications"]))
    b.subheader("Projects")
    for pr in p.get("projects", []) or [{"name": "—", "description": "No projects detected"}]:
        b.markdown(f"**{pr.get('name')}** — {pr.get('description', '')}")
    with st.expander("Edit skills manually"):
        edited = st.text_area("Comma-separated skills", ", ".join(p.get("skills", [])))
        if st.button("Save skills"):
            p["skills"] = [s.strip() for s in edited.split(",") if s.strip()]
            db.save_profile(S.user_id, db.latest_resume_id(S.user_id), p)
            S.profile = p
            st.success("Skills updated and saved. Re-run AI Agents to refresh results.")


def page_jobs():
    st.header("Job Research Agent")
    need(S.profile, "Upload your resume first (Resume page).")
    tab1, tab2 = st.tabs(["Search jobs", "Paste a job description"])
    with tab1:
        c1, c2, c3 = st.columns([3, 2, 1])
        role = c1.text_input("Target role", "GenAI Engineer Intern")
        loc = c2.text_input("Location (optional)", "")
        if c3.button("Search", type="primary"):
            with st.spinner("Searching and parsing job descriptions..."):
                res = search_jobs(role, loc)
            saved = []
            for j in res["jobs"]:
                j["id"] = db.save_job(S.user_id, j)
                saved.append(j)
            S.jobs = saved + [j for j in S.jobs if j["id"] not in {x["id"] for x in saved}]
            st.caption("Source: " + {"adzuna": "Adzuna API", "remotive": "Remotive public API (free, remote jobs)"}.get(
                res["source"], "bundled sample jobs (live API unreachable)"))
    with tab2:
        title = st.text_input("Job title", "")
        company = st.text_input("Company", "")
        jd = st.text_area("Paste job description", height=180)
        if st.button("Parse & save JD") and jd.strip():
            job = {"title": title or "Custom role", "company": company, "location": "", "description": jd, "url": "", **parse_job_description(jd)}
            job["id"] = db.save_job(S.user_id, job)
            S.jobs.insert(0, job)
            st.success("Saved.")
    st.markdown("### Saved jobs")
    need(S.jobs, "No jobs yet — search or paste one above.")
    for j in S.jobs:
        with st.expander(f"{j['title']} — {j.get('company') or 'Unknown'}  ·  {j.get('location') or ''}"):
            st.write(j["description"][:700] + ("..." if len(j["description"]) > 700 else ""))
            st.write("**Required:** " + (", ".join(j.get("required_skills", [])) or "—"))
            st.write("**Preferred:** " + (", ".join(j.get("preferred_skills", [])) or "—"))
            if j.get("url"):
                st.markdown(f"[Open listing]({j['url']})")
            if st.button("Set as target job", key=f"sel{j['id']}"):
                S.job, S.state = j, None
                chatbot.index_job(S.user_id, j["id"], j)
                st.success("Target job set. Go to **AI Agents**.")


def page_agents():
    st.header("AI Agents — Career Analysis")
    need(S.profile, "Upload your resume first.")
    need(S.job, "Pick a target job on the Jobs page.")
    st.write(f"Analyzing **{S.profile.get('name') or S.user_name}** against **{S.job['title']}**")
    if st.button("Run LangGraph workflow", type="primary"):
        state = {"resume_text": S.resume_text, "candidate_profile": S.profile, "target_role": S.job["title"], "job": S.job}
        with st.status("Agents working...", expanded=True) as status:
            for node, update in stream_workflow(state):
                state.update(update)
                st.write(f"✅ **{node}** — {update.get('trace', [''])[-1]}")
            status.update(label="Workflow complete", state="complete")
        S.state = state
        rep = state.get("final_report", {})
        if rep.get("status") == "complete":
            jid = S.job["id"]
            db.save_match(S.user_id, jid, rep["match_score"], state["match_result"])
            db.save_gaps(S.user_id, jid, rep["skill_gaps"])
            db.save_plan(S.user_id, jid, rep["roadmap"])
            S.interview_id = db.save_interview(S.user_id, jid, rep["interview_questions"])
            S.q_idx, S.eval = 0, None
    state = S.state
    need(state, "Run the workflow to see results.")
    rep = state["final_report"]
    if rep["status"] != "complete":
        st.warning(rep["message"])
        for m in rep["missing_info"]:
            st.write(f"- {m}")
        st.stop()
    m1, m2, m3 = st.columns(3)
    m1.metric("Match score", f"{rep['match_score']}%")
    m2.metric("Matched skills", len(rep["matched_skills"]))
    m3.metric("Gaps", len(rep["skill_gaps"]))
    st.subheader("Resume vs job requirements")
    rows = "".join(
        f"<tr><td>{r['skill']}</td><td>{r['kind']}</td><td>{badge(r['status'])}</td><td style='opacity:.7;font-size:.85rem'>{r['evidence'][:110]}</td></tr>"
        for r in state["match_result"]["results"]
    )
    st.markdown(f"<table style='width:100%'><tr><th align=left>Skill</th><th align=left>Type</th><th align=left>Status</th><th align=left>Evidence</th></tr>{rows}</table>", unsafe_allow_html=True)
    st.subheader("Learning roadmap")
    for w in rep["roadmap"]:
        with st.expander(f"Week {w.get('week')} — {w.get('focus')}"):
            for t in w.get("tasks", []):
                st.write("• " + t)
            st.caption("Deliverable: " + str(w.get("deliverable", "")))
    with st.expander("Agent trace"):
        for t in state.get("trace", []):
            st.write("• " + t)
    st.download_button("Download report (JSON)", data=pd.Series(rep).to_json(indent=2), file_name="career_report.json")


def page_chat():
    st.header("Career Chat (RAG)")
    need(S.profile, "Upload your resume first.")
    st.caption("Answers come only from your resume and the selected job description, with sources.")
    if not S.job:
        st.info("Tip: set a target job to also search the job description.")
    for msg in S.chat:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            for s in msg.get("sources", []):
                with st.expander(f"Source [{s['tag']}] · similarity {s['score']}"):
                    st.write(s["text"])
    q = st.chat_input("e.g. Why am I suitable for this GenAI internship?")
    if q:
        S.chat.append({"role": "user", "content": q})
        with st.spinner("Retrieving evidence..."):
            res = chatbot.answer(S.user_id, q)
        S.chat.append({"role": "assistant", "content": res["answer"], "sources": res["sources"]})
        st.rerun()


def page_interview():
    st.header("Interview Practice")
    need(S.profile, "Upload your resume first.")
    need(S.job, "Pick a target job first.")
    if not (S.state and S.state.get("interview_questions")):
        if st.button("Generate questions", type="primary"):
            qs = generate_questions(S.profile, S.job)
            S.state = {"interview_questions": qs}
            S.interview_id = db.save_interview(S.user_id, S.job["id"], qs)
            S.q_idx, S.eval = 0, None
            st.rerun()
        st.stop()
    qs = S.state["interview_questions"]
    S.q_idx = min(S.q_idx, len(qs) - 1)
    q = qs[S.q_idx]
    st.progress((S.q_idx + 1) / len(qs), text=f"Question {S.q_idx + 1} of {len(qs)} · {q.get('topic', '')}")
    st.subheader(q["question"])
    ans = st.text_area("Your answer", height=160, key=f"ans{S.q_idx}")
    c1, c2, c3 = st.columns([1, 1, 4])
    if c1.button("Evaluate", type="primary") and ans.strip():
        with st.spinner("Interviewer is thinking..."):
            S.eval = evaluate_answer(q["question"], ans, S.job)
        db.save_answer(S.interview_id, q["question"], ans, float(S.eval.get("score", 0)), S.eval)
    if c2.button("Next ▶") and S.q_idx < len(qs) - 1:
        S.q_idx, S.eval = S.q_idx + 1, None
        st.rerun()
    ev = S.eval
    if ev:
        st.metric("Score", f"{ev.get('score', 0)}/10")
        if ev.get("strengths"):
            st.success("**Strengths**\n\n" + "\n".join(f"- {s}" for s in ev["strengths"]))
        if ev.get("improvements"):
            st.warning("**Improve**\n\n" + "\n".join(f"- {s}" for s in ev["improvements"]))
        with st.expander("Ideal answer points"):
            for p in ev.get("ideal_answer_points", []):
                st.write("• " + p)
        if ev.get("follow_up"):
            st.info("**Follow-up:** " + ev["follow_up"])
        if ev.get("note"):
            st.caption(ev["note"])


{"Dashboard": page_dashboard, "Resume": page_resume, "Jobs": page_jobs, "AI Agents": page_agents,
 "Career Chat": page_chat, "Interview": page_interview}[page]()
