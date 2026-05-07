import streamlit as st
from pathlib import Path

def set_request_id()->None:
    """Sets a request id for the existing streamlit session state"""
    if 'request_id' not in st.session_state:
        from nanoid import generate
        id = generate(size=10)
        st.session_state['request_id'] = id
    

def get_request_id()->str:
    """ Retrieves request id from the existing streamlit session state."""
    if 'request_id' not in st.session_state:
        return "NO_USER"
    else:
        return st.session_state['request_id']
    

def get_latest_matching_file(directory, starts_with, extension)->Path | None:
    directory = Path(directory)
    if not directory.is_dir():
        return None
    latest_file = None
    latest_mtime = -1
    for file in directory.iterdir():
        if not file.is_file():
            continue
        if not file.name.startswith(starts_with):
            continue
        if file.suffix.lower() != extension.lower():
            continue
        # 4. Only now get modified time
        mtime = file.stat().st_mtime
        if mtime > latest_mtime:
            latest_mtime = mtime
            latest_file = file
    return latest_file