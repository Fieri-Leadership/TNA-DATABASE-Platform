"""
database_postgres.py
────────────────────
Supabase / PostgreSQL backend — drop-in replacement for database_sqlite.py

Requirements:
    pip install psycopg2-binary python-dotenv

Environment variables (add to .env or your deployment secrets):
    SUPABASE_DB_URL  — full Postgres connection string, e.g.
        postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
        (use the *Session* pooler URL from Supabase → Project Settings → Database → Connection string)
"""

import os
import sys
from contextlib import contextmanager
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras          # RealDictCursor (optional, used in helpers)
from psycopg2 import pool as pg_pool
import streamlit as st

from logger import get_logger

logger = get_logger()

# ─── Load environment ─────────────────────────────────────────────────────────

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    logger.warning("python-dotenv not installed — relying on real environment variables.")

SUPABASE_DB_URL = os.environ.get("SUPABASE_POSTGRES_SP_URI", "").strip()

if not SUPABASE_DB_URL:
    logger.error(
        "SUPABASE_DB_URL is not set. "
        "Add it to your .env file or deployment environment and restart."
    )
    sys.exit(1)


# ─── Connection pool (created once per Streamlit process) ────────────────────
#
#   min/max connections are conservative defaults — tune to your Supabase plan.
#   Supabase free tier allows ~20 direct connections; the session pooler on
#   port 6543 supports many more.

@st.cache_resource
def _get_pool() -> pg_pool.ThreadedConnectionPool:
    logger.info("Creating Postgres connection pool…")
    try:
        p = pg_pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=SUPABASE_DB_URL,
            connect_timeout=10,
        )
        logger.info("Postgres connection pool ready.")
        return p
    except Exception as e:
        logger.error(f"Could not create connection pool: {e}", exc_info=True)
        raise


# ─── Context manager — borrow / return a connection ──────────────────────────

@contextmanager
def get_conn():
    """
    Yields a psycopg2 connection from the pool.
    Commits on clean exit, rolls back on exception, always returns connection
    to the pool.
    """
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"DB error (rolled back): {e}", exc_info=True)
        raise
    finally:
        pool.putconn(conn)


# ─── Low-level helpers ────────────────────────────────────────────────────────
#
#   Postgres uses %s placeholders (not ? like SQLite).
#   These two helpers are the only place that difference matters — every
#   query string above this line already uses %s.

def fetchall(sql: str, params: tuple = ()) -> list:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def fetchone(sql: str, params: tuple = ()) -> tuple | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()


