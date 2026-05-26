"""
test_db_health.py
─────────────────
Pre-deployment database health check.
Self-contained — no Streamlit, no app imports, only psycopg2.

Usage:
    python test_db_health.py              # full output
    python test_db_health.py --quiet      # failures/warnings only
    echo $?                               # 0 = all passed, 1 = any failure

CI example (GitHub Actions):
    - run: python test_db_health.py
      env:
        SUPABASE_DB_URL: ${{ secrets.SUPABASE_DB_URL }}
"""

import argparse
import os
import sys
import time
from datetime import datetime, timezone

import psycopg2

# ── Colour output ─────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):     print(f"  {GREEN}✓{RESET}  {msg}")
def warn(msg):   print(f"  {YELLOW}⚠{RESET}  {msg}")
def fail(msg):   print(f"  {RED}✗{RESET}  {msg}")
def info(msg):   print(f"  {CYAN}·{RESET}  {msg}")
def header(msg): print(f"\n{BOLD}{msg}{RESET}")


# ── Shared connection (opened once, reused across all checks) ─────────────────

_conn = None

def get_db_url() -> str:
    toml_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        ".streamlit", "secrets.toml"
    )
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # pip install tomli (Python < 3.11)
    with open(toml_path, "rb") as f:
        return tomllib.load(f)["SUPABASE_POSTGRES_SP_URI"].strip()

def open_connection() -> bool:
    global _conn
    url = get_db_url()
    try:
        _conn = psycopg2.connect(url, connect_timeout=10)
        _conn.autocommit = True
        return True
    except Exception:
        return False

def fetchone(sql: str, params: tuple = ()):
    with _conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()

def fetchall(sql: str, params: tuple = ()):
    with _conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


# ── Checks ────────────────────────────────────────────────────────────────────

def check_env() -> bool:
    header("1 · Environment")
    url = get_db_url()
    if not url:
        fail("SUPABASE_DB_URL not found in .streamlit/secrets.toml")
        info("Add this line to .streamlit/secrets.toml:")
        info("  SUPABASE_DB_URL = 'postgresql://...'")
        return False
    if not (url.startswith("postgresql://") or url.startswith("postgres://")):
        warn(f"URL doesn't start with postgresql://  ({url[:50]}…)")
    else:
        ok(f"SUPABASE_DB_URL is set  ({url[:50]}…)")
    return True


def check_connectivity() -> bool:
    header("2 · Connectivity")
    t0 = time.perf_counter()
    if open_connection():
        ms = (time.perf_counter() - t0) * 1000
        ok(f"Connected  ({ms:.0f} ms)")
        return True
    else:
        url = get_db_url()
        fail("Could not connect to the database")
        info("Things to check:")
        info("  · SUPABASE_DB_URL is correct (project ref, password, region)")
        info("  · Use the Session pooler URL — port 6543, not 5432")
        info("  · Supabase project is not paused (free tier auto-pauses)")
        info(f"  · URL used: {url[:60]}…")
        return False


def check_ping() -> bool:
    header("3 · Ping (SELECT 1)")
    t0 = time.perf_counter()
    try:
        row = fetchone("SELECT 1")
        ms = (time.perf_counter() - t0) * 1000
        if row and row[0] == 1:
            ok(f"Round-trip latency: {ms:.0f} ms")
            if ms > 500:
                warn("Latency >500 ms — consider the Supabase session pooler on port 6543")
            return True
        fail(f"Unexpected result from SELECT 1: {row}")
        return False
    except Exception as e:
        fail(f"Ping failed: {e}")
        return False


def check_server_version() -> bool:
    header("4 · Server version")
    try:
        row = fetchone("SELECT version()")
        info(row[0].split(",")[0])   # e.g. PostgreSQL 15.1 on x86_64-pc-linux-gnu
        return True
    except Exception as e:
        fail(f"Could not fetch version: {e}")
        return False


