import sqlite3
import os
import sys
from datetime import datetime
import threading
import streamlit as st
import libsql
from contextlib import contextmanager

from logger import get_logger
logger = get_logger()

DB_PATH = "qa_portal.db"
# Load .env file if present (local dev only)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    logger.error("Error loading variables from the environment.")
    pass  # dotenv not installed, rely on real environment variables

TURSO_DB_NAME = os.environ.get("TURSO_DB_NAME", "").strip()
TURSO_URL   = os.environ.get("TURSO_URL", "").strip()
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "").strip()
USE_TURSO   = bool(TURSO_URL and TURSO_TOKEN and TURSO_DB_NAME)

# @st.cache_resource
# def _get_turso_conn():
#     import libsql
#     try:
#         conn = libsql.connect(TURSO_URL, auth_token=TURSO_TOKEN)
#         return conn
#     except Exception as e:
#         logger.error(f"Error connecting database at Turso: {e}", exc_info=True)
#         raise

# logger.info(f"Using database backend: {'Turso' if USE_TURSO else 'SQLite'}")
# @contextmanager
# def get_conn():
#     if USE_TURSO:
#         conn = _get_turso_conn()
#         try:
#             yield conn
#             conn.commit()
#         except Exception as e:
#             logger.error(f"Turso DB error: {e}", exc_info=True)
#             st.error("Something went wrong with database connection. Contact your admin. ")
#         # Note: do NOT close — connection is reused across requests
#     else:
#         conn = sqlite3.connect(DB_PATH, check_same_thread=False)
#         try:
#             yield conn
#             conn.commit()
#         except Exception as e:
#             logger.error(f"Local DB error: {e}", exc_info=True)
#             raise
#         finally:
#             conn.close()
_lock = threading.Lock()

@st.cache_resource
def _get_turso_conn():
    logger.info("Creating Turso connection")

    return libsql.connect(
        TURSO_URL,
        auth_token=TURSO_TOKEN
    )


def _reconnect():
    logger.warning("Reconnecting Turso database...")

    try:
        _get_turso_conn().close()
    except Exception:
        pass

    _get_turso_conn.clear()

    return _get_turso_conn()


def _ensure_connection(conn):
    try:
        conn.execute("SELECT 1")
        return conn

    except Exception as e:
        logger.warning(f"Stale Turso connection detected: {e}")

        return _reconnect()


@contextmanager
def get_conn():

    if USE_TURSO:

        with _lock:

            conn = _get_turso_conn()
            conn = _ensure_connection(conn)

        try:
            yield conn
            conn.commit()

        except Exception as e:

            logger.error(
                f"Turso DB error: {e}",
                exc_info=True
            )

            # reconnect for next request
            _reconnect()

            raise

    else:

        conn = sqlite3.connect(
            DB_PATH,
            check_same_thread=False
        )

        try:
            yield conn
            conn.commit()

        except Exception as e:

            logger.error(
                f"Local DB error: {e}",
                exc_info=True
            )

            raise

        finally:
            conn.close()

