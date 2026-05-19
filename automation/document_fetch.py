"""
Generate LLM-ready context documents from Turso SQLite questionnaire data.

Produces:
  1. client_context.md      - Q&A for the 'client' page
  2. learner_context.md     - Q&A for the 'learner' page
  3. likert_context.md      - Likert scores with computed stats & insights

These are plain markdown files intended to be pasted or loaded into an LLM
context window. They are structured but not decorated — no styling, no fluff.

"""

import os
import statistics
from datetime import datetime

from logger import get_logger
from database import fetchall,verify_schema,verify_job_exists,get_job_metadata

logger = get_logger()

# ══════════════════════════════════════════════════════════════════════════════
# 1 & 2 — Q&A context documents (client / learner)
# ══════════════════════════════════════════════════════════════════════════════

def build_qa_context(page: str, job_code: str) -> str:
    lines = []
    lines.append(f"# {page.upper()} QUESTIONNAIRE — Q&A CONTEXT DOCUMENT")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"Page: {page}")
    
    # ── Job metadata ──────────────────────────────────────────────────────
    lines = lines+get_job_metadata(job_code=job_code)
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Fetch questions + answers ─────────────────────────────────────────
    if job_code:
        rows = fetchall("""
            SELECT q.position, q.question, q.answer_type, q.subsection,
                   a.answer, a.mode, a.updated_at
            FROM   questions q
            LEFT JOIN answers a
                   ON a.question_id = q.id
                  AND a.page        = q.page
                  AND a.job_code    = ?
            WHERE  q.page      = ?
              AND  q.is_active  = 1
              AND  q.answer_type != 'likert'
            ORDER  BY q.subsection NULLS FIRST, q.position
        """, (job_code, page))
    else:
        raise ValueError(f"Invalid job code supplied for Q&A context generation: {job_code}")

    if not rows:
        lines.append(f"No questions found for page '{page}'.")
        return "\n".join(lines)

    # ── Group by subsection ───────────────────────────────────────────────
    sections: dict[str, list] = {}
    for row in rows:
        subsection = row[3] or "General"
        sections.setdefault(subsection, []).append(row)

    answered = sum(1 for r in rows if r[4])
    lines.append(f"## Summary")
    lines.append(f"- Total questions: {len(rows)}")
    lines.append(f"- Answered: {answered}")
    lines.append(f"- Unanswered: {len(rows) - answered}")
    lines.append(f"- Sections: {', '.join(sections.keys())}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Q&A content ───────────────────────────────────────────────────────
    lines.append("## Questions & Answers")
    lines.append("")

    for subsection, questions in sections.items():
        lines.append(f"### {subsection}")
        lines.append("")

        for position, question, answer_type, _, answer, mode, updated_at in questions:
            lines.append(f"**Q{position}: {question}**")
            if answer_type and answer_type not in ("text", "likert"):
                lines.append(f"_(Answer type: {answer_type})_")
            if answer and answer.strip():
                lines.append(f"A: {answer.strip()}")
            else:
                lines.append("A: [No answer recorded]")
            if mode and mode != "Manual":
                lines.append(f"_(Source: {mode})_")
            lines.append("")

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# 3 — Likert scale context document
# ══════════════════════════════════════════════════════════════════════════════

LIKERT_LABELS = {1: "Strongly Disagree", 2: "Disagree", 3: "Neutral", 4: "Agree", 5: "Strongly Agree"}

def rating_label(avg: float) -> str:
    if avg >= 4.5: return "Exceptional"
    if avg >= 3.5: return "Positive"
    if avg >= 2.5: return "Mixed / Neutral"
    return "Needs Attention"


def build_likert_context(job_code: str) -> str:
    lines = []

    lines.append("# LIKERT SCALE SCORES — CONTEXT DOCUMENT")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    lines = lines + get_job_metadata(job_code=job_code)
    lines.append("")
    lines.append("Scale: 1 = Strongly Disagree, 2 = Disagree, 3 = Neutral, 4 = Agree, 5 = Strongly Agree")
    lines.append("")
    lines.append("---")
    lines.append("")
 
    # ── Fetch all Likert answers ──────────────────────────────────────────
    rows = fetchall("""
        SELECT q.id, q.page, q.position, q.question, q.subsection,
               a.answer, a.job_code
        FROM   questions q
        JOIN   answers a ON a.question_id = q.id AND a.job_code = ?
        WHERE  q.answer_type = 'likert'
          AND  q.is_active   = 1
          AND  a.answer IS NOT NULL
        ORDER  BY q.page, q.subsection NULLS FIRST, q.position
    """, (job_code,))
 
    if not rows:
        lines.append("No Likert scale answers found.")
        return "\n".join(lines)
 
    # ── Parse & structure scores ──────────────────────────────────────────
    # { page: { subsection: { question: [scores] } } }
    data: dict = {}
    all_scores: list[float] = []
 
    for q_id, page, position, question, subsection, answer, jc in rows:
        try:
            score = float(answer)
            if score not in (1, 2, 3, 4, 5):
                continue
        except (ValueError, TypeError):
            continue
 
        sub = subsection or "General"
        data.setdefault(page, {}).setdefault(sub, {}).setdefault(question, []).append(score)
        all_scores.append(score)
 
    # ── Overall stats ─────────────────────────────────────────────────────
    overall_avg = statistics.mean(all_scores)
    overall_std = statistics.stdev(all_scores) if len(all_scores) > 1 else 0.0
    overall_med = statistics.median(all_scores)
 
    lines.append("## Overall Statistics")
    lines.append(f"- Total responses: {len(all_scores)}")
    lines.append(f"- Overall average: {overall_avg:.2f} / 5.00")
    lines.append(f"- Median: {overall_med:.1f}")
    lines.append(f"- Std deviation: {overall_std:.2f}")
    lines.append(f"- Overall rating: {rating_label(overall_avg)}")
 
    # Score distribution
    dist = {k: [int(s) for s in all_scores].count(k) for k in range(1, 6)}
    dist_str = ", ".join(f"{LIKERT_LABELS[k]}: {dist[k]}" for k in range(1, 6))
    lines.append(f"- Response distribution: {dist_str}")
    lines.append("")
    lines.append("---")
    lines.append("")
 
    # ── Per-page & per-subsection breakdown ───────────────────────────────
    lines.append("## Detailed Scores by Page & Section")
    lines.append("")
 
    all_q_avgs = []  # collected for final recommendations
 
    for page, subsections in data.items():
        page_scores = [s for sub in subsections.values() for qs in sub.values() for s in qs]
        page_avg    = statistics.mean(page_scores)
 
        lines.append(f"### Page: {page.title()}")
        lines.append(f"Page average: {page_avg:.2f} / 5.00 — {rating_label(page_avg)}")
        lines.append(f"Responses: {len(page_scores)}")
        lines.append("")
 
        for subsection, questions in subsections.items():
            sub_scores = [s for qs in questions.values() for s in qs]
            sub_avg    = statistics.mean(sub_scores)
            sub_std    = statistics.stdev(sub_scores) if len(sub_scores) > 1 else 0.0
 
            lines.append(f"#### Section: {subsection}")
            lines.append(f"Section average: {sub_avg:.2f} / 5.00 — {rating_label(sub_avg)}")
            lines.append(f"Std deviation: ±{sub_std:.2f} | Responses: {len(sub_scores)}")
            lines.append("")
 
            for question, scores in questions.items():
                q_avg  = statistics.mean(scores)
                q_std  = statistics.stdev(scores) if len(scores) > 1 else 0.0
                q_dist = {k: scores.count(k) for k in range(1, 6)}
                dist_parts = " | ".join(
                    f"{LIKERT_LABELS[k]}: {q_dist[k]}"
                    for k in range(1, 6) if q_dist[k] > 0
                )
 
                lines.append(f"**Q: {question}**")
                lines.append(f"- Average: {q_avg:.2f} / 5.00 ({rating_label(q_avg)})")
                lines.append(f"- Std deviation: ±{q_std:.2f}")
                lines.append(f"- Distribution: {dist_parts}")
                lines.append(f"- Individual scores: {sorted(scores)}")
                lines.append("")
 
                all_q_avgs.append((page, subsection, question, q_avg, len(scores)))
 
    # ── Key insights ──────────────────────────────────────────────────────
    all_q_avgs.sort(key=lambda x: x[3])
    bottom5 = all_q_avgs[:5]
    top5    = all_q_avgs[-5:][::-1]
 
    lines.append("---")
    lines.append("")
    lines.append("## Key Insights")
    lines.append("")
 
    lines.append("### Highest Scoring Areas")
    for page, sub, q, avg, n in top5:
        lines.append(f"- [{page} > {sub}] {q}")
        lines.append(f"  Score: {avg:.2f}/5.00 ({rating_label(avg)}) — {n} response(s)")
    lines.append("")
 
    lines.append("### Lowest Scoring Areas")
    for page, sub, q, avg, n in bottom5:
        lines.append(f"- [{page} > {sub}] {q}")
        lines.append(f"  Score: {avg:.2f}/5.00 ({rating_label(avg)}) — {n} response(s)")
    lines.append("")
 
    # Variance flags — questions with high spread (std > 1.2)
    high_variance = [(pg, s, q, a, std) for pg, s, q, a, n in all_q_avgs
                     for scores in [data[pg][s][q]]
                     for std in [statistics.stdev(scores) if len(scores) > 1 else 0.0]
                     if std > 1.2]
 
    if high_variance:
        lines.append("### High Variance Questions (std > 1.2 — divided opinion)")
        for pg, sub, q, avg, std in sorted(high_variance, key=lambda x: -x[4]):
            lines.append(f"- [{page} > {sub}] {q}")
            lines.append(f"  Avg: {avg:.2f} | Std: ±{std:.2f} — responses are polarised")
        lines.append("")
 
    lines.append("---")
    lines.append(f"End of document. Job: {job_code or 'All'} | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
 
    return "\n".join(lines)



def generate_documents_from_db(job_code:str)->str:

    # Getting Turso Connection
    logger.debug(f"Connecting to database for fetching job documents…")
    logger.debug("Connected.\n")

    # Verifying Schema
    logger.debug("Verifying schema…")
    verify_schema()
    
    # Verifying the supplied job
    logger.debug("Verifying job exists…")
    verify_job_exists(job_code)
    
    # After verification only make data directory
    out_dir  = os.getenv("DATA_DIR","/data")+f"/{job_code}"
    os.makedirs(out_dir, exist_ok=True)
    
    suffix = f"_{job_code}" if job_code else ""

    for page in ("client", "learner"):
        logger.debug(f"Building {page} Q&A context…")
        content = build_qa_context(page, job_code)
        path = os.path.join(out_dir, f"{page}_context{suffix}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"  ✓  {path}  ({len(content):,} chars)")

    logger.debug("Building Likert insights context…")
    content = build_likert_context(job_code)
    path = os.path.join(out_dir, f"likert_context{suffix}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info(f" ✓  Document written to {path}  ({len(content):,} chars)")