def execute(sql: str, params: tuple = ()) -> None:
    """Run a statement that returns no rows (INSERT / UPDATE / DELETE)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)


# ─── Schema verification ──────────────────────────────────────────────────────

def verify_schema() -> None:
    """Check that all required tables exist; exit with a clear message if not."""
    REQUIRED_TABLES = {"jobs", "questions", "answers"}
    try:
        rows = fetchall(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        )
    except Exception as e:
        logger.error(f"Could not query database schema: {e}")
        logger.error("→ Check that SUPABASE_DB_URL is correct and the DB is reachable.")
        sys.exit(1)

    found_tables = {row[0] for row in rows}
    missing = REQUIRED_TABLES - found_tables

    if missing:
        logger.error("Connected to Postgres but required tables are missing.")
        logger.error(f"  Expected : {', '.join(sorted(REQUIRED_TABLES))}")
        logger.error(f"  Found    : {', '.join(sorted(found_tables)) or '(none)'}")
        logger.error(f"  Missing  : {', '.join(sorted(missing))}")
        logger.error("→ Verify you are pointing at the correct Supabase project.")
        sys.exit(1)

    logger.info(f"Schema OK — tables verified: {', '.join(sorted(REQUIRED_TABLES))}")


# ─── Timestamp helper ─────────────────────────────────────────────────────────

def _now() -> str:
    """ISO-8601 UTC timestamp string — consistent with the old SQLite code."""
    return datetime.now(timezone.utc).isoformat()


# ─── Job CRUD ─────────────────────────────────────────────────────────────────

def create_job(job_code: str, client_name: str, description: str,
               sector: str, cohort_size: int) -> None:
    logger.info(f"Creating job: {job_code.upper()} — {client_name}")
    now = _now()
    try:
        execute(
            "INSERT INTO jobs VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (job_code.upper(), client_name, description, sector, now, now, cohort_size),
        )
    except Exception as e:
        logger.error(f"Failed to create job {job_code}: {e}", exc_info=True)
        raise


def get_all_jobs() -> list:
    return fetchall(
        "SELECT job_code, client_name, sector, cohort_size FROM jobs ORDER BY created_at DESC"
    )


def get_job(job_code: str) -> tuple | None:
    return fetchone(
        "SELECT * FROM jobs WHERE job_code = %s",
        (job_code.upper(),),
    )


def update_job(job_code: str, client_name: str, description: str,
               sector: str, cohort_size: int) -> None:
    execute(
        """UPDATE jobs
              SET client_name=%s, description=%s, sector=%s,
                  updated_at=%s, cohort_size=%s
            WHERE job_code=%s""",
        (client_name, description, sector, _now(), cohort_size, job_code.upper()),
    )


def delete_job(job_code: str) -> None:
    logger.warning(f"Deleting job and all answers: {job_code}")
    try:
        # Single round-trip: delete answers first (FK), then the job
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM answers WHERE job_code = %s", (job_code.upper(),)
                )
                cur.execute(
                    "DELETE FROM jobs WHERE job_code = %s", (job_code.upper(),)
                )
    except Exception as e:
        logger.error(f"Failed to delete job {job_code}: {e}", exc_info=True)
        raise


def verify_job_exists(job_code: str) -> None:
    row = fetchone(
        "SELECT job_code, client_name FROM jobs WHERE job_code = %s",
        (job_code,),
    )
    if not row:
        available = fetchall(
            "SELECT job_code, client_name FROM jobs ORDER BY job_code"
        )
        logger.error(f"Job code '{job_code}' not found in the jobs table.")
        if available:
            for jc, name in available:
                logger.error(f"    - {jc}  ({name})")
        else:
            logger.error("  The jobs table is empty — no jobs have been created yet.")
        sys.exit(1)
    logger.debug(f"Job OK — '{job_code}' found: {row[1]}")


def get_job_metadata(job_code: str) -> list[str]:
    job_row = fetchone(
        "SELECT job_code, client_name, description, sector, cohort_size"
        "  FROM jobs WHERE job_code = %s",
        (job_code,),
    )
    lines = []
    if job_row:
        job_code_val, client_name, description, sector, cohort_size = job_row
        lines.append(f"- Job Code: {job_code_val}")
        lines.append(f"- Client: {client_name}")
        lines.append(f"- Sector: {sector or 'N/A'}")
        lines.append(f"- Cohort Size: {cohort_size or 'N/A'}")
        if description:
            lines.append(f"- Description: {description}")
    return lines


# ─── Question CRUD ────────────────────────────────────────────────────────────

def get_questions(page: str) -> list:
    return fetchall(
        """SELECT id, question, position, subsection, answer_type
             FROM questions
            WHERE page=%s AND is_active=1
            ORDER BY position""",
        (page,),
    )


def add_question(page: str, question_text: str, subsection_text: str,
                 answer_type: str = "text") -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(MAX(position), -1) FROM questions WHERE page=%s",
                (page,),
            )
            max_pos = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO questions (page, position, question, subsection, answer_type)
                   VALUES (%s, %s, %s, %s, %s)""",
                (page, max_pos + 1, question_text, subsection_text, answer_type),
            )


def delete_question(question_id: int) -> None:
    execute("UPDATE questions SET is_active=0 WHERE id=%s", (question_id,))


def update_question_type(question_id: int, answer_type: str) -> None:
    execute(
        "UPDATE questions SET answer_type=%s WHERE id=%s",
        (answer_type, question_id),
    )


def update_question(question_id: int, question_text: str, subsection: str) -> None:
    execute(
        "UPDATE questions SET question=%s, subsection=%s WHERE id=%s",
        (question_text, subsection, question_id),
    )


# ─── Answer CRUD ──────────────────────────────────────────────────────────────