def init_db():
    with get_conn() as conn:
        try:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_code     TEXT PRIMARY KEY,
                client_name  TEXT NOT NULL,
                description  TEXT,
                sector       TEXT,
                created_at   TEXT,
                updated_at   TEXT,
                cohort_size  INT DEFAULT 10
            );

            CREATE TABLE IF NOT EXISTS questions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                page         TEXT NOT NULL,
                position     INTEGER NOT NULL,
                question     TEXT NOT NULL,
                answer_type  TEXT DEFAULT 'text',
                is_active    INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS answers (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                job_code     TEXT NOT NULL,
                page         TEXT NOT NULL,
                question_id  INTEGER NOT NULL,
                answer       TEXT,
                mode         TEXT DEFAULT 'Manual',
                updated_at   TEXT,
                UNIQUE(job_code, page, question_id)
            );
            """)
            # Migration: add answer_type column to existing databases
            # cols = [r[1] for r in conn.execute("PRAGMA table_info(questions)").fetchall()]
            # if "answer_type" not in cols:
            #     conn.execute("ALTER TABLE questions ADD COLUMN answer_type TEXT DEFAULT 'text'")
            # _seed_default_questions(conn)
        except Exception as e:
            logger.critical(f"DB init failed: {e}", exc_info=True)
            raise


def _seed_default_questions(conn):
    """Insert default questions if table is empty."""
    count = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    if count > 0:
        return

    defaults = {
        "client": [
            "What are the primary business objectives driving this engagement?",
            "What are the key performance indicators (KPIs) for success?",
            "What challenges or pain points is the client currently experiencing?",
            "What is the timeline and budget for the project?",
            "Who are the key stakeholders and decision-makers?",
            "What previous initiatives or solutions have been attempted?",
            "What does success look like at the end of this engagement?",
            "Are there any constraints or non-negotiables we should be aware of?",
        ],
        "learner": [
            "What is the target learner profile and demographic?",
            "What prior knowledge or experience do learners bring?",
            "What are the primary learning objectives?",
            "How will learning be delivered (e.g. online, blended, in-person)?",
            "What motivates this learner group?",
            "What barriers to learning might this group face?",
            "How will learning be assessed or measured?",
            "What is the expected time commitment for learners?",
        ],
        "manager": [
            "What behaviours or skills should managers reinforce post-training?",
            "How will line managers support learners on the job?",
            "What reporting or visibility do managers need on learner progress?",
            "How will managers be briefed on the programme objectives?",
            "What role will managers play in the sign-off or completion process?",
            "What concerns might managers have about releasing staff for training?",
            "How can managers be engaged as champions of this initiative?",
            "What follow-up actions will managers be expected to take?",
        ],
    }

    for page, questions in defaults.items():
        for i, q in enumerate(questions):
            conn.execute(
                "INSERT INTO questions (page, position, question) VALUES (?, ?, ?)",
                (page, i, q),
            )

# ─── Common DB fetch Functions ────────────────────────────────────────────────────────────────

def fetchall(sql, params=()):
    with get_conn() as conn:
        return conn.execute(sql, params).fetchall()


def fetchone(sql, params=()):
    with get_conn() as conn:
        return conn.execute(sql, params).fetchone()

def verify_schema() -> None:
    REQUIRED_TABLES = {"jobs", "questions", "answers"}
    """
    Check that all required tables exist in the connected database.
    Prints a clear diagnostic and exits with code 1 if any are missing.
    """
    try:
        rows = fetchall("SELECT name FROM sqlite_master WHERE type='table'")
    except Exception as e:
        logger.error(f"\n[ERROR] Could not query database schema: {e}")
        logger.error("  → Check that TURSO_URL and TURSO_AUTH_TOKEN are correct and point to the right database.")
        sys.exit(1)
 
    found_tables = {row[0] for row in rows}
    missing = REQUIRED_TABLES - found_tables
 
    if missing:
        logger.error("\n[ERROR] Connected to the database but required tables are missing.")
        logger.error(f"  Expected : {', '.join(sorted(REQUIRED_TABLES))}")
        logger.error(f"  Found    : {', '.join(sorted(found_tables)) or '(no tables)'}")
        logger.error(f"  Missing  : {', '.join(sorted(missing))}")
        logger.error("\n  → You are likely connected to the wrong database.")
        logger.error("     Run:  turso db list")
        logger.error("     Then: turso db show <correct-db-name>  to get the right URL.")
        sys.exit(1)
 
    logger.info(f"  Schema OK — tables verified: {', '.join(sorted(REQUIRED_TABLES))}")

# ─── Job CRUD and helper functions ────────────────────────────────────────────────────────────────

def create_job(job_code, client_name, description, sector,cohort_size):
    logger.info(f"Creating job: {job_code.upper()} — {client_name}")
    now = datetime.now().isoformat()
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO jobs VALUES (?, ?, ?, ?, ?, ?, ?)",
                (job_code.upper(), client_name, description, sector,now, now, cohort_size),
            )
    except Exception as e:
        logger.error(f"Failed to create job {job_code}: {e}", exc_info=True)
        raise


def get_all_jobs():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT job_code, client_name, sector, cohort_size FROM jobs ORDER BY created_at DESC"
        ).fetchall()
    return rows


def get_job(job_code):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM jobs WHERE job_code = ?", (job_code.upper(),)
        ).fetchone()
    return row


def update_job(job_code, client_name, description, sector,cohort_size):
    now = datetime.now().isoformat()
    with get_conn() as conn:
        conn.execute(
            "UPDATE jobs SET client_name=?, description=?, sector=?, updated_at=?, cohort_size=? WHERE job_code=?",
            (client_name, description, sector,now,cohort_size, job_code.upper()),
        )


def delete_job(job_code):
    logger.warning(f"Deleting job and all answers: {job_code}")
    try:
        with get_conn() as conn:
            conn.execute("DELETE FROM jobs WHERE job_code = ?", (job_code.upper(),))
            conn.execute("DELETE FROM answers WHERE job_code = ?", (job_code.upper(),))
    except Exception as e:
        logger.error(f"Failed to delete job {job_code}: {e}", exc_info=True)
        raise


def verify_job_exists(job_code: str) -> None:
    """
    Check that the given job_code exists in the jobs table.
    Prints a clear diagnostic and exits with code 1 if not found.
    """
    row = fetchone("SELECT job_code, client_name FROM jobs WHERE job_code = ?", (job_code,))
    if not row:
        # Show available job codes to help the user pick the right one
        available = fetchall("SELECT job_code, client_name FROM jobs ORDER BY job_code")
        logger.error(f"\n[ERROR] Job code '{job_code}' not found in the jobs table.")
        if available:
            logger.error(f"  Available job codes:")
            for jc, name in available:
                logger.error(f"    - {jc}  ({name})")
        else:
            logger.error("  The jobs table is empty — no jobs have been created yet.")
        sys.exit(1)
    logger.debug(f"  Job OK — '{job_code}' found: {row[1]}")

def get_job_metadata(job_code:str)->list[str]:
    job_row = fetchone(
            "SELECT job_code, client_name, description, sector, cohort_size FROM jobs WHERE job_code = ?",
            (job_code,))
    job_lines=[]
    if job_row:
        job_code_val, client_name, description, sector, cohort_size = job_row
        job_lines.append(f"- Job Code: {job_code_val}")
        job_lines.append(f"- Client: {client_name}")
        job_lines.append(f"- Sector: {sector or 'N/A'}")
        job_lines.append(f"- Cohort Size: {cohort_size or 'N/A'}")
        if description:
            job_lines.append(f"- Description: {description}")
    return job_lines

# ─── Question CRUD ──────────────────────────────────────────────────────────

def get_questions(page):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, question, position,subsection, answer_type FROM questions WHERE page=? AND is_active=1 ORDER BY position",
            (page,),
        ).fetchall()
    return rows


def add_question(page, question_text, subsection_text, answer_type="text"):
    with get_conn() as conn:
        max_pos = conn.execute(
            "SELECT COALESCE(MAX(position), -1) FROM questions WHERE page=?", (page,)
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO questions (page, position, question, subsection,answer_type) VALUES (?, ?, ? , ?, ?)",
            (page, max_pos + 1, question_text,subsection_text, answer_type),
        )


def delete_question(question_id):
    with get_conn() as conn:
        conn.execute("UPDATE questions SET is_active=0 WHERE id=?", (question_id,))


def update_question_type(question_id, answer_type):
    with get_conn() as conn:
        conn.execute("UPDATE questions SET answer_type=? WHERE id=?", (answer_type, question_id))

def update_question(question_id, question_text, subsection):
    with get_conn() as conn:
        conn.execute(
            "UPDATE questions SET question=?, subsection=? WHERE id=?",
            (question_text, subsection, question_id)
        )

# ─── Answer CRUD ─────────────────────────────────────────────────────────────

def get_answers(job_code, page):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT question_id, answer, mode FROM answers WHERE job_code=? AND page=?",
            (job_code.upper(), page),
        ).fetchall()
    return {r[0]: {"answer": r[1], "mode": r[2]} for r in rows}


def save_answer(job_code, page, question_id, answer, mode="Manual"):
    try:
        now = datetime.now().isoformat()
        with get_conn() as conn:
            conn.execute(
                """INSERT INTO answers (job_code, page, question_id, answer, mode, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_code, page, question_id)
                DO UPDATE SET answer=excluded.answer, mode=excluded.mode, updated_at=excluded.updated_at""",
                (job_code.upper(), page, question_id, answer, mode, now),
            )
    except Exception as e:
        logger.error(f"Failed to save answer — job:{job_code} q:{question_id}: {e}", exc_info=True)
        raise


def clear_answers(job_code, page):
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM answers WHERE job_code=? AND page=?",
            (job_code.upper(), page),
        )


# ─── Research Base ───────────────────────────────────────────────────────────

def init_research_tables():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS research_topics (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS research_items (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id   INTEGER NOT NULL,
            title      TEXT NOT NULL,
            link       TEXT,
            summary    TEXT,
            content    TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (topic_id) REFERENCES research_topics(id)
        );
        """)

