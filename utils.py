import streamlit as st

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