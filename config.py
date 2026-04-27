"""
config.py — All branding, labels, and configuration in one place.
Edit this file to customise the portal for your company.
"""

# ─── Company Branding ────────────────────────────────────────────────────────
BRANDING = {
    "company_name": "Fieri Leadership",        # ← Change this
    "tagline": "Training Needs Analysis Database platform",       # ← Change this
    "logo_emoji": "🔍",                    # ← Change to your emoji or remove
    "primary_colour": "#1a56db",           # ← Brand primary colour (hex)
    "accent_colour": "#e74c3c",            # ← Accent / highlight colour
    "version": "1.0.0",
}

# ─── Sector / Industry Options ───────────────────────────────────────────────
SECTOR_OPTIONS = [
    "Financial Services",
    "Healthcare & Life Sciences",
    "Technology",
    "Retail & Consumer",
    "Public Sector & Government",
    "Education",
    "Manufacturing & Engineering",
    "Professional Services",
    "Charity & Non-Profit",
    "Other",
]

# ─── Answer Types ────────────────────────────────────────────────────────────
ANSWER_TYPES = {
    "text":   "Free Text",
    "likert": "Likert Scale",
    "dropdown": "Drop Down"
}

# ─── Likert Scale ─────────────────────────────────────────────────────────────
# Customise labels and values to match your rating framework.
LIKERT_SCALE = [
    {"value": "1", "label": "Strongly Disagree", "emoji": "😞"},
    {"value": "2", "label": "Disagree",           "emoji": "🙁"},
    {"value": "3", "label": "Neutral",            "emoji": "😐"},
    {"value": "4", "label": "Agree",              "emoji": "🙂"},
    {"value": "5", "label": "Strongly Agree",     "emoji": "😊"},
]
# key     → internal page identifier (matches database 'page' column)
# label   → display name shown in tabs and headings
# icon    → emoji shown in tab label
PAGE_CONFIG = {
    "client": {
        "label": "Organisational Profile",
        "icon":  "🏢",
        "description": "Questions for gathering information to create a rich organisational profile for analysis. \n Please provide answers for as many as you can. ",
    },
    "learner": {
        "label": "Learners Population",
        "icon":  "👩‍🎓",
        "description": "Questions related to the target trainee population/cohort. Please provide answers for as many as you can.",
    },
    "individual_char": {
        "label": "Individual Characteristics",
        "icon":  "👔",
        "description": "Questions that capture various individual characteristics of the learning population. Usually this information is received from a survey or similar sources but for this dataset it can represent an Avg of the cohort. Please provide answers for as many as you can.",
    },
}