def get_research_topics():
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, name FROM research_topics ORDER BY name"
        ).fetchall()

def add_research_topic(name):
    now = datetime.now().isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO research_topics (name, created_at) VALUES (?, ?)",
            (name, now)
        )

def delete_research_topic(topic_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM research_items WHERE topic_id=?", (topic_id,))
        conn.execute("DELETE FROM research_topics WHERE id=?", (topic_id,))

def get_research_items(topic_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, title, link, summary, content FROM research_items WHERE topic_id=? ORDER BY title",
            (topic_id,)
        ).fetchall()

def add_research_item(topic_id, title, link, summary, content):
    now = datetime.now().isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO research_items (topic_id, title, link, summary, content, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
            (topic_id, title, link, summary, content, now, now)
        )

def update_research_item(item_id, title, link, summary, content):
    now = datetime.now().isoformat()
    with get_conn() as conn:
        conn.execute(
            "UPDATE research_items SET title=?, link=?, summary=?, content=?, updated_at=? WHERE id=?",
            (title, link, summary, content, now, item_id)
        )

def delete_research_item(item_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM research_items WHERE id=?", (item_id,))

# ─── TNA Report ───────────────────────────────────────────────────────────

def save_tna_report(job_code: str, requested_by: str, report_content: str):
    """Save a generated TNA report to the database."""
    now = datetime.now().isoformat()
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO tna_reports (requested_by, request_timestamp, report_content, job_code)
               VALUES (?, ?, ?, ?)""",
            (requested_by, now, report_content, job_code.upper())
        )
    logger.info(f"TNA report saved — job:{job_code} user:{requested_by}")


def get_latest_tna_report(job_code: str, requested_by: str) -> str | None:
    """Fetch the most recent report for a given job and user. Returns None if not found."""
    with get_conn() as conn:
        row = conn.execute(
            """SELECT report_content FROM tna_reports
               WHERE job_code = ? AND requested_by = ?
               ORDER BY request_timestamp DESC
               LIMIT 1""",
            (job_code.upper(), requested_by)
        ).fetchone()
    if row:
        logger.debug(f"TNA report fetched — job:{job_code} user:{requested_by}")
        return row[0]
    logger.debug(f"No TNA report found — job:{job_code} user:{requested_by}")
    return None