def get_answers(job_code: str, page: str) -> dict:
    rows = fetchall(
        "SELECT question_id, answer, mode FROM answers WHERE job_code=%s AND page=%s",
        (job_code.upper(), page),
    )
    return {r[0]: {"answer": r[1], "mode": r[2]} for r in rows}


def save_answer(job_code: str, page: str, question_id: int,
                answer: str, mode: str = "Manual") -> None:
    """Upsert an answer row — Postgres native ON CONFLICT … DO UPDATE."""
    try:
        execute(
            """INSERT INTO answers (job_code, page, question_id, answer, mode, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s)
               ON CONFLICT (job_code, page, question_id)
               DO UPDATE SET
                   answer     = EXCLUDED.answer,
                   mode       = EXCLUDED.mode,
                   updated_at = EXCLUDED.updated_at""",
            (job_code.upper(), page, question_id, answer, mode, _now()),
        )
    except Exception as e:
        logger.error(
            f"Failed to save answer — job:{job_code} q:{question_id}: {e}",
            exc_info=True,
        )
        raise


def clear_answers(job_code: str, page: str) -> None:
    execute(
        "DELETE FROM answers WHERE job_code=%s AND page=%s",
        (job_code.upper(), page),
    )


# ─── Research tables ──────────────────────────────────────────────────────────
#
#   Postgres does not support executescript().
#   Each CREATE TABLE is run separately inside one transaction.

def init_research_tables() -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS research_topics (
                    id         SERIAL PRIMARY KEY,
                    name       TEXT NOT NULL,
                    created_at TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS research_items (
                    id         SERIAL PRIMARY KEY,
                    topic_id   INTEGER NOT NULL REFERENCES research_topics(id),
                    title      TEXT NOT NULL,
                    link       TEXT,
                    summary    TEXT,
                    content    TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)


def get_research_topics() -> list:
    return fetchall("SELECT id, name FROM research_topics ORDER BY name")


def add_research_topic(name: str) -> None:
    execute(
        "INSERT INTO research_topics (name, created_at) VALUES (%s, %s)",
        (name, _now()),
    )


def delete_research_topic(topic_id: int) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM research_items WHERE topic_id=%s", (topic_id,))
            cur.execute("DELETE FROM research_topics WHERE id=%s", (topic_id,))


def get_research_items(topic_id: int) -> list:
    return fetchall(
        "SELECT id, title, link, summary, content"
        "  FROM research_items WHERE topic_id=%s ORDER BY title",
        (topic_id,),
    )


def add_research_item(topic_id: int, title: str, link: str,
                      summary: str, content: str) -> None:
    now = _now()
    execute(
        """INSERT INTO research_items
               (topic_id, title, link, summary, content, created_at, updated_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (topic_id, title, link, summary, content, now, now),
    )


def update_research_item(item_id: int, title: str, link: str,
                         summary: str, content: str) -> None:
    execute(
        """UPDATE research_items
              SET title=%s, link=%s, summary=%s, content=%s, updated_at=%s
            WHERE id=%s""",
        (title, link, summary, content, _now(), item_id),
    )


def delete_research_item(item_id: int) -> None:
    execute("DELETE FROM research_items WHERE id=%s", (item_id,))


# ─── TNA Report ───────────────────────────────────────────────────────────────

def save_tna_report(job_code: str, requested_by: str, report_content: str) -> None:
    execute(
        """INSERT INTO tna_reports (requested_by, request_timestamp, report_content, job_code)
           VALUES (%s, %s, %s, %s)""",
        (requested_by, _now(), report_content, job_code.upper()),
    )
    logger.info(f"TNA report saved — job:{job_code} user:{requested_by}")


def get_latest_tna_report(job_code: str, requested_by: str) -> str | None:
    row = fetchone(
        """SELECT report_content FROM tna_reports
            WHERE job_code=%s AND requested_by=%s
            ORDER BY request_timestamp DESC
            LIMIT 1""",
        (job_code.upper(), requested_by),
    )
    if row:
        logger.debug(f"TNA report fetched — job:{job_code} user:{requested_by}")
        return row[0]
    logger.debug(f"No TNA report found — job:{job_code} user:{requested_by}")
    return None