import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path("qa_portal.db")


def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_code     TEXT PRIMARY KEY,
            client_name  TEXT NOT NULL,
            description  TEXT,
            sector       TEXT,
            created_at   TEXT,
            updated_at   TEXT
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
        cols = [r[1] for r in conn.execute("PRAGMA table_info(questions)").fetchall()]
        if "answer_type" not in cols:
            conn.execute("ALTER TABLE questions ADD COLUMN answer_type TEXT DEFAULT 'text'")
        _seed_default_questions(conn)


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


# ─── Job CRUD ────────────────────────────────────────────────────────────────

def create_job(job_code, client_name, description, sector,cohort_size):
    now = datetime.now().isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO jobs VALUES (?, ?, ?, ?, ?, ?, ?)",
            (job_code.upper(), client_name, description, sector, cohort_size ,now, now),
        )


def get_all_jobs():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT job_code, client_name, sector,cohort_size created_at FROM jobs ORDER BY created_at DESC"
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
            "UPDATE jobs SET client_name=?, description=?, sector=?,cohort_size=?, updated_at=? WHERE job_code=?",
            (client_name, description, sector,cohort_size, now, job_code.upper()),
        )


def delete_job(job_code):
    with get_conn() as conn:
        conn.execute("DELETE FROM jobs WHERE job_code = ?", (job_code.upper(),))
        conn.execute("DELETE FROM answers WHERE job_code = ?", (job_code.upper(),))


# ─── Question CRUD ──────────────────────────────────────────────────────────

def get_questions(page):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, question, position, answer_type FROM questions WHERE page=? AND is_active=1 ORDER BY position",
            (page,),
        ).fetchall()
    return rows


def add_question(page, question_text, answer_type="text"):
    with get_conn() as conn:
        max_pos = conn.execute(
            "SELECT COALESCE(MAX(position), -1) FROM questions WHERE page=?", (page,)
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO questions (page, position, question, answer_type) VALUES (?, ?, ?, ?)",
            (page, max_pos + 1, question_text, answer_type),
        )


def delete_question(question_id):
    with get_conn() as conn:
        conn.execute("UPDATE questions SET is_active=0 WHERE id=?", (question_id,))


def update_question_type(question_id, answer_type):
    with get_conn() as conn:
        conn.execute("UPDATE questions SET answer_type=? WHERE id=?", (answer_type, question_id))


# ─── Answer CRUD ─────────────────────────────────────────────────────────────

def get_answers(job_code, page):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT question_id, answer, mode FROM answers WHERE job_code=? AND page=?",
            (job_code.upper(), page),
        ).fetchall()
    return {r[0]: {"answer": r[1], "mode": r[2]} for r in rows}


def save_answer(job_code, page, question_id, answer, mode="Manual"):
    now = datetime.now().isoformat()
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO answers (job_code, page, question_id, answer, mode, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(job_code, page, question_id)
               DO UPDATE SET answer=excluded.answer, mode=excluded.mode, updated_at=excluded.updated_at""",
            (job_code.upper(), page, question_id, answer, mode, now),
        )


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