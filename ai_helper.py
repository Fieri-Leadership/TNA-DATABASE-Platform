"""
ai_helper.py
Handles automatic answer generation via Claude API.
Replace ANTHROPIC_API_KEY in your environment or .env file.
"""

import os
import requests


ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-20250514"


def generate_answers(job_details: dict, questions: list[str], page: str) -> list[str]:
    """
    Generate answers for a list of questions given job context.

    Args:
        job_details: dict with keys job_code, client_name, description, sector
        questions:   list of question strings
        page:        one of 'client', 'learner', 'manager'

    Returns:
        list of answer strings, same length as questions
    """
    if not ANTHROPIC_API_KEY:
        return ["[ERROR] ANTHROPIC_API_KEY not set in environment."] * len(questions)

    audience_map = {
        "client": "Client / Commissioning Organisation",
        "learner": "Learners / Participants",
        "manager": "Line Managers",
    }

    numbered = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))

    system_prompt = (
        "You are an expert learning & development analyst. "
        "You are completing a structured Q&A analysis document for a client project. "
        "Respond ONLY with a JSON array of strings — one answer per question, in order. "
        "Each answer should be concise (2-4 sentences), professional, and grounded in the context provided. "
        "Do not include any preamble, markdown, or additional keys."
    )

    user_prompt = (
        f"Project context:\n"
        f"- Job Code: {job_details.get('job_code', 'N/A')}\n"
        f"- Client: {job_details.get('client_name', 'N/A')}\n"
        f"- Sector: {job_details.get('sector', 'N/A')}\n"
        f"- Description: {job_details.get('description', 'N/A')}\n\n"
        f"Audience perspective: {audience_map.get(page, page)}\n\n"
        f"Answer each of the following questions:\n{numbered}"
    )

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    payload = {
        "model": MODEL,
        "max_tokens": 2000,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }

    try:
        resp = requests.post(API_URL, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        text = data["content"][0]["text"].strip()

        import json
        answers = json.loads(text)
        if isinstance(answers, list) and len(answers) == len(questions):
            return [str(a) for a in answers]
        return ["[Parse error] Unexpected response format."] * len(questions)

    except requests.exceptions.Timeout:
        return ["[ERROR] Request timed out. Try again."] * len(questions)
    except Exception as e:
        return [f"[ERROR] {str(e)}"] * len(questions)
