import streamlit as st
import bcrypt

from logger import get_logger

logger = get_logger()

def _check_password(username, password):
    try:
        stored_hash = st.secrets["auth"]["passwords"][username]
        return bcrypt.checkpw(password.encode(), stored_hash.encode())
    except Exception:
        return False

def _login():
    st.title("Fieri Leadership - TNA Database platform - Login")
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")

    if st.button("Login"):
        if _check_password(u, p):
            st.session_state["auth"] = True
            st.session_state["user"] = u
            from utils import set_request_id
            set_request_id()
            logger.info(f"User <{u}> just logged in.")
            st.rerun()
        else:
            st.error("Invalid credentials")

def _logout():
    logger.info(f"User <{st.session_state["user"]}> just logged out.")
    st.session_state.clear()
    st.rerun()

def require_auth():
    if "auth" not in st.session_state:
        st.session_state["auth"] = False

    if not st.session_state["auth"]:
        _login()
        st.stop()

    with st.sidebar:
        st.markdown("---")
        st.markdown(f"### 👤 {(st.session_state.get('user','')).upper()}")
        if st.button("⏻", use_container_width=False):
            _logout()