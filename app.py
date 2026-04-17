# ─── Authentication first ────────────────────────────────────────────────────────────
from ui import render_logo,render_theme
render_theme()
render_logo()

# ─── Authentication first ────────────────────────────────────────────────────────────
from auth import require_auth
require_auth()

import streamlit as st
from database import init_db
from ui import render_sidebar, render_admin_page, render_job_pages,render_footer,set_pagelayout

# ─── Page Config ────────────────────────────────────────────────────────────
set_pagelayout()

# ─── Inject Custom CSS ──────────────────────────────────────────────────────
# with open("style.css") as f:
#     st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ─── Initialise DB ──────────────────────────────────────────────────────────
init_db()
from database import init_research_tables
init_research_tables()

# ─── Session State Defaults ─────────────────────────────────────────────────
if "current_job" not in st.session_state:
    st.session_state.current_job = None
if "current_page" not in st.session_state:
    st.session_state.current_page = "admin"
if "mode" not in st.session_state:
    st.session_state.mode = "Manual"

# ─── Render App ─────────────────────────────────────────────────────────────
render_sidebar()

if st.session_state.current_page == "admin":
    render_admin_page()
else:
    render_job_pages()

# ─── Footer ────────────────────────────────────────────────────────────
render_footer()