def check_schema() -> bool:
    header("5 · Schema")
    REQUIRED = {"jobs", "questions", "answers"}
    OPTIONAL = {"tna_reports", "research_topics", "research_items"}
    try:
        rows = fetchall(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        )
    except Exception as e:
        fail(f"Could not query pg_tables: {e}")
        return False

    found = {row[0] for row in rows}
    missing_required = REQUIRED - found
    missing_optional = OPTIONAL - found

    if missing_required:
        for t in sorted(missing_required):
            fail(f"Required table missing: {t}")
    else:
        ok(f"Required tables present: {', '.join(sorted(REQUIRED))}")

    for t in sorted(missing_optional):
        warn(f"Optional table not found: {t}  — create it if that feature is in use")

    if missing_optional != OPTIONAL:  # at least some optional tables exist
        found_optional = OPTIONAL - missing_optional
        ok(f"Optional tables present: {', '.join(sorted(found_optional))}")

    extra = found - REQUIRED - OPTIONAL
    if extra:
        info(f"Other tables in public schema: {', '.join(sorted(extra))}")

    return len(missing_required) == 0


def check_row_counts() -> bool:
    header("6 · Row counts")
    tables = ["jobs", "questions", "answers"]
    all_ok = True
    for table in tables:
        try:
            row = fetchone(f"SELECT COUNT(*) FROM {table}")
            n = row[0]
            label = f"{n} row{'s' if n != 1 else ''}"
            if n == 0:
                warn(f"{table:<20} {label}  (table is empty — was the migration run?)")
            else:
                ok(f"{table:<20} {label}")
        except Exception as e:
            fail(f"{table}: {e}")
            all_ok = False
    return all_ok

def check_active_questions() -> bool:
    header("8 · Active questions sanity")
    try:
        row = fetchone("SELECT COUNT(*) FROM questions WHERE is_active = 1")
        n = row[0]
        if n == 0:
            warn("No active questions found (is_active=1) — the portal will show empty pages")
            return False
        ok(f"{n} active question{'s' if n != 1 else ''}")
        return True
    except Exception as e:
        fail(f"Could not query questions: {e}")
        return False


# ── Runner ────────────────────────────────────────────────────────────────────

CHECKS = [
    ("Environment",             check_env,                False),  # (name, fn, needs_conn)
    ("Connectivity",            check_connectivity,       False),
    ("Ping",                    check_ping,               True),
    ("Server version",          check_server_version,     True),
    ("Schema",                  check_schema,             True),
    ("Row counts",              check_row_counts,         True),
    ("Active questions sanity", check_active_questions,   True),
]


def main():
    parser = argparse.ArgumentParser(
        description="QA Portal — pre-deployment database health check"
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Only print failures and warnings"
    )
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass  # CI injects env vars directly

    print(f"\n{BOLD}{'─' * 52}")
    print("  QA Portal · Pre-deployment DB Health Check")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"{'─' * 52}{RESET}")

    results   = {}
    connected = False

    for name, fn, needs_conn in CHECKS:
        if needs_conn and not connected:
            warn(f"Skipping '{name}' — no database connection")
            results[name] = None
            continue
        try:
            passed = fn()
        except Exception as e:
            fail(f"Unexpected error in '{name}': {e}")
            passed = False

        results[name] = passed

        if name == "Connectivity" and passed:
            connected = True

    # ── Summary ───────────────────────────────────────────────────────────────
    header("Summary")
    passed_count  = sum(1 for v in results.values() if v is True)
    warned_count  = sum(1 for v in results.values() if v is False)
    skipped_count = sum(1 for v in results.values() if v is None)

    for name, result in results.items():
        if result is True:
            ok(name)
        elif result is False:
            fail(name)
        else:
            warn(f"{name}  (skipped)")

    print()
    if warned_count == 0 and skipped_count == 0:
        print(f"{GREEN}{BOLD}  All {passed_count} checks passed — safe to deploy.{RESET}\n")
        sys.exit(0)
    else:
        print(
            f"{RED}{BOLD}  {warned_count} check(s) failed, "
            f"{skipped_count} skipped.{RESET}"
            f"  ({passed_count} passed)\n"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()