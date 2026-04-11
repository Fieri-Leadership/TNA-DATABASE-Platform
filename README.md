# QA Analysis Portal

A lightweight Streamlit web app for structured Q&A analysis across client engagements.

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. (Optional) Set your Anthropic API key for AI mode
export ANTHROPIC_API_KEY=sk-ant-...

# 3. Run the app
streamlit run app.py
```

The app will open at `http://localhost:8501` and create a `qa_portal.db` SQLite file automatically.

---

## Project Structure

```
qa_portal/
├── app.py            # Entry point — page config & layout
├── ui.py             # All Streamlit rendering logic
├── database.py       # SQLite CRUD operations
├── ai_helper.py      # Claude API integration for Auto mode
├── config.py         # ← Customise branding & settings here
├── style.css         # ← Customise colours & fonts here
├── requirements.txt
└── qa_portal.db      # Auto-created on first run
```

---

## Customisation

### 1. Branding (config.py)
Edit `BRANDING` in `config.py`:
```python
BRANDING = {
    "company_name": "Your Company Name",
    "tagline":      "QA Analysis Portal",
    "logo_emoji":   "🔍",
    "primary_colour": "#1a56db",   # Your brand colour
    "accent_colour":  "#e74c3c",
}
```

### 2. Colours (style.css)
Update the CSS variables at the top of `style.css`:
```css
:root {
    --primary:      #1a56db;   /* Main brand colour */
    --primary-dark: #1342b0;   /* Hover state */
    --accent:       #e74c3c;   /* Highlights */
}
```

### 3. Pages & Questions
- Page names/icons are configured in `config.py → PAGE_CONFIG`
- Questions can be added/removed via Admin → Manage Questions in the UI
- Default questions are seeded automatically on first run

### 4. Sectors
Edit `SECTOR_OPTIONS` in `config.py` to match your industry verticals.

---

## AI (Automatic) Mode

In Automatic mode, clicking **⚡ Generate All** calls the Claude API to draft
answers for all questions on a page, using the job's context (client name, sector,
description) as a prompt.

**Requirements:**
- Set `ANTHROPIC_API_KEY` as an environment variable
- Or add it to a `.env` file and load with `python-dotenv`

All AI-generated answers are tagged `[AI]` and remain fully editable.

---

## Deployment

For a web portal, deploy with:
- **Streamlit Community Cloud** (free, connects to GitHub)
- **Docker** + any cloud provider
- **Heroku / Railway / Render** (simple, low-cost)

For production, replace SQLite with PostgreSQL using `psycopg2` and
update `get_conn()` in `database.py`.

---

## Database

The app uses SQLite with three tables:
- `jobs` — job codes and client metadata
- `questions` — question bank per page (shared across all jobs)
- `answers` — answers per job × page × question

To reset the database: delete `qa_portal.db` and restart the app.
