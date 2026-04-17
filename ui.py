"""
ui.py — All rendering logic for the QA Analysis Portal.
"""

import streamlit as st
from database import (
    create_job, get_all_jobs, get_job, update_job, delete_job,
    get_questions, add_question, delete_question, update_question_type,
    update_question, get_answers, save_answer, clear_answers,
    get_research_topics, add_research_topic, delete_research_topic,
    get_research_items, add_research_item, update_research_item, delete_research_item,
)
from config import BRANDING, SECTOR_OPTIONS, PAGE_CONFIG, ANSWER_TYPES, LIKERT_SCALE
from ai_helper import generate_answers


# ════════════════════════════════════════════════════════════════════════════
#  Logo
# ════════════════════════════════════════════════════════════════════════════
def render_logo():
    st.image("./assets/logo/Fieri_Leadership.png", width=200)


# ════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ════════════════════════════════════════════════════════════════════════════
def render_theme():
    css_file_path = "./assets/style.css"
    with open(css_file_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ════════════════════════════════════════════════════════════════════════════

def render_sidebar():
    with st.sidebar:
        st.image("./assets/logo/Fieri_Leadership.png", width=75)
        st.markdown(
            f"""
            <div class="sidebar-brand">
                <span class="brand-logo">{BRANDING['logo_emoji']}</span>
                <div>
                    <div class="brand-name">{BRANDING['company_name']}</div>
                    <div class="brand-tagline">{BRANDING['tagline']}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("---")

        # ── Admin button ──
        if st.button("⚙ Admin / Jobs", use_container_width=True,
                      type="primary" if st.session_state.current_page == "admin" else "secondary"):
            st.session_state.current_page = "admin"
            st.session_state.current_job = None
            st.rerun()

        st.markdown("##### Recent Jobs")

        jobs = get_all_jobs()
        if not jobs:
            st.caption("No jobs yet. Create one in Admin.")
        else:
            for job_code, client_name, sector, _ in jobs:
                label = f"**{job_code}** · {client_name}"
                active = st.session_state.current_job == job_code
                if st.button(label, key=f"job_btn_{job_code}", use_container_width=True,
                              type="primary" if active else "secondary"):
                    st.session_state.current_job = job_code
                    st.session_state.current_page = "client"
                    st.rerun()

        st.markdown("---")

        # ── Mode selector ──
        if st.session_state.current_job:
            st.markdown("##### Answer Mode")
            mode = st.radio(
                "Mode",
                ["Manual"],
                # ["Manual", "Automatic (AI)"], use this instead of the above lien when the AI mode is working.
                index=0 if st.session_state.mode == "Manual" else 1,
                label_visibility="collapsed",
            )
            st.session_state.mode = "Manual" if mode == "Manual" else "Automatic"

            if st.session_state.mode == "Automatic":
                st.info("AI will generate draft answers from job context. You can edit afterwards.")

        st.markdown("---")
        st.caption(f"v{BRANDING['version']} · {BRANDING['company_name']}")

# ════════════════════════════════════════════════════════════════════════════
#  Common Page layout
# ════════════════════════════════════════════════════════════════════════════

def set_pagelayout():
    st.set_page_config(
    page_title="Fieri Leadership and Development - TNA Platform",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ════════════════════════════════════════════════════════════════════════════
#  ADMIN PAGE
# ════════════════════════════════════════════════════════════════════════════

def render_admin_page():
    st.markdown('<h1 class="page-title">⚙ Admin Panel</h1>', unsafe_allow_html=True)

    tab_create, tab_manage, tab_questions, tab_research = st.tabs(["Create Job", "Manage Jobs", "Manage Questions", "Research Base"])

    # ── Create Job ──────────────────────────────────────────────────────────
    with tab_create:
        st.markdown("#### New Job")
        col1, col2 = st.columns(2)
        with col1:
            job_code = st.text_input("Job Code *", placeholder="e.g. JOB-2024-001",
                                     help="Unique identifier. Will be uppercased.")
            client_name = st.text_input("Client Name *", placeholder="e.g. Acme Corporation")
            cohort_size = st.number_input("Cohort Size *",placeholder=10)
        with col2:
            sector = st.selectbox("Sector", SECTOR_OPTIONS)
            description = st.text_area("Description", placeholder="Brief context about this engagement…", height=120)

        if st.button("Create Job", type="primary", use_container_width=True):
            if not job_code or not client_name or not cohort_size:
                st.error("Job Code, Client Name and Cohort Size are required.")
            elif get_job(job_code):
                st.error(f"Job code **{job_code.upper()}** already exists.")
            else:
                create_job(job_code, client_name, description, sector,cohort_size)
                st.success(f"✅ Job **{job_code.upper()}** created.")
                st.session_state.current_job = job_code.upper()
                st.session_state.current_page = "client"
                st.rerun()

    # ── Manage Jobs ─────────────────────────────────────────────────────────
    with tab_manage:
        jobs = get_all_jobs()
        if not jobs:
            st.info("No jobs found. Create one first.")
        else:
            selected = st.selectbox(
                "Select a job to edit",
                [f"{j[0]} — {j[1]}" for j in jobs],
            )
            job_code_sel = selected.split(" — ")[0]
            if st.session_state.get("_last_admin_job") != job_code_sel:
                for k in ["edit_client", "edit_sector", "edit_desc","edit_cohort_size"]:
                    st.session_state.pop(k, None)
                    st.session_state["_last_admin_job"] = job_code_sel
            job = get_job(job_code_sel)

            if job:
                job_code_d, client_name_d, description_d, sector_d, created, updated, cohort_size_d = job
                st.markdown(f"<small>Created: {created[:10]} · Updated: {updated[:10]}</small>",
                            unsafe_allow_html=True)
                col1, col2 = st.columns(2)
                with col1:
                    new_client = st.text_input("Client Name", value=client_name_d, key=f"edit_client_{job_code_d}")
                    new_sector = st.selectbox("Sector", SECTOR_OPTIONS,
                                              index=SECTOR_OPTIONS.index(sector_d) if sector_d in SECTOR_OPTIONS else 0,
                                              key=f"edit_sector_{job_code_d}")
                    new_cohort_size = st.text_input("Cohort Size",value=cohort_size_d,key=f"edit_cohort_size_{job_code_d}")
                with col2:
                    new_desc = st.text_area("Description", value=description_d or "", height=120, key=f"edit_desc_{job_code_d}")

                col_save, col_del = st.columns([3, 1])
                with col_save:
                    if st.button("💾 Save Changes", type="primary", use_container_width=True):
                        update_job(job_code_d, new_client, new_desc, new_sector, new_cohort_size)
                        st.success("Saved.")
                        st.rerun()
                with col_del:
                    if st.button("🗑 Delete", type="secondary", use_container_width=True):
                        st.session_state["confirm_delete"] = job_code_d

                if st.session_state.get("confirm_delete") == job_code_d:
                    st.warning(f"Delete **{job_code_d}** and ALL its answers?")
                    col_yes, col_no = st.columns(2)
                    with col_yes:
                        if st.button("Yes, delete", type="primary"):
                            delete_job(job_code_d)
                            st.session_state.pop("confirm_delete", None)
                            if st.session_state.current_job == job_code_d:
                                st.session_state.current_job = None
                                st.session_state.current_page = "admin"
                            st.rerun()
                    with col_no:
                        if st.button("Cancel"):
                            st.session_state.pop("confirm_delete", None)
                            st.rerun()

    # ── Manage Questions ────────────────────────────────────────────────────
    with tab_questions:
        st.markdown("#### Question Bank")
        st.caption("Add or remove questions and set the answer type for each. Changes apply to all jobs.")

        page_sel = st.selectbox("Page", list(PAGE_CONFIG.keys()),
                                format_func=lambda k: PAGE_CONFIG[k]["label"])

        questions = get_questions(page_sel)
        for qid, qtext, pos, subsection, ans_type in questions:
            col_q, col_sub, col_type, col_del = st.columns([5, 2, 2, 1])
            with col_q:
                new_qtext = st.text_input(
                    "Question",
                    value=qtext,
                    key=f"qtext_{qid}",
                    label_visibility="collapsed",
                )
            with col_sub:
                new_sub = st.text_input(
                    "Subsection",
                    value=subsection or "",
                    key=f"qsub_{qid}",
                    label_visibility="collapsed",
                    placeholder="Subsection label…",
                )
            with col_type:
                type_options = list(ANSWER_TYPES.keys())
                current_idx = type_options.index(ans_type) if ans_type in type_options else 0
                new_type = st.selectbox(
                    "Type",
                    type_options,
                    index=current_idx,
                    key=f"type_{qid}",
                    format_func=lambda k: ANSWER_TYPES[k],
                    label_visibility="collapsed",
                )
                if new_type != ans_type:
                    update_question_type(qid, new_type)
                    st.rerun()
            with col_del:
                col_save_q, col_del_q = st.columns(2)
                with col_save_q:
                    if st.button("💾", key=f"save_q_{qid}", help="Save changes"):
                        update_question(qid, new_qtext, new_sub)
                        st.rerun()
                with col_del_q:
                    if st.button("✕", key=f"del_q_{qid}", help="Remove question"):
                        delete_question(qid)
                        st.rerun()

        st.markdown("---")
        col_new_q, col_new_type,col_subsection = st.columns([3, 1,1])
        with col_new_q:
            new_q = st.text_input("Add new question", placeholder="Type question text…")
        with col_subsection:
            new_subsection = st.text_input("Add a new subsection",placeholder="Type subsection text..")
        with col_new_type:
            new_type = st.selectbox(
                "Answer type",
                list(ANSWER_TYPES.keys()),
                format_func=lambda k: ANSWER_TYPES[k],
                key="new_q_type",
            )
        if st.button("＋ Add Question", type="primary"):
            if new_q.strip():
                add_question(page_sel, new_q.strip(), new_subsection,new_type)
                st.rerun()
            else:
                st.warning("Question text cannot be empty.")
    # ── Research Base ───────────────────────────────────────────────────────
    with tab_research:
        render_research_base()

# ════════════════════════════════════════════════════════════════════════════
#  LIKERT WIDGET
# ════════════════════════════════════════════════════════════════════════════

def _render_likert(job_code,qid, page_key, existing_value):
    """Render a 5-point Likert scale as radio buttons styled as clickable cards."""
    options = [o["value"] for o in LIKERT_SCALE]
    labels  = [f"{o['emoji']} {o['label']}" for o in LIKERT_SCALE]

    current_idx = options.index(existing_value) if existing_value in options else None

    # Use st.radio with horizontal layout
    selected_label = st.radio(
        f"likert_{page_key}_{qid}",
        labels,
        index=current_idx,
        horizontal=True,
        key=f"ans_{job_code}_{page_key}_{qid}",
        label_visibility="collapsed",
    )

    if selected_label is None:
        return ""
    idx = labels.index(selected_label)
    return options[idx]



def _render_dropdown(job_code, qid, page_key, qtext, existing_value):
    """Parse options from [opt1, opt2, ...] in question text and render a selectbox."""
    import re
    match = re.search(r'\[([^\]]+)\]', qtext)
    if not match:
        st.caption("⚠ No options defined. Add them in [option1, option2] format to the question text.")
        return existing_value

    options = [o.strip() for o in match.group(1).split(",") if o.strip()]
    options_with_placeholder = ["— Select —"] + options
    if existing_value in options:
        current_idx = options_with_placeholder.index(existing_value)
    else:
        current_idx = 0

    selected = st.selectbox(
        f"dropdown_{job_code}_{page_key}_{qid}",
        options_with_placeholder,
        index=current_idx,
        key=f"ans_{job_code}_{page_key}_{qid}",
        label_visibility="collapsed",
    )

    return "" if selected == "— Select —" else selected

# ════════════════════════════════════════════════════════════════════════════
#  JOB PAGES (Client / Learner / Manager)
# ════════════════════════════════════════════════════════════════════════════

def render_job_pages():
    job_code = st.session_state.current_job
    job = get_job(job_code)

    if not job:
        st.error("Job not found.")
        return

    job_code_d, client_name, description, sector,cohort_size, _, _ = job
    # Purge stale widget keys when job changes
    if st.session_state.get("_last_rendered_job") != job_code_d:
        stale = [k for k in st.session_state if k.startswith("ans_") or k.startswith("gen_")
                or k.startswith("save_") or k.startswith("clear_") or k.startswith("export_")]
        for k in stale:
            del st.session_state[k]
        st.session_state["_last_rendered_job"] = job_code_d

    # ── Job header ──────────────────────────────────────────────────────────
    st.markdown(
        f"""
        <div class="job-header">
            <div>
                <span class="job-code">{job_code_d}</span>
                <span class="job-client">{client_name}</span>
            </div>
            <span class="job-sector">{sector}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Page tabs ───────────────────────────────────────────────────────────
    page_keys = list(PAGE_CONFIG.keys())
    tab_labels = [f"{PAGE_CONFIG[k]['icon']} {PAGE_CONFIG[k]['label']}" for k in page_keys]
    tabs = st.tabs(tab_labels)

    for tab, page_key in zip(tabs, page_keys):
        with tab:
            st.session_state.current_page = page_key
            render_qa_page(job_code_d, page_key, job)


def render_qa_page(job_code, page_key, job):
    config = PAGE_CONFIG[page_key]
    mode = st.session_state.mode

    questions = get_questions(page_key)
    answers = get_answers(job_code, page_key)

    if not questions:
        st.info("No questions configured for this page. Add them in Admin → Manage Questions.")
        return

    # ── Auto-generate strip ──────────────────────────────────────────────
    if mode == "Automatic":
        col_info, col_btn = st.columns([3, 1])
        with col_info:
            st.markdown(
                f'<div class="mode-badge auto">✦ Automatic Mode — AI will draft answers from job context</div>',
                unsafe_allow_html=True,
            )
        with col_btn:
            if st.button(f"⚡ Generate All", key=f"gen_{job_code}_{page_key}", type="primary", use_container_width=True):
                with st.spinner("Generating answers…"):
                    job_details = {
                        "job_code": job[0],
                        "client_name": job[1],
                        "description": job[2],
                        "sector": job[3],
                    }
                    q_texts = [q[1] for q in questions]
                    ai_answers = generate_answers(job_details, q_texts, page_key)
                    for (qid, _, _), ans in zip(questions, ai_answers):
                        save_answer(job_code, page_key, qid, ans, mode="Automatic")
                st.rerun()
    else:
        st.markdown(
            '<div class="mode-badge manual">✎ Manual Mode — Fill in answers below</div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.info(PAGE_CONFIG[page_key]["description"], icon="ℹ️")

    # ── Q&A fields ───────────────────────────────────────────────────────
    draft = {}
    for qid, qtext, pos, subsection, ans_type in questions:
        existing = answers.get(qid, {}).get("answer", "")
        ans_mode = answers.get(qid, {}).get("mode", "")

        type_badge = {
            "likert":   '<span class="type-badge likert">Likert</span>',
            "dropdown": '<span class="type-badge dropdown">Dropdown</span>',
        }.get(ans_type, '<span class="type-badge text">Text</span>')

        subsection_badge = f' <span class="type-badge subsection">{subsection}</span>'
        ai_badge = ' <span class="ai-tag">AI</span>' if ans_mode == "Automatic" else ""

        import re as _re
        _display_text = _re.sub(r'\s*\[[^\]]*\]', '', qtext).strip()
        st.markdown(
            f'<div class="question-label">{pos + 1}. {_display_text} {subsection_badge} {type_badge}{ai_badge}</div>',
            unsafe_allow_html=True,
        )

        if ans_type == "likert":
            draft[qid] = _render_likert(job_code,qid, page_key, existing)
        elif ans_type == "dropdown":
            draft[qid] = _render_dropdown(job_code, qid, page_key, qtext, existing)
        else:
            draft[qid] = st.text_area(
                f"Answer {pos + 1}",
                value=existing,
                height=100,
                key=f"ans_{job_code}_{page_key}_{qid}",
                label_visibility="collapsed",
                placeholder="Enter answer here…",
            )

    st.markdown("---")

    # ── Action row ───────────────────────────────────────────────────────
    col_save, col_clear, col_export = st.columns([2, 1, 1])
    with col_save:
        if st.button("💾 Save All", type="primary", use_container_width=True, key=f"save_{job_code}_{page_key}"):
            for qid, answer_text in draft.items():
                save_answer(job_code, page_key, qid, answer_text, mode=mode)
            st.success("✅ Saved successfully.")

    with col_clear:
        if st.button("🗑 Clear All", type="secondary", use_container_width=True, key=f"clear_{job_code}_{page_key}"):
            st.session_state[f"confirm_clear_{page_key}"] = True

    with col_export:
        # Simple text export
        export_lines = [f"{PAGE_CONFIG[page_key]['label']} — {job_code}\n{'='*50}\n"]
        for qid, qtext, pos,subsection, ans_type in questions:
            ans = draft.get(qid, "")
            export_lines.append(f"Q{pos+1}: {qtext}\nA: {ans}\n")
        export_text = "\n".join(export_lines)
        st.download_button(
            "⬇ Export",
            data=export_text,
            file_name=f"{job_code}_{page_key}.txt",
            mime="text/plain",
            use_container_width=True,
            key=f"export_{job_code}_{page_key}",
        )

    if st.session_state.get(f"confirm_clear_{page_key}"):
        st.warning("This will remove all saved answers for this page. Continue?")
        col_yes, col_no = st.columns(2)
        with col_yes:
            if st.button("Yes, clear", type="primary", key=f"yes_clear_{job_code}_{page_key}"):
                clear_answers(job_code, page_key)
                st.session_state.pop(f"confirm_clear_{page_key}", None)
                st.rerun()
        with col_no:
            if st.button("No, cancel", key=f"no_clear_{job_code}_{page_key}"):
                st.session_state.pop(f"confirm_clear_{page_key}", None)
                st.rerun()


# ════════════════════════════════════════════════════════════════════════════
#  RESEARCH BASE
# ════════════════════════════════════════════════════════════════════════════    
def render_research_base():
    if "research_item_form_key" not in st.session_state:
        st.session_state.research_item_form_key = 0
    if "research_topic_form_key" not in st.session_state:
        st.session_state.research_topic_form_key = 0
    st.markdown("#### Research Base")
    st.caption("Organise research topics and items. Each item has a link, summary and detailed content.")

    # ── Add new topic ──────────────────────────────────────────────────────
    with st.expander("＋ Add New Topic", expanded=False):
        new_topic = st.text_input("Topic name", key=f"new_topic_name_{st.session_state.research_topic_form_key}")
        if st.button("Create Topic", type="primary", key="btn_create_topic"):
            if new_topic.strip():
                add_research_topic(new_topic.strip())
                st.success(f"Topic '{new_topic}' created.")
                st.session_state.research_topic_form_key += 1
                st.rerun()
            else:
                st.warning("Topic name cannot be empty.")

    st.markdown("---")

    topics = get_research_topics()
    if not topics:
        st.info("No topics yet. Add one above.")
        return

    # ── Topic selector ─────────────────────────────────────────────────────
    topic_map = {name: tid for tid, name in topics}
    selected_topic = st.selectbox(
        "Select topic",
        list(topic_map.keys()),
        key="research_topic_sel"
    )
    topic_id = topic_map[selected_topic]

    col_del_topic, _ = st.columns([1, 4])
    with col_del_topic:
        if st.button("🗑 Delete Topic", key=f"del_topic_{topic_id}", type="secondary"):
            st.session_state["confirm_del_topic"] = topic_id

    if st.session_state.get("confirm_del_topic") == topic_id:
        st.warning(f"Delete topic **{selected_topic}** and ALL its items?")
        col_yes, col_no = st.columns(2)
        with col_yes:
            if st.button("Yes, delete", type="primary", key="yes_del_topic"):
                delete_research_topic(topic_id)
                st.session_state.pop("confirm_del_topic", None)
                st.rerun()
        with col_no:
            if st.button("Cancel", key="no_del_topic"):
                st.session_state.pop("confirm_del_topic", None)
                st.rerun()

    st.markdown("---")

    # ── Add new item ───────────────────────────────────────────────────────
    with st.expander("＋ Add New Research Item", expanded=False):
        form_key = st.session_state.research_item_form_key
        ni_title   = st.text_input("Title *", key=f"ni_title_{form_key}")
        ni_link    = st.text_input("Link / URL", key=f"ni_link_{form_key}", placeholder="https://…")
        ni_summary = st.text_area("Summary", key=f"ni_summary_{form_key}", height=80,
                                  placeholder="One or two sentence overview…")
        ni_content = st.text_area("Detailed Content", key=f"ni_content_{form_key}", height=160,
                                  placeholder="Full notes, findings, quotes…")
        if st.button("Add Item", type="primary", key="btn_add_item"):
            if ni_title.strip():
                add_research_item(topic_id, ni_title.strip(), ni_link.strip(),
                                  ni_summary.strip(), ni_content.strip())
                st.success("Item added.")
                st.session_state.research_item_form_key += 1
                st.rerun()
            else:
                st.warning("Title is required.")

    # ── Existing items ─────────────────────────────────────────────────────
    items = get_research_items(topic_id)
    if not items:
        st.info("No items under this topic yet.")
        return

    for item_id, title, link, summary, content in items:
        with st.expander(f"📄 {title}", expanded=False):
            e_title   = st.text_input("Title", value=title,   key=f"ei_title_{item_id}")
            e_link    = st.text_input("Link",  value=link or "", key=f"ei_link_{item_id}",
                                      placeholder="https://…")
            e_summary = st.text_area("Summary", value=summary or "", height=80,
                                     key=f"ei_summary_{item_id}")
            e_content = st.text_area("Detailed Content", value=content or "", height=160,
                                     key=f"ei_content_{item_id}")

            col_save, col_del = st.columns([3, 1])
            with col_save:
                if st.button("💾 Save", type="primary", key=f"save_item_{item_id}",
                             use_container_width=True):
                    update_research_item(item_id, e_title, e_link, e_summary, e_content)
                    st.success("Saved.")
            with col_del:
                if st.button("🗑 Delete", type="secondary", key=f"del_item_{item_id}",
                             use_container_width=True):
                    delete_research_item(item_id)
                    st.rerun()

# ════════════════════════════════════════════════════════════════════════════
#  FOOTER
# ════════════════════════════════════════════════════════════════════════════    
def render_footer():
    st.markdown("""
<style>
.footer {
    position: fixed;
    left: 0;
    bottom: 0;
    width: 100%;
    background-color: #f8fafc;
    color: #1f2937;
    text-align: center;
    padding: 10px;
    font-size: 14px;
    border-top: 1px solid #e5e7eb;
}
</style>

<div class="footer">
    © 2026 Fieri Leadership | All Rights Reserved
</div>
""", unsafe_allow_html=True)