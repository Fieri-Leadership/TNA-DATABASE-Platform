"""
logger.py — Centralised logging
All modules import get_logger() from here.
"""

import logging
import sys
import copy
from utils import get_request_id
import streamlit as st


def filter(record: logging.LogRecord):
    record = copy.copy(record)
    id = get_request_id()
    record.request_id = id
    return record

@st.cache_resource
def _setup_logger():
    """
    Create and configure the app logger once.
    @st.cache_resource ensures this runs only once per app session,
    even though Streamlit reruns the script on every interaction.
    """
    logger = logging.getLogger("TNA database")
    # Avoid adding duplicate handlers if somehow called twice
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # ── Format ────────────────────────────────────────────────────────────
    fmt = logging.Formatter(
        fmt="%(asctime)s | %(request_id)-8s | %(levelname)-8s | %(module)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
   
    # ── Console handler (visible in Streamlit Cloud logs) ─────────────────
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG)
    console.setFormatter(fmt)
    console.addFilter(filter)
    logger.addHandler(console)

    # ── File handler (local dev only — skipped silently on read-only fs) ──
    try:
        file_handler = logging.FileHandler("tna_database.log", mode="a", encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(fmt)
        file_handler.addFilter(filter)
        logger.addHandler(file_handler)
    except (OSError, PermissionError):
        pass  # Streamlit Cloud has a read-only filesystem — that's fine

    logger.propagate = False
    logger.info("Logger initialised")
    return logger


def get_logger():
    """Call this in any module to get the shared logger."""
    return _setup_logger()