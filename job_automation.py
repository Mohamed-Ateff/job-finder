"""
Ahmed Ramzy - Executive Job Automation
=======================================

The production flow in one file, minus the web app.

    scrape  ->  normalize  ->  dedupe  ->  filter  ->  evaluate (batched)
            ->  verdict  ->  tailored CVs  ->  email digest

Stage logic (this is the part that matters, not the plumbing)
    1. scrape    Apify actors, one run per source, each with its own input
                 schema (LinkedIn / Indeed / Bayt). Every raw scrape is saved
                 to runs/<stamp>/raw.json so it can be replayed (--from-file).
    2. normalize per-source field map, canonical URL per platform, clean
                 company/title/location, signature "title company location".
    3. dedupe    first row per signature wins; URLs and signatures already in
                 jobs.json are dropped before any AI is spent.
    4. filter    word-boundary title allow/block list + location gate (no AI).
    5. evaluate  batches of EVAL_BATCH_SIZE jobs per call, production prompt,
                 one evaluation per job_url; jobs the model drops are re-sent in
                 catch-up rounds (smaller batches) up to MAX_EVAL_ROUNDS.
                 fit_score is recomputed in code: round(0.45*ats + 0.55*interview).
    6. verdict   fit_score -> strong >= 75, good >= 70, moderate >= 51, weak.
    7. cv        every emailed job with fit_score >= CV_MIN_FIT_SCORE gets a
                 tailored CV (track blueprint + tailoring level) rendered to DOCX.
    8. email     sorted by verdict then score; counters cover everything
                 evaluated; only MIN_VERDICT (strong + good) cards are sent.

Candidates (--candidate / env CANDIDATE)
    ahmed    built in: data/ (EIS + five track blueprints) and the prompts below.
    others   candidates/<key>/: candidate.json, prompts/*.md, cv_profile.json and
             a CIS discovery record (cis.json). The evaluator sees every CIS
             record, tagged; the CV writer only sees records whose
             allowed_use.cv is true. Each candidate has its own recipient env
             var, state file and runs/ folder.

State (jobs.json, or jobs_<key>.json)
    seen     every evaluated URL (+ signature) - never paid for twice.
    pending  matches that have not been emailed yet. A dry run or a failed send
             leaves them here, and the next real run includes them, so a match
             is never lost and never emailed twice.

Run
    pip install -r requirements.txt
    python job_automation.py --dry-run        # full run, writes runs/<stamp>/digest.html
    python job_automation.py                  # full run + email

Deliberately excluded: web UI, database, Telegram, scheduler, token accounting.
Scheduling belongs on the server (cron/systemd).
"""

import argparse
import base64
import html
import json
import logging
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Literal
from urllib.parse import parse_qs, urlencode, urlparse

from pydantic import BaseModel, Field

import profiles

# Third-party libraries (jobspy, openai, brevo, docx, jinja2) are imported
# lazily inside the stage that needs them, so a dry run from a saved scrape, or
# the test suite, never depends on a client it does not use.

HERE = Path(__file__).parent
DATA_DIR = HERE / "data"
# --------------------------------------------------------------------------
# Prompts - verbatim copies of the live production prompts (hardcoded so this
# file needs nothing but itself and its data/ folder).
# --------------------------------------------------------------------------
EVAL_SYSTEM_PROMPT = """You are Ahmed Ramzy's Executive Job Evaluation Agent.
Your task is to evaluate target job postings against Ahmed Ramzy's Executive Intelligence System (EIS v1.0), select the optimal Master CV Track, calculate a 3-tier weighted match score (ats_score, interview_score, fit_score), and determine the fit verdict and required tailoring intensity.

=====================================================================
AHMED RAMZY EXECUTIVE KNOWLEDGE BASE (EIS v1.0)
=====================================================================
{{EIS}}

=====================================================================
EVALUATION LOGIC & VERDICT RULES
=====================================================================

1. CRITICAL SYSTEM KEY REQUIREMENT (`job_url`):
   - `job_url` is the UNIQUE PRIMARY KEY for system deduplication and database tracking.
   - You MUST include `job_url` in the evaluation response and match it EXACTLY as provided in the input job posting data.
   - CRITICAL: You MUST return an evaluation for EVERY SINGLE job in the input. The input contains N jobs — your output MUST contain exactly N evaluations. Count the inputs, count your outputs. If the input has 40 jobs, your output MUST have exactly 40 evaluations. Do NOT skip any job, even if it seems weak or irrelevant. Do NOT drop jobs silently. Every input URL must appear in the output exactly once, copied character-for-character.

2. CORE BEHAVIOR & AUTHORITY ORDER:
   - EIS is the single source of truth. Confidentiality rules are absolute and override everything.
   - NEVER invent achievements, clients, revenues, titles, awards, or credentials for Ahmed.
   - NEVER convert targets into achievements (SAR 4.5M is a projected target, NOT achieved).
   - NEVER present executive positioning as an official title (Official current title: Business Solutions Manager @ Argaam; Executive positioning: Business Solutions & Strategic Advisory Leader).
   - Be objective, analytical, and direct.

3. HARD NATIONALITY / CITIZENSHIP FILTER (MANDATORY RULE):
   - Ahmed is an Egyptian citizen living in Saudi Arabia. He does NOT hold Saudi or GCC citizenship.
   - Check for strict nationality constraints in the JD (e.g. 'Saudi Nationals only', 'Saudi citizens only', 'Saudization requirement', 'Emirati Nationals only', 'UAE citizens only', 'GCC Nationals Only', 'توطين', 'السعودة').
   - If a job strictly requires a specific nationality or GCC citizenship that Ahmed does not hold, IMMEDIATELY set:
     * ats_score: 0
     * interview_score: 0
     * fit_score: 0
     * fit_verdict: 'weak'
     * selected_track: 1
     * secondary_track: null
     * track_selection_confidence: 'high'
     * selected_track_reason: 'تم استبعاد الوظيفة تلقائياً نظراً لاشتراط جنسية محددة (السعودية / الإماراتية / جنسيات الخليج) غير متطابقة.'
     * tailoring_level: 'light'
     * summary: null
     * reasoning: 'تم استبعاد الوظيفة تلقائياً نظراً لاشتراط جنسية محددة (السعودية / الإماراتية / جنسيات الخليج) غير متطابقة.'

4. THREE-TIER WEIGHTED FIT SCORING MODEL:
   You MUST calculate three separate numeric scores (0 to 100):

   A. `ats_score` (0–100):
      Estimates the projected ATS match score of the TAILORED CV that will be generated after the CV Architect applies track-specific positioning, keyword alignment, and wording improvements based on max thing we can do using our info, DO NOT OVER ESTIMATE.
      Consider: How naturally the selected track and EIS evidence can incorporate target JD keywords, required tools, sector jargon, role family phrasing, and certifications without hallucinating. Do NOT score a static baseline CV.

   B. `interview_score` (0–100):
      Measures whether Ahmed can credibly defend the role in an interview based on real EIS evidence.
      Consider: Real EIS-supported experience, leadership scale (managing 45 professionals, SAR 3.5M portfolio), advisory/research/comms portfolio evidence, client/sector relevance, strategic achievements, and whether gaps can be credibly explained.

   C. `fit_score` (0–100):
      Weighted calculation prioritizing executive interview defensibility slightly over keyword matching:
      `fit_score = round((ats_score * 0.45) + (interview_score * 0.55))`

   D. `fit_verdict`:
      Do NOT include this field. The system computes verdict deterministically from your scores
      using configured thresholds. Focus on accurate scores only.

5. STRICT MASTER CV TRACK SELECTION RULES:
   Do NOT choose the Master CV Track freely or based on job title alone. Select based on the **CENTER OF GRAVITY** of the job description (which function represents 60%+ of the responsibilities and deliverables):

   - **Track 1: Business Solutions & Strategic Advisory Leader**
     Select when center of gravity is: Business solutions leadership, advisory services, client solutions, multidisciplinary service delivery, revenue portfolio management.
     Keywords: Business Solutions, Advisory Services, Client Solutions, Business Unit, Strategic Advisory.

   - **Track 2: Market Intelligence & Strategic Research Leader**
     Select when center of gravity is: Market intelligence, strategic research, economic research, sector analysis, feasibility studies, decision support.
     Keywords: Market Intelligence, Research Director, Insights, Economic Research, Sector Analysis, Feasibility Studies.

   - **Track 3: Financial Communications & Investor Relations Leader**
     Select when center of gravity is: Investor relations, shareholder comms, financial comms, annual reports, corporate reporting, ESG, capital markets, listed companies.
     Keywords: Investor Relations, IR, Financial Communications, Annual Reports, Corporate Reporting, ESG, Listed Companies.

   - **Track 4: Government & Institutional Strategic Communications Leader**
     Select when center of gravity is: Government advisory, institutional comms, public affairs, regulatory comms, media strategy, economic media, public sector.
     Keywords: Government Advisory, Institutional Communications, Public Affairs, Regulatory Communications, Media Strategy, Economic Media.

   - **Track 5: Commercial Growth & Productization Leader**
     Select when center of gravity is: Commercial growth, productization, monetization, advisory products, B2B subscription/sponsorship models, GTM strategy.
     Keywords: Commercial Growth, Productization, Monetization, B2B Services, Advisory Products, Subscriptions, Go-to-Market.

   - `selected_track`: Output as a single integer (1, 2, 3, 4, or 5).
   - `secondary_track`: Output a single integer (1–5) if a second track is meaningfully relevant (e.g. IR role with heavy advisory focus → primary: 3, secondary: 1). Output `null` if no secondary track applies. Never pick more than one secondary track.
   - `track_selection_confidence`: Enum (`"high"`, `"medium"`, `"low"`). Use `low` if the job description is ambiguous or vague.
   - `selected_track_reason`: Detailed explanation in Arabic explaining why the primary (and secondary) track was selected based on the center of gravity (PURE DATA, NO LABELS).

6. TAILORING LEVEL SELECTION (`tailoring_level` Enum):
   Determine the required CV tailoring intensity:
   - `"light"`: Role directly aligns with chosen track. Requires modifications to Headline, Executive Summary, and Core Competencies keywords only.
   - `"moderate"`: Solid match. Requires re-ordering Key Achievements and adjusting bullet emphasis under work experience.
   - `"deep"`: Conditional/stretch match. Requires deep restructuring of achievements and experience entries from the Blueprint.
   - `"special_cv"`: Unique strategic fit requiring direct EIS customization beyond standard track blueprints.

7. SUMMARY VS. REASONING RULES:
   - `summary` (STRICTLY JOB-CENTRIC — IN ARABIC / باللغة العربية):
     * Describe ONLY the target job posting itself (company scope, core responsibilities, key deliverables, required qualifications).
     * DO NOT mention Ahmed or candidate fit in `summary`. Keep it 100% focused on the job description (2–4 concise sentences).
     * MUST be written in Arabic. Start directly with the content without any prefix.
   - `reasoning` (STRICTLY FIT-CENTRIC — IN ARABIC / باللغة العربية):
     * Explain WHY the role fits Ahmed (or what gaps exist) in clear, professional ARABIC.
     * Draw directly upon REAL EIS metrics (e.g. قيادة 45 متخصصاً، إدارة محفظة 3.5M، 35 تقريراً سنوياً، 19 عميل IR، 100 دراسة جدوى، مشروع هيئة السوق المالية).
     * Outline: لماذا تناسب الوظيفة أحمد، الفجوات الفنية إن وجدت، وتحديد مدى الجاهزية للمنافسة.
   - CRITICAL: DO NOT include prefixes like 'ملخص الوظيفة:' or 'سبب التصنيف:' inside the text. Start directly with the content.

8. TOKEN & CONTEXT OPTIMIZATION:
   - FOR `"strong"`, `"good"`, AND `"moderate"` (`fit_score > 50`) FITS:
     * Generate `summary` (Job-centric, ARABIC) and `reasoning` (Fit-centric, ARABIC).
   - FOR `"weak"` (`fit_score <= 50`) FITS ONLY:
     * Set `summary = null` and `reasoning = null` (do not waste tokens generating summary/reasoning for weak jobs that will be dropped).
"""

EVAL_USER_PROMPT = """Evaluate the following job postings against the EIS knowledge base provided in the system prompt. Return exactly one evaluation per job, matching each job_url character-for-character.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
JOBS YOU NEED TO EVALUATE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{{JOBS_TEXT}}
"""

CV_SYSTEM_PROMPT = """You are Ahmed Ramzy's Executive CV Tailoring Agent.
You MUST ONLY use information present in the EIS and Track Blueprint provided below. Never invent achievements, clients, revenues, titles, or credentials.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL RULES — ZERO INVENTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. **Source-Faithful Generation**: The Executive Intelligence System (EIS) and the selected Track Blueprint below are the ONLY sources of truth for achievements, client names, project names, revenues, metrics, and titles.
2. **NEVER INVENT**: Do NOT invent or fabricate: client names, project names, revenue figures, awards, certifications, professional titles, or any quantitative achievements not explicitly present in the EIS.
3. **NEVER CONVERT TARGETS**: Do NOT convert projected targets (e.g. "SAR 4.5M projected revenue target") into accomplished achievements. Targets must remain framed as targets/forecasts if they are targets in the EIS.
4. **Layout Fidelity**: Preserve the exact DOCX layout structure. Do not add new sections, remove existing sections, or change section headings.
5. **Strict JSON Output**: Return ONLY valid JSON matching the provided schema. No markdown, no explanations outside the JSON.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ENGLISH LANGUAGE REQUIREMENT (CRITICAL)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ALL output CV fields (`headline`, `about_paragraphs`, `achievements_title`, `key_achievements`, `work_experience`, `core_competencies`) MUST BE 100% IN PROFESSIONAL EXECUTIVE ENGLISH. Even if the input evaluation metadata, reasoning, or selected_track_reason contains Arabic text, the CV JSON itself is strictly English. NEVER output Arabic text inside the CV JSON.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PAGE BUDGET & TONE (CRITICAL)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- **2-PAGE STRICT LIMIT**: The rendered CV MUST fit onto EXACTLY 2 PAGES. Verbose text or excessive bullet points that overflow onto a 3rd page are forbidden.
- **PUNCHY EXECUTIVE TONE**: Every sentence must be concise, crisp, and high-impact. Avoid fluff or repetitive descriptions.
- **DYNAMIC TAILORING FREEDOM**: Use your judgment to allocate detail across sections. Focus depth on positions and achievements that best match the target job while staying within the 2-page budget.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ATS MATCH MAXIMIZATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The primary goal of tailoring is to maximize ATS keyword matching. Best practices:
- **Exact Phrase Matching**: Naturally integrate EXACT phrasing from the JD into `core_competencies`, `headline`, `about_paragraphs`, `key_achievements`, and `work_experience` bullets.
- **Action Verbs**: Start all achievement bullets with strong action verbs (Spearheaded, Directed, Architected, Steered, Optimized, Oversaw, Executed).
- **Truthfulness Anchor**: Every keyword added MUST be backed by real EIS experience — never invent skills or titles solely for ATS.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONFIDENTIALITY & NON-MONETARY SCALE RULE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- NEVER include specific monetary values, contract figures, budget numbers, or revenue amounts in the CV (e.g. omit SAR 4.5M, SAR 3.5M, SAR 2.2M).
- PRESERVE non-monetary scale indicators from the EIS (e.g. "managing 45 multidisciplinary professionals", "overseeing 35 corporate annual reports", "managing 19 IR retainer clients", "authoring 100 feasibility & market studies").

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ACADEMIC & CERTIFICATION ACCURACY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- PhD status is "PhD researcher" (in financial crisis early warning systems). Do NOT state completed PhD.
- MBA / Professional Master in Financial Markets (Arab Academy, 2023, Excellent).
- Master's in Economics (American Open University, 2017, Excellent).
- B.Sc. Commerce in Accounting (Ain Shams University, 2004).
- Certifications: CertBV (ACCA) · FMVA (CFI) · CME-1 (Saudi CMA) · Financial Analysis Diploma (IUFA).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TRACK BLUEPRINT (Source of Truth for this CV)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{{TRACK_BLUEPRINT}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TAILORING LEVEL BEHAVIOR
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Use the `tailoring_level` from the evaluation metadata:
- **light**: Modify Headline, About paragraphs, and Core Competencies keywords only. Keep standard Blueprint flow.
- **moderate**: Re-order Key Achievements and adjust bullet emphasis under Argaam based on job relevance.
- **deep**: Rebuild achievement bullets and deeply tailor work experience across all positions from the Blueprint.
- **special_cv**: Create bespoke structure from EIS if standard Blueprint sections don't fit the target role. Keep core DOCX layout but adapt content structure.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FIELD-BY-FIELD INSTRUCTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- `headline`: CONCISE, JOB-ALIGNED EXECUTIVE HEADLINE. Maximum 6–10 words (under 75 characters). Structure: `[Target Job Title] | [Pillar 1] | [Pillar 2]`. Must directly mirror the target job.

- `about_paragraphs`: Array of EXACTLY 2 short paragraphs (total 4–5 lines):
  * Paragraph 1 (Role-Aligned Positioning): Focus on target job alignment, track expertise, and strategic value proposition.
  * Paragraph 2 (EIS Proof Points & Leadership Scale): Focus on verified non-monetary metrics (45 professionals, 35 annual reports, 19 IR clients, 100 sector studies).

- `achievements_title`: Section header for key achievements (e.g. "Key Business Development Achievements:").

- `key_achievements`: Array of 6 to 8 short, punchy English bullet points (1 line each). RELEVANCE RANKING: Rank by relevance to the target job, NOT chronology. For IR roles → lead with IR clients and annual reports. For Market Intelligence → lead with 100 sector studies. For Advisory → lead with business solutions portfolio.

- `work_experience`: Array for all 3 career positions (Argaam, Asharq Al-Awsat, Mubasher) in chronological order:
  * `company`: Company name and period.
  * `role_title`: Official title + tailored scope.
  * `role_description`: 1 short summary sentence.
  * `bullets`: 3–5 bullets for Argaam (most relevant), 0–3 for Asharq/Mubasher depending on relevance.

- `core_competencies`: Pipe-separated string of EXACTLY 5 to 8 top-priority English keywords. DO NOT list 15–30 keywords. Select only the most critical, role-matched terms.
"""

CV_USER_PROMPT = """Tailor Ahmed Ramzy's Executive CV for this specific position. Generate the tailored executive CV in strict JSON format following the EIS and the selected Track Blueprint.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TARGET JOB DETAILS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{{JOB_DETAILS}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EVALUATION METADATA (Fit Scores & Tailoring Directives)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{{EVAL_METADATA}}
"""
STATE_DIR = HERE                    # jobs.json (Ahmed) / jobs_<key>.json (others)
STATE_FILE = STATE_DIR / "jobs.json"   # set per candidate in main()
RUNS_DIR = HERE / "runs"            # runs/<candidate>/<stamp>/
CANDIDATES_DIR = HERE / "candidates"   # candidates/<key>/candidate.json + prompts/ + knowledge

# ---------------------------------------------------------------- config ----
LOCATION = "Saudi Arabia"
KEYWORDS = [
    "Business Solutions", "Strategic Advisory", "Advisory Services",
    "Market Intelligence", "Strategic Research", "Market Insights",
    "Research Director", "Investor Relations", "Financial Communications",
    "Strategic Communications", "Public Affairs", "Government Relations",
    "Corporate Strategy", "Business Development Director", "Commercial Director",
]
# Job sites, searched for free with the open-source JobSpy library: no account, no key, no cost.
SITES = {"linkedin": "LinkedIn", "indeed": "Indeed", "bayt": "Bayt"}
SOURCES = ["linkedin", "indeed"]    # env SOURCES=linkedin,indeed,bayt
SEARCH_HOURS = 24                   # how far back a daily search looks (env SEARCH_HOURS)
KEYWORDS_PER_QUERY = 4              # '"A" OR "B" OR ...' - a few polite requests instead of one per keyword
RESULTS_PER_QUERY = 15
QUERY_PAUSE_SECONDS = 3             # between searches on one site; LinkedIn answers 429 when rushed
EXPERIENCE_LEVELS = ["mid-senior", "director", "executive"]
BAYT_EXPERIENCE_LEVELS = ["3", "4", "5"]   # kept for candidate configs; JobSpy's Bayt search has no level filter
# LOCATION -> the country name Indeed uses. Unknown -> Indeed is skipped.
COUNTRIES = {
    "saudi arabia": "saudi arabia", "ksa": "saudi arabia",
    "united arab emirates": "united arab emirates", "uae": "united arab emirates",
    "qatar": "qatar", "kuwait": "kuwait", "bahrain": "bahrain", "oman": "oman", "egypt": "egypt",
}

# Scoring and CVs: "basic" (default) is free keyword matching in basic_ai.py;
# "chatgpt" uses OpenAI (needs OPENAI_API_KEY, paid per use). Env AI_MODE.
AI_MODE = "basic"
AI_MODES = {"basic", "chatgpt"}

# OpenAI (ChatGPT models) scores the jobs and writes the CVs.
MODEL_EVAL = os.environ.get("OPENAI_MODEL_EVAL", "gpt-5.6-luna")
MODEL_CV = os.environ.get("OPENAI_MODEL_CV", MODEL_EVAL)
CV_MIN_FIT_SCORE = int(os.environ.get("CV_MIN_FIT_SCORE", "70"))
EVAL_BATCH_SIZE = int(os.environ.get("EVAL_BATCH_SIZE", "8"))
MAX_EVAL_ROUNDS = int(os.environ.get("MAX_EVAL_ROUNDS", "3"))
DESCRIPTION_CHARS = 6000            # JD text sent to the model per job
PENDING_MAX_AGE_DAYS = 7            # un-emailed matches older than this are dropped
RUNS_KEEP_DAYS = 30                 # runs/<stamp>/ folders older than this are pruned

# Verdict thresholds - identical defaults to the live system, overridable by env.
STRONG_MIN = int(os.environ.get("VERDICT_STRONG_MIN", "75"))
GOOD_MIN = int(os.environ.get("VERDICT_GOOD_MIN", "70"))
MODERATE_MIN = int(os.environ.get("VERDICT_MODERATE_MIN", "51"))
MIN_VERDICT = {"strong", "good"}    # what is worth emailing; env EMAIL_VERDICTS
EMAIL_DIGEST = False                # env EMAIL_DIGEST=on also emails the digest through Brevo;
                                    # off (default): matches and CVs are kept for the web app only


def env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    return default if not raw else raw in {"on", "true", "yes", "1"}

EIS_FILE = DATA_DIR / "Ahmed_Ramzy_Executive_Intelligence_System_EIS.md"
CV_PROFILE_FILE = DATA_DIR / "cv_profile.json"   # contact / education / certs for the DOCX

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "trk", "trackingId", "refId", "originalSubdomain", "currentJobId", "eBP",
    "from", "vjk", "tk", "advn",
}

# Word-boundary patterns: plain substrings blocked "International ..." (intern),
# "Internal Communications" (intern) and "Assistant Vice President" (assistant).
TITLE_BLOCKLIST = (
    r"interns?", r"internships?", r"trainees?", r"graduates?", r"junior", r"jr",
    r"assistant(?!\s+(?:vice\s+president|general\s+manager|director|managing\s+director))",
    r"secretary", r"drivers?", r"receptionists?", r"nurses?", r"engineer\w*",
    r"developers?", r"programmers?", r"accountants?", r"clerks?", r"technicians?",
    r"designers?", r"teachers?",
)
TITLE_HINTS = (
    r"director", r"head", r"s?vp", r"avp", r"evp", r"vice\s+president", r"chief", r"c[efmos]o",
    r"partner", r"principal", r"senior\s+manager", r"general\s+manager",
    r"lead(?:er)?", r"strateg\w*", r"advisory", r"advis[oe]r", r"consultant", r"research\w*",
    r"insights?", r"intelligence", r"investor\s+relations", r"ir", r"communications?",
    r"public\s+affairs", r"government\s+relations", r"business\s+development",
    r"commercial", r"product\w*", r"\w*مدير\w*", r"\w*رئيس\w*",
)
LOCATION_HINTS = (
    "saudi", "ksa", "riyadh", "jeddah", "jedda", "dammam", "khobar", "makkah", "mecca",
    "medina", "madinah", "jubail", "yanbu", "abha", "tabuk", "qassim", "buraidah",
    "eastern province", "neom", "dhahran", "hail", "najran", "jazan", "taif",
    "الرياض", "جدة", "الدمام", "الخبر", "مكة", "المدينة", "السعودية",
)
# Place names that mean "in this country" when a posting gives only a city.
COUNTRY_HINTS = {
    "saudi arabia": LOCATION_HINTS,
    "united arab emirates": ("united arab emirates", "uae", "dubai", "abu dhabi", "sharjah", "ajman",
                             "ras al khaimah", "fujairah", "al ain", "الإمارات", "دبي", "أبوظبي", "الشارقة"),
    "qatar": ("qatar", "doha", "lusail", "al wakrah", "قطر", "الدوحة"),
    "kuwait": ("kuwait", "hawalli", "farwaniya", "ahmadi", "الكويت"),
    "bahrain": ("bahrain", "manama", "muharraq", "riffa", "البحرين", "المنامة"),
    "oman": ("oman", "muscat", "sohar", "salalah", "nizwa", "عمان", "مسقط"),
    "egypt": ("egypt", "cairo", "giza", "alexandria", "new cairo", "6th of october", "مصر", "القاهرة", "الجيزة"),
}
VERDICT_RANK = {"strong": 1, "good": 2, "moderate": 3, "weak": 4}
ARABIC_RE = re.compile(r"[؀-ۿ]")

# Monetary figures must never reach a CV (EIS confidentiality rule).
MONEY_RE = re.compile(
    r"(?i)(?:\b(?:SAR|SR|USD|US\$|AED|EGP|EUR|GBP)\s?\d"
    r"|[$€£]\s?\d"
    r"|\d[\d.,]*\s?(?:million|billion|mn|bn)\b"
    r"|\d[\d.,]*\s?[MK]\b"
    r"|ريال)"
)

# --- email presentation: copied from the production email builder ----------
BADGE = {
    "strong": {"text": "🟢 STRONG FIT", "style": "background:#D1FAE5;color:#065F46;border:1px solid #10B981;", "bar": "#10B981"},
    "good": {"text": "🟡 GOOD FIT", "style": "background:#FEF3C7;color:#92400E;border:1px solid #F59E0B;", "bar": "#F59E0B"},
    "moderate": {"text": "⚪ MODERATE FIT", "style": "background:#F3F4F6;color:#374151;border:1px solid #9CA3AF;", "bar": "#6B7280"},
    "weak": {"text": "🔴 WEAK FIT", "style": "background:#FEE2E2;color:#991B1B;border:1px solid #EF4444;", "bar": "#EF4444"},
}
TRACK_NAMES = {
    1: "Business Solutions & Strategic Advisory Leader",
    2: "Market Intelligence & Strategic Research Leader",
    3: "Financial Communications & Investor Relations Leader",
    4: "Government & Institutional Strategic Communications Leader",
    5: "Commercial Growth & Productization Leader",
}
CONFIDENCE_CONFIG = {
    "high": {"text": "High Confidence", "icon": "🟢", "bg": "#ECFDF5", "color": "#065F46", "border": "#A7F3D0"},
    "medium": {"text": "Medium Confidence", "icon": "🟡", "bg": "#FEF3C7", "color": "#92400E", "border": "#FDE68A"},
    "low": {"text": "Low Confidence", "icon": "⚪", "bg": "#F3F4F6", "color": "#374151", "border": "#E5E7EB"},
}
TAILORING_CONFIG = {
    "special_cv": {"text": "Special CV", "icon": "✨", "bg": "#FDF4FF", "color": "#86198F", "border": "#F5D0FE"},
    "deep": {"text": "Deep Tailoring", "icon": "⚡", "bg": "#EEF2FF", "color": "#3730A3", "border": "#C7D2FE"},
    "moderate": {"text": "Moderate Tailoring", "icon": "🎯", "bg": "#F0FDF4", "color": "#166534", "border": "#BBF7D0"},
    "light": {"text": "Light Tailoring", "icon": "📝", "bg": "#F8FAFC", "color": "#475569", "border": "#E2E8F0"},
}


# --------------------------------------------------------------------------
# Email template - the production digest template, verbatim, as a Jinja2
# string. Jinja parses it exactly as it parses a file, so {% if %} / {{ }}
# behave identically; the web-only buttons are simply passed as empty.
# --------------------------------------------------------------------------
EMAIL_TEMPLATE = """<!DOCTYPE html>
<html>

<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Daily Executive Job Search & Tailored CV Digest</title>
</head>

<body
  style="margin:0; padding:0; background-color:#F4F6F9; font-family:'Segoe UI', Helvetica, Arial, sans-serif; -webkit-font-smoothing:antialiased; color:#2D3748;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"
    style="background-color:#F4F6F9; padding: 25px 10px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"
          style="max-width: 720px; background-color: #FFFFFF; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.08); border: 1px solid #E2E8F0;">

          <!-- HEADER BANNER -->
          <tr>
            <td
              style="background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%); padding: 32px 36px; text-align: left;">
              <table width="100%" cellspacing="0" cellpadding="0" border="0">
                <tr>
                  <td>
                    <span
                      style="display: inline-block; background-color: rgba(255,255,255,0.15); color: #94A3B8; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.5px; padding: 4px 10px; border-radius: 4px; margin-bottom: 8px;">{{system_label}}</span>
                    <h1
                      style="color: #FFFFFF; font-size: 24px; font-weight: 800; margin: 6px 0 4px 0; line-height: 1.3;">
                      {{period_label}} {{digest_title}}</h1>
                    <p style="color: #CBD5E1; font-size: 14px; margin: 0; font-weight: 500;">Prepared for <strong>{{candidate_name}}</strong> &bull; {{date_today}}</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- METRIC SUMMARY ROW -->
          <tr>
            <td style="background-color: #F8FAFC; border-bottom: 1px solid #E2E8F0; padding: 20px 36px;">
              {{download_btn}}
              <table width="100%" cellspacing="0" cellpadding="0" border="0" style="font-size: 13px; color: #475569;">
                <tr>
                  <td width="25%" align="center">
                    <div style="font-size: 26px; font-weight: 800; color: #0F172A;">{{total_jobs}}</div>
                    <div style="font-size: 10px; text-transform: uppercase; font-weight: 700; color: #64748B; letter-spacing: 0.5px;">Total Jobs</div>
                  </td>
                  <td width="25%" align="center"
                    style="border-left: 1px solid #E2E8F0;">
                    <div style="font-size: 26px; font-weight: 800; color: #059669;">{{strong_count}}</div>
                    <div style="font-size: 10px; text-transform: uppercase; font-weight: 700; color: #64748B; letter-spacing: 0.5px;">Strong Fit</div>
                  </td>
                  <td width="25%" align="center"
                    style="border-left: 1px solid #E2E8F0;">
                    <div style="font-size: 26px; font-weight: 800; color: #2563EB;">{{good_count}}</div>
                    <div style="font-size: 10px; text-transform: uppercase; font-weight: 700; color: #64748B; letter-spacing: 0.5px;">Good Fit</div>
                  </td>
                  <td width="25%" align="center"
                    style="border-left: 1px solid #E2E8F0;">
                    <div style="font-size: 26px; font-weight: 800; color: #D97706;">{{moderate_count}}</div>
                    <div style="font-size: 10px; text-transform: uppercase; font-weight: 700; color: #64748B; letter-spacing: 0.5px;">Moderate</div>
                  </td>
                </tr>
              </table>
              <!-- Secondary stats row -->
              <table width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top: 12px; font-size: 12px;">
                <tr>
                  <td align="center">
                    <span style="display: inline-block; background-color: #ECFDF5; color: #059669; font-size: 11px; font-weight: 700; padding: 4px 12px; border-radius: 20px; margin: 0 4px;">{{high_fit_count}} High Fit</span>
                    <span style="display: inline-block; background-color: #EFF6FF; color: #2563EB; font-size: 11px; font-weight: 700; padding: 4px 12px; border-radius: 20px; margin: 0 4px;">{{attachments_count}} CVs Attached</span>
                    {% if weak_count > 0 %}
                    <span style="display: inline-block; background-color: #FEF2F2; color: #DC2626; font-size: 11px; font-weight: 700; padding: 4px 12px; border-radius: 20px; margin: 0 4px;">{{weak_count}} Weak (Dropped)</span>
                    {% endif %}
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- MAIN CONTENT BODY -->
          <tr>
            <td style="padding: 30px 36px;">

              <!-- EXECUTIVE INSTRUCTIONS BOX -->
              <div
                style="background-color: #EFF6FF; border-left: 4px solid #2563EB; padding: 14px 18px; border-radius: 0 8px 8px 0; margin-bottom: 28px; font-size: 13px; color: #1E40AF; line-height: 1.5;">
                📌 <strong>Executive Instructions:</strong> Jobs are ranked by priority. <span style="color: #059669; font-weight: 700;">Strong ({{strong_min}}+)</span> and <span style="color: #2563EB; font-weight: 700;">Good ({{good_min}}-{{strong_min - 1}})</span> fits include tailored CVs. <span style="color: #D97706; font-weight: 700;">Moderate ({{moderate_min}}-{{good_min - 1}})</span> fits provide strategic summaries. Weak fits (0-{{moderate_min - 1}}) are excluded.
              </div>

              <!-- DYNAMIC JOB CARDS CONTAINER -->
              {{job_cards_html}}

            </td>
          </tr>

          <!-- FOOTER -->
          <tr>
            <td
              style="background-color: #F1F5F9; padding: 24px 36px; text-align: center; border-top: 1px solid #E2E8F0; font-size: 12px; color: #64748B; line-height: 1.6;">
              Automated Executive Job Search & Tailored CV System &bull; Powered by OpenAI<br>
              Architected & Built by <a href="https://www.linkedin.com/in/abdallahsaber065/" target="_blank" style="color: #2563EB; font-weight: bold; text-decoration: none;">Abdallah Saber</a> &bull; For <strong>{{candidate_name}}</strong> ({{footer_positioning}})
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>

</html>
"""


log = logging.getLogger("job_automation")


def setup_logging() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # Arabic/emoji on Windows consoles
        except (AttributeError, ValueError):
            pass
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


def parse_env_line(line: str) -> tuple[str, str] | None:
    """KEY=value, KEY="value", KEY=value  # inline comment (dotenv rules)."""
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        return None
    key, value = line.split("=", 1)
    value = value.strip()
    if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
        value = value[1:-1]
    else:
        value = re.split(r"\s+#", value, maxsplit=1)[0].strip()
    return key.strip(), value


def load_env() -> None:
    env_file = HERE / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        parsed = parse_env_line(line)
        if parsed:
            os.environ.setdefault(*parsed)


def need(key: str) -> str:
    value = os.environ.get(key, "").strip()
    if not value:
        sys.exit(f"missing {key} in .env")
    return value


def _env_list(key: str, default) -> list[str]:
    items = [x.strip().lower() for x in os.environ.get(key, "").split(",") if x.strip()]
    return items or list(default)


def apply_env() -> None:
    """Re-read the tunables after .env is loaded (module-level values see only real env)."""
    global LOCATION, MODEL_EVAL, MODEL_CV, EVAL_BATCH_SIZE, MAX_EVAL_ROUNDS
    global CV_MIN_FIT_SCORE, SOURCES, MIN_VERDICT
    global STRONG_MIN, GOOD_MIN, MODERATE_MIN, EMAIL_DIGEST, AI_MODE, SEARCH_HOURS
    LOCATION = os.environ.get("LOCATION", LOCATION)
    EMAIL_DIGEST = env_flag("EMAIL_DIGEST")
    AI_MODE = os.environ.get("AI_MODE", AI_MODE).strip().lower() or "basic"
    if AI_MODE not in AI_MODES:
        sys.exit(f"AI_MODE must be one of {', '.join(sorted(AI_MODES))}")
    SEARCH_HOURS = max(1, int(os.environ.get("SEARCH_HOURS", SEARCH_HOURS)))
    MODEL_EVAL = os.environ.get("OPENAI_MODEL_EVAL", MODEL_EVAL)
    MODEL_CV = os.environ.get("OPENAI_MODEL_CV", MODEL_EVAL)
    CV_MIN_FIT_SCORE = int(os.environ.get("CV_MIN_FIT_SCORE", CV_MIN_FIT_SCORE))
    EVAL_BATCH_SIZE = max(1, int(os.environ.get("EVAL_BATCH_SIZE", EVAL_BATCH_SIZE)))
    MAX_EVAL_ROUNDS = max(1, int(os.environ.get("MAX_EVAL_ROUNDS", MAX_EVAL_ROUNDS)))
    STRONG_MIN = int(os.environ.get("VERDICT_STRONG_MIN", STRONG_MIN))
    GOOD_MIN = int(os.environ.get("VERDICT_GOOD_MIN", GOOD_MIN))
    MODERATE_MIN = int(os.environ.get("VERDICT_MODERATE_MIN", MODERATE_MIN))
    SOURCES = _env_list("SOURCES", SOURCES)
    MIN_VERDICT = set(_env_list("EMAIL_VERDICTS", MIN_VERDICT))

    check_sources(SOURCES)
    unknown_verdicts = MIN_VERDICT - set(VERDICT_RANK)
    if unknown_verdicts:
        sys.exit(f"unknown EMAIL_VERDICTS: {', '.join(sorted(unknown_verdicts))}")
    if not STRONG_MIN >= GOOD_MIN >= MODERATE_MIN:
        sys.exit("verdict thresholds must satisfy VERDICT_STRONG_MIN >= VERDICT_GOOD_MIN >= VERDICT_MODERATE_MIN")


def check_sources(sources: list[str]) -> None:
    unknown = [s for s in sources if s not in SITES]
    if unknown:
        sys.exit(f"unknown source(s): {', '.join(unknown)} (known: {', '.join(SITES)})")


def clean(text: str) -> str:
    """One-line text: tags stripped, entities decoded, whitespace collapsed."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def clean_description(text: str) -> str:
    """Like clean(), but keeps paragraph and list structure for the evaluator."""
    text = re.sub(r"(?i)<\s*li[^>]*>", "\n- ", text or "")
    text = re.sub(r"(?i)<\s*(?:br|/p|/li|/div|/h\d|/tr|/ul|/ol)\s*/?>", "\n", text)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    lines = [re.sub(r"[ \t\r\f\v\xa0]+", " ", line).strip() for line in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False, default=str), encoding="utf-8")


# ---------------------------------------------- 1. scrape (JobSpy, free) --
def search_queries(keywords: list[str]) -> list[str]:
    """Keywords grouped into '"A" OR "B" OR ...' queries: a handful of requests per
    site instead of one per keyword (LinkedIn and Indeed both read OR)."""
    return [" OR ".join(f'"{k}"' for k in keywords[i:i + KEYWORDS_PER_QUERY])
            for i in range(0, len(keywords), KEYWORDS_PER_QUERY)]


def site_search_args(source: str) -> dict | None:
    """Per-site JobSpy arguments; None when the site can't search LOCATION."""
    if source == "linkedin":
        return {"location": LOCATION, "fetch_description": True}
    if source == "indeed":
        country = COUNTRIES.get(LOCATION.strip().lower())
        if not country:
            log.warning("scrape: indeed skipped - no COUNTRIES entry for LOCATION=%r", LOCATION)
            return None
        return {"location": LOCATION, "country_indeed": country}
    if source == "bayt":
        return {}                       # no location filter there; filter_jobs drops other countries
    return None


def jobspy_row(row: dict, source: str) -> dict:
    """One JobSpy result as a raw item normalize() reads like the others."""
    def text(key: str) -> str:
        value = row.get(key)
        return "" if value is None or (isinstance(value, float) and value != value) else str(value)   # NaN -> ""

    job_id = text("id")
    item = {"_source": source, "id": job_id, "url": text("job_url"), "title": text("title"),
            "company": text("company"), "location": text("location"), "description": text("description"),
            "logo": text("company_logo"), "company_site": text("company_url_direct"), "posted": text("date_posted")[:10]}
    if source == "linkedin":
        item["jobId"] = job_id.removeprefix("li-")
    return item


def scrape(keywords: list[str], sources: list[str], hours: int | None = None) -> list[dict]:
    """Public job listings, read directly (no account, no key). A site that fails
    is skipped; only when every site fails does the run stop, with the reason."""
    import warnings

    from jobspy import scrape_jobs

    from concurrent.futures import ThreadPoolExecutor

    hours = hours or SEARCH_HOURS
    queries = search_queries(keywords)
    plan = [(source, extra) for source in sources if (extra := site_search_args(source)) is not None]
    for source, _ in plan:
        log.info("scrape: %s (%d keywords in %d searches, last %d hours)", source, len(keywords), len(queries), hours)

    def one_site(source: str, extra: dict) -> tuple[list[dict], str | None]:
        """Every search on one site, in order (LinkedIn with a pause between them)."""
        found_rows, failed = [], []
        for i, query in enumerate(keywords if source == "bayt" else queries):     # Bayt doesn't read OR
            if i and source == "linkedin":
                time.sleep(QUERY_PAUSE_SECONDS)
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    found = scrape_jobs(site_name=[source], search_term=query, results_wanted=RESULTS_PER_QUERY,
                                        hours_old=hours, description_format="html", verbose=0, **extra)
                records = found.to_dict("records") if hasattr(found, "to_dict") else list(found or [])
            except Exception as exc:  # noqa: BLE001 - one bad search must not kill the run
                failed.append(str(exc))
                continue
            found_rows.extend(jobspy_row(r, source) for r in records)
        if failed and not found_rows:
            log.error("  %s: %s", source, failed[0])
            return found_rows, failed[0]
        log.info("  %s: %d raw items%s", source, len(found_rows), f" ({len(failed)} searches failed)" if failed else "")
        return found_rows, None

    # The sites are searched at the same time (each one still paced on its own), so a search
    # takes as long as the slowest site rather than all of them added up.
    with ThreadPoolExecutor(max_workers=max(1, len(plan))) as pool:
        results = list(pool.map(lambda p: one_site(*p), plan))
    rows = [row for found_rows, _ in results for row in found_rows]           # in the order the sites were listed
    errors = [error for _, error in results if error]
    tried = len(plan)
    if tried and len(errors) == tried:
        raise RunStopped(f"no job site could be searched - check the internet connection ({errors[0][:160]})")
    return rows


# ---------------------------------------------------- 2. normalize (logic) --
# Where each actor puts each field (dotted = nested). Checked against the
# actors' published output: LinkedIn's description is `jobDescription`, Indeed
# nests everything (`title.text`, `company.name`, `urls.indeed`), Bayt is flat.
FIELD_MAP = {
    "linkedin": {
        "id": ("jobId",),
        "url": ("jobUrl", "link", "url", "applyUrl"),
        "title": ("jobTitle", "title", "position"),
        "company": ("companyName", "company"),
        "location": ("location", "jobLocation"),
        "description": ("jobDescription", "descriptionText", "description", "descriptionHtml"),
    },
    "indeed": {
        "id": ("id", "jobKey"),
        "url": ("urls.indeed", "url", "jobUrl", "urls.apply"),
        "title": ("title.text", "title"),
        "company": ("company.name", "companyName", "company"),
        "location": ("location.formattedShort", "location.formatted", "location.city", "location"),
        "description": ("description.text", "description.html", "description"),
    },
    "bayt": {
        "id": ("id",),
        "url": ("canonicalUrl", "url"),
        "title": ("title",),
        "company": ("company",),
        "location": ("location", "companyLocation"),
        "description": ("description",),
    },
}


def canonical_url(raw: str, linkedin_id: str = "") -> str:
    """Platform rules: keep the stable job id, drop tracking and fragments."""
    url = (raw or "").strip().split("#")[0]
    if linkedin_id.isdigit() and (not url or "linkedin.com" in url):
        return f"https://www.linkedin.com/jobs/view/{linkedin_id}"
    if not url:
        return ""
    if "linkedin.com" in url:
        # /jobs/view/<id>, /jobs/view/<slug>-<id>, or ?currentJobId=<id>
        match = re.search(r"jobs/view/(?:[^/?#]*?-)?(\d{6,})", url) or re.search(r"currentJobId=(\d+)", url)
        if match:
            return f"https://www.linkedin.com/jobs/view/{match.group(1)}"
    if "indeed." in url:
        match = re.search(r"[?&]jk=([a-f0-9]+)", url, re.I)
        if match:
            host = urlparse(url).netloc or "www.indeed.com"
            return f"https://{host}/viewjob?jk={match.group(1).lower()}"
    parsed = urlparse(url)
    query = {k: v for k, v in parse_qs(parsed.query).items() if k not in TRACKING_PARAMS}
    rebuilt = parsed._replace(query=urlencode(query, doseq=True), fragment="").geturl()
    return rebuilt.rstrip("/")


def _dig(item: Any, path: str) -> Any:
    for part in path.split("."):
        if not isinstance(item, dict):
            return None
        item = item.get(part)
    return item


def _pick(item: dict, *paths: str) -> str:
    for path in paths:
        value = _dig(item, path)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def company_key(name: str) -> str:
    """'Gathern | جاذر إن' and 'Gathern' -> 'gathern': one key per company for its logo."""
    return re.sub(r"[\W_]+", " ", (name or "").split("|")[0].lower()).strip()


def remember_logos(state: dict, jobs: list[dict]) -> None:
    """Company -> logo URL, from every job a search sees (before dedupe), so jobs
    found on earlier searches show their company's logo too."""
    logos = state.setdefault("logos", {})
    for job in jobs:
        key = company_key(job.get("company", ""))
        if key and job.get("logo"):
            logos[key] = job["logo"]


def make_signature(title: str, company: str, place: str) -> str:
    # Lowercase + no punctuation so "Head of Strategy" and "Head Of Strategy "
    # collapse. \w keeps Arabic letters (an a-z class reduced Arabic titles to "").
    return re.sub(r"[\W_]+", " ", f"{title} {company} {place}".lower()).strip()


def normalize(items: list[dict]) -> list[dict]:
    jobs = []
    for item in items:
        source = str(item.get("_source") or item.get("source") or "linkedin").lower()
        fields = FIELD_MAP.get(source, FIELD_MAP["linkedin"])
        job_id = _pick(item, *fields["id"])
        url = canonical_url(_pick(item, *fields["url"]), job_id if source == "linkedin" else "")
        title = clean(_pick(item, *fields["title"]))
        if not (url and title):
            continue
        company = clean(_pick(item, *fields["company"]))
        place = clean(_pick(item, *fields["location"]))
        description = clean_description(_pick(item, *fields["description"]))
        skills = item.get("skills")
        if isinstance(skills, list) and skills:
            description += "\n\nSkills: " + "; ".join(str(s) for s in skills if s)
        logo = str(item.get("logo") or "").strip()
        posted = str(item.get("posted") or "")[:10]
        jobs.append(
            {
                "url": url,
                "title": title,
                "company": company,
                "location": place,
                "description": description,
                "source": source,
                "signature": make_signature(title, company, place) or url,
                "logo": logo if logo.startswith("https://") else "",
                "posted": posted if re.fullmatch(r"\d{4}-\d\d-\d\d", posted) else "",
            }
        )
    missing = sum(1 for job in jobs if not job["description"])
    log.info("normalize: %d -> %d (%d without a description)", len(items), len(jobs), missing)
    return jobs


def recent_only(jobs: list[dict], hours: int, today: datetime | None = None) -> list[dict]:
    """Drop postings older than the look-back. The job sites' own filter is loose (LinkedIn returns
    reposted and older jobs), so the posted date each site gives is checked here. Sites give a date,
    not a time: with 24 hours, today and yesterday stay. No date given: the job stays."""
    today = (today or datetime.now()).date()
    cutoff = (today - timedelta(days=max(1, -(-hours // 24)))).isoformat()
    kept = [job for job in jobs if not job.get("posted") or job["posted"] >= cutoff]
    log.info("dates: %d -> %d (posted before %s dropped)", len(jobs), len(kept), cutoff)
    return kept


LINKEDIN_POSTING = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{id}"
BROWSER_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                                 "Chrome/131.0 Safari/537.36", "Accept-Language": "en-US,en;q=0.9"}


def fetch_description(url: str) -> str:
    """The full posting text for a job that arrived without one. LinkedIn shows it on its public job
    page; Bayt refuses automated reads, so it returns "" there (and on any failure)."""
    match = re.search(r"linkedin\.com/jobs/view/(?:[^/?#]*-)?(\d{6,})", url or "")
    if not match:
        return ""
    import requests
    from bs4 import BeautifulSoup

    try:
        r = requests.get(LINKEDIN_POSTING.format(id=match.group(1)), headers=BROWSER_HEADERS, timeout=12)
        if r.status_code != 200:
            return ""
        r.encoding = "utf-8"
        el = BeautifulSoup(r.text, "html.parser").select_one("div.show-more-less-html__markup, div.description__text")
        return clean_description(el.decode_contents()) if el else ""
    except Exception:  # noqa: BLE001 - a missing description is never worth failing a search
        return ""


def fill_descriptions(jobs: list[dict]) -> None:
    """Fetch the description of every job that arrived without one (before scoring, so the
    score can use it). A few at a time, gently: LinkedIn slows down tools that rush it."""
    from concurrent.futures import ThreadPoolExecutor

    missing = [job for job in jobs if len(job.get("description") or "") < 150 and "linkedin.com" in job.get("url", "")]
    if not missing:
        return
    with ThreadPoolExecutor(max_workers=3) as pool:
        texts = list(pool.map(lambda job: fetch_description(job["url"]), missing))
    got = 0
    for job, text in zip(missing, texts):
        if len(text) >= 150:
            job["description"] = text
            got += 1
    log.info("descriptions: fetched %d of %d that LinkedIn left out", got, len(missing))


# -------------------------------------------------------- 3. dedupe (logic) --
def same_job_key(title: str, company: str) -> str:
    """Company + title, ignoring how each site writes the city: the same job posted on LinkedIn
    and Indeed ('Gathern | جاذر إن', 'Riyadh, Saudi Arabia' / 'Gathern', 'Riyadh') is one job."""
    firm = company_key(company)
    return f"{firm}|{re.sub(r'[\W_]+', ' ', (title or '').lower()).strip()}" if firm else ""


def _same_firm(a: str, b: str) -> bool:
    """'qiddiya' and 'qiddiya investment company' are one company (one name starts the other)."""
    return a == b or a.startswith(b + " ") or b.startswith(a + " ")


def _known(key: str, keys) -> bool:
    if not key:
        return False
    firm, title = key.split("|", 1)
    return any(t == title and _same_firm(firm, f) for f, t in (k.split("|", 1) for k in keys))


def dedupe(jobs: list[dict], seen_urls: set[str], seen_signatures: set[str] | None = None,
           seen_keys: set[str] | None = None) -> list[dict]:
    """Exact pass only: canonical URL, the title|company|location signature, and company + title
    across sites - within this scrape and against everything already in jobs.json. When a job is
    on two sites, the copy kept gets the longer description of the two."""
    seen_signatures, seen_keys = seen_signatures or set(), seen_keys or set()
    kept, urls, signatures, by_key = [], set(), set(), {}
    already = dupes = 0
    for job in jobs:
        key = same_job_key(job.get("title", ""), job.get("company", ""))
        if job["url"] in seen_urls or job["signature"] in seen_signatures or _known(key, seen_keys):
            already += 1
            continue
        if job["url"] in urls or job["signature"] in signatures or _known(key, by_key):
            twin = next((by_key[k] for k in by_key if _known(key, [k])), None) if key else None
            if twin is not None and len(job.get("description") or "") > len(twin.get("description") or ""):
                twin["description"] = job["description"]
            dupes += 1
            continue
        urls.add(job["url"])
        signatures.add(job["signature"])
        if key:
            by_key[key] = job
        kept.append(job)
    log.info("dedupe: %d -> %d (%d duplicates, %d already seen)", len(jobs), len(kept), dupes, already)
    return kept


# -------------------------------------------------------- 4. filter (logic) --
def word_pattern(patterns) -> re.Pattern:
    """Title allow/block lists are matched as whole words, case-insensitive."""
    return re.compile(r"\b(?:" + "|".join(patterns) + r")\b", re.I)


def title_ok(title: str) -> bool:
    return not CANDIDATE.title_block_re.search(title) and bool(CANDIDATE.title_hint_re.search(title))


def location_ok(place: str) -> bool:
    place = place.lower()
    if not place:
        return True                     # no location given: let the evaluator decide
    hints = COUNTRY_HINTS.get(LOCATION.strip().lower(), ())
    return any(hint in place for hint in hints) or LOCATION.lower() in place


def filter_jobs(jobs: list[dict]) -> list[dict]:
    kept = []
    blocked = no_hint = elsewhere = 0
    for job in jobs:
        if CANDIDATE.title_block_re.search(job["title"]):
            blocked += 1
        elif not CANDIDATE.title_hint_re.search(job["title"]):
            no_hint += 1
        elif not location_ok(job["location"]):
            elsewhere += 1
        else:
            kept.append(job)
    log.info(
        "filter: %d -> %d (blocked title %d, no seniority/function match %d, outside %s %d)",
        len(jobs), len(kept), blocked, no_hint, LOCATION, elsewhere,
    )
    return kept


# ------------------------------------------------------ 5. evaluate (logic) --
class JobEvaluation(BaseModel):
    """Structured-output contract for one job - every field the evaluation prompt
    asks for. No defaults anywhere: strict structured outputs reject `default`."""

    job_url: str = Field(description="job_url exactly as supplied")
    ats_score: int = Field(description="0-100")
    interview_score: int = Field(description="0-100")
    fit_score: int = Field(description="round(ats_score * 0.45 + interview_score * 0.55)")
    selected_track: Literal[1, 2, 3, 4, 5]
    secondary_track: Literal[1, 2, 3, 4, 5] | None
    track_selection_confidence: Literal["high", "medium", "low"]
    selected_track_reason: str = Field(description="Arabic")
    tailoring_level: Literal["light", "moderate", "deep", "special_cv"]
    summary: str | None = Field(description="Arabic, job-centric; null for weak fits")
    reasoning: str | None = Field(description="Arabic, fit-centric; null for weak fits")


class BatchEvaluations(BaseModel):
    evaluations: list[JobEvaluation]


class OpenAIAI:
    """OpenAI (ChatGPT models) behind the pipeline's one AI call:
    parse(model=, messages=, response_format=) -> a validated pydantic object.
    The system prompt (the knowledge base) comes first in every request, so
    OpenAI's automatic prompt caching bills repeats of it at the cached rate."""

    def __init__(self, api_key: str):
        from openai import OpenAI

        self.sdk = OpenAI(api_key=api_key, max_retries=2, timeout=600.0)
        self.usage = {"calls": 0, "input": 0, "cached": 0, "output": 0}

    def parse(self, *, model: str, messages: list[dict], response_format: type[BaseModel]) -> BaseModel:
        completion = self.sdk.chat.completions.parse(model=model, messages=messages, response_format=response_format)
        self._count(getattr(completion, "usage", None))
        choice = completion.choices[0]
        if getattr(choice.message, "refusal", None):
            raise RuntimeError(f"model refused: {choice.message.refusal}")
        if getattr(choice, "finish_reason", None) == "length":
            raise RuntimeError("the model's answer was cut off (finish_reason=length)")
        if choice.message.parsed is None:
            raise RuntimeError(f"no structured output (finish_reason={getattr(choice, 'finish_reason', '?')})")
        return choice.message.parsed

    def _count(self, usage) -> None:
        self.usage["calls"] += 1
        if usage is None:
            return
        self.usage["input"] += getattr(usage, "prompt_tokens", 0) or 0
        self.usage["output"] += getattr(usage, "completion_tokens", 0) or 0
        details = getattr(usage, "prompt_tokens_details", None)
        self.usage["cached"] += getattr(details, "cached_tokens", 0) or 0

    def usage_line(self) -> str:
        u = self.usage
        return (f"openai: {u['calls']} calls, {u['input']:,} input tokens ({u['cached']:,} cached), "
                f"{u['output']:,} output tokens")


def make_ai_client() -> OpenAIAI:
    return OpenAIAI(need("OPENAI_API_KEY"))


class RunStopped(RuntimeError):
    """A failure the whole run shares (a rejected key, no credit): stop with a plain reason."""


class AIUnavailable(RunStopped):
    """An error every further AI call would hit too (bad key, no credit): stop the run."""


def fatal_ai_error(exc: Exception) -> str | None:
    status = getattr(exc, "status_code", None)
    text = str(exc).lower()
    if status == 401:
        return "the OpenAI API key was rejected - check it in Client Setup"
    if (getattr(exc, "code", None) == "insufficient_quota" or "insufficient_quota" in text
            or "exceeded your current quota" in text or "no credits remaining" in text):
        return "the OpenAI account is out of credit - add credit under Billing at platform.openai.com"
    if status == 403:
        return "this OpenAI API key is not allowed to make this request"
    if status == 404 and "model" in text:
        return f"model not available to this key: {MODEL_EVAL}"
    return None


def llm_parse(client, *, model: str, messages: list[dict], response_format: type[BaseModel]) -> BaseModel:
    """Every AI client here (OpenAI, Demo Mode's simulated AI, the test fakes)
    answers parse() with the validated object, or raises."""
    return client.parse(model=model, messages=messages, response_format=response_format)


def jobs_text(batch: list[dict]) -> str:
    blocks = []
    for job in batch:
        blocks.append(
            f"job_url: {job['url']}\n"
            f"title: {job['title']}\n"
            f"company: {job['company']}\n"
            f"location: {job['location']}\n"
            f"description:\n{(job['description'] or '(no description provided)')[:DESCRIPTION_CHARS]}"
        )
    return "\n\n---\n\n".join(blocks)


def evaluate_batch(batch: list[dict], client, system: str) -> dict[str, dict]:
    if hasattr(client, "evaluate_jobs"):            # free mode (basic_ai) scores the jobs directly, no prompt
        parsed = client.evaluate_jobs(batch)
    else:
        prompt = CANDIDATE.eval_user_prompt.replace("{{JOBS_TEXT}}", jobs_text(batch))
        parsed = llm_parse(
            client,
            model=MODEL_EVAL,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            response_format=BatchEvaluations,
        )
    # Match the model's job_url back to ours, tolerating a trailing slash or a
    # re-added tracking parameter - otherwise a cosmetic difference costs a retry.
    wanted = {}
    for job in batch:
        wanted[job["url"]] = job["url"]
        wanted[canonical_url(job["url"])] = job["url"]
    out = {}
    for evaluation in parsed.evaluations:
        url = wanted.get(evaluation.job_url.strip()) or wanted.get(canonical_url(evaluation.job_url))
        if url:
            out[url] = evaluation.model_dump()
    return out


def _clamp(value: Any) -> int:
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return 0


def weighted_fit(ats_score: int, interview_score: int) -> int:
    """The prompt's formula, computed here instead of trusting model arithmetic."""
    return int(ats_score * 0.45 + interview_score * 0.55 + 0.5)


def apply_evaluation(job: dict, evaluation: dict) -> dict:
    evaluation = dict(evaluation)
    evaluation.pop("job_url", None)
    ats, interview = _clamp(evaluation["ats_score"]), _clamp(evaluation["interview_score"])
    fit = weighted_fit(ats, interview)
    if abs(fit - _clamp(evaluation.get("fit_score"))) > 2:
        log.debug("  fit_score corrected %s -> %s for %s", evaluation.get("fit_score"), fit, job["title"])
    job.update(evaluation)
    job.update(ats_score=ats, interview_score=interview, fit_score=fit, fit_verdict=verdict(fit))
    return job


def evaluate(jobs: list[dict], client, knowledge: str) -> list[dict]:
    """Batched evaluation with catch-up rounds for anything the model drops.
    Each catch-up round halves the batch size, so one malformed job cannot keep
    sinking the same large batch. `knowledge` is the candidate's knowledge base
    (Ahmed's EIS, or a rendered CIS)."""
    system = CANDIDATE.eval_system_prompt.replace(CANDIDATE.kb_placeholder, knowledge)
    pending = list(jobs)
    results: dict[str, dict] = {}

    for round_no in range(1, MAX_EVAL_ROUNDS + 1):
        if not pending:
            break
        size = max(1, EVAL_BATCH_SIZE // (2 ** (round_no - 1)))
        log.info("evaluate: round %d, %d jobs, batch %d", round_no, len(pending), size)
        still_pending = []
        for start in range(0, len(pending), size):
            batch = pending[start : start + size]
            try:
                got = evaluate_batch(batch, client, system)
            except Exception as exc:  # noqa: BLE001 - retry next round
                reason = fatal_ai_error(exc)
                if reason:
                    raise AIUnavailable(reason) from exc
                log.warning("  batch of %d failed: %s", len(batch), exc)
                still_pending.extend(batch)
                continue
            for job in batch:
                found = got.get(job["url"])
                if found:
                    results[job["url"]] = found
                else:
                    still_pending.append(job)      # model skipped it -> catch-up
        pending = still_pending
    if pending:
        log.warning("  %d jobs never evaluated after %d rounds (retried next run)", len(pending), MAX_EVAL_ROUNDS)

    breakdowns = getattr(client, "breakdowns", None) or {}       # free scoring explains each score
    out = []
    for job in jobs:
        if job["url"] in results:
            job = apply_evaluation(job, results[job["url"]])
            if job["url"] in breakdowns:
                job["breakdown"] = breakdowns[job["url"]]
            out.append(job)
    return out


# --------------------------------------------------------- 6. verdict (logic) --
def verdict(fit_score: int) -> str:
    if fit_score >= STRONG_MIN:
        return "strong"
    if fit_score >= GOOD_MIN:
        return "good"
    if fit_score >= MODERATE_MIN:
        return "moderate"
    return "weak"


def sort_jobs(jobs: list[dict]) -> list[dict]:
    return sorted(jobs, key=lambda j: (VERDICT_RANK.get(j.get("fit_verdict"), 4), -int(j.get("fit_score") or 0)))


# ------------------------------------------------- 7. CV generation (high fit) --
class WorkExperienceEntry(BaseModel):
    company: str
    period: str
    role_title: str
    role_description: str
    bullets: list[str]


class TailoredCV(BaseModel):
    """CV architect output - the content fields of the production contract.
    Job metadata (url, title, scores, track) stays in code rather than being
    echoed by the model, and no field has a default because strict structured
    outputs reject `default`."""

    headline: str
    about_paragraphs: list[str]
    achievements_title: str
    key_achievements: list[str]
    work_experience: list[WorkExperienceEntry]
    core_competencies: str


TRACK_FILES = {
    1: "Business Solutions & Strategic Advisory Leader.md",
    2: "Market Intelligence & Strategic Research Leader.md",
    3: "Financial Communications & Investor Relations Leader.md",
    4: "Government & Institutional Strategic Communications Leader.md",
    5: "Commercial Growth & Productization Leader.md",
}
RULE = "━" * 51


def cv_eval_metadata(job: dict, track: int) -> str:
    names = CANDIDATE.track_names
    secondary = job.get("secondary_track")
    lines = [
        f"Target Position: {job['title']} @ {job['company']} ({job['location']})",
        f"Job URL: {job['url']}",
        f"Overall Fit Score: {job['fit_score']}% (Verdict: {job['fit_verdict']})",
        f"  • ATS Match Score: {job['ats_score']}%",
        f"  • Interview Match Score: {job['interview_score']}%",
        f"Primary Selected Track: Track {track} - {names[track]}",
        f"Secondary Track: Track {secondary} - {names[secondary]}" if secondary in names else "Secondary Track: none",
        f"Track Selection Confidence: {job.get('track_selection_confidence') or 'medium'}",
        f"tailoring_level: {job.get('tailoring_level') or 'moderate'}",
    ]
    if CANDIDATE.cv_free_text_metadata:
        # The evaluator saw the whole knowledge base; where that includes records
        # not cleared for CVs, its free text must not cross into the CV call.
        lines += [
            f"Track Selection Reason: {job.get('selected_track_reason') or ''}",
            f"Fit Reasoning: {job.get('reasoning') or ''}",
        ]
    return "\n".join(lines)


def _cv_texts(cv: TailoredCV) -> list[str]:
    texts = [cv.headline, cv.achievements_title, cv.core_competencies, *cv.about_paragraphs, *cv.key_achievements]
    for entry in cv.work_experience:
        texts += [entry.role_title, entry.role_description, *entry.bullets]
    return texts


def _breaks_rules(text: str) -> bool:
    return any(pattern.search(text or "") for _, pattern in CANDIDATE.cv_forbidden)


def cv_leaks(cv: TailoredCV) -> list[str]:
    """One finding per CV line that breaks the candidate's disclosure rules
    (money for Ahmed; money, headcounts, restricted names and figures for Atef)."""
    found = []
    for text in _cv_texts(cv):
        for label, pattern in CANDIDATE.cv_forbidden:
            match = pattern.search(text or "")
            if match:
                found.append(f'{label}: "{text[max(0, match.start() - 25) : match.end() + 20].strip()}"')
                break
    return found


def _drop_sentences(text: str) -> str:
    parts = re.split(r"(?<=[.;!?])\s+", text or "")
    return " ".join(p for p in parts if not _breaks_rules(p)).strip()


def _drop_segments(text: str) -> str:
    return " | ".join(s.strip() for s in (text or "").split("|") if s.strip() and not _breaks_rules(s))


def scrub_cv(cv: TailoredCV) -> TailoredCV:
    """Last-resort guard: drop any bullet/sentence/segment that still breaks a rule."""
    cv = cv.model_copy(deep=True)
    cv.headline = _drop_segments(cv.headline)
    cv.core_competencies = _drop_segments(cv.core_competencies)
    cv.about_paragraphs = [p for p in map(_drop_sentences, cv.about_paragraphs) if p]
    cv.key_achievements = [b for b in cv.key_achievements if not _breaks_rules(b)]
    for entry in cv.work_experience:
        entry.role_description = _drop_sentences(entry.role_description)
        entry.bullets = [b for b in entry.bullets if not _breaks_rules(b)]
    return cv


def tailor_cv(job: dict, client) -> TailoredCV | None:
    """One CV architect call per high-fit job, with the candidate's CV prompts."""
    track = job.get("selected_track") if job.get("selected_track") in CANDIDATE.track_names else 1
    if hasattr(client, "tailor"):                   # free mode: the standard CV, still guarded
        try:
            cv = client.tailor(job, track)
            return scrub_cv(cv) if cv_leaks(cv) else cv
        except Exception as exc:  # noqa: BLE001 - a failed CV must not lose the digest
            log.error("  cv failed (%s): %s", job["title"], exc)
            return None
    blueprint = CANDIDATE.blueprint(track)
    if not blueprint:
        log.error("  blueprint missing for track %s", track)
        return None

    system = CANDIDATE.cv_system_prompt.replace("{{TRACK_BLUEPRINT}}", blueprint)
    if job.get("tailoring_level") == "special_cv":
        # special_cv means "bespoke structure from the knowledge base" - so it has
        # to be there. (Empty for CIS candidates: their blueprint already holds
        # every CV-approved fact, and nothing else may reach the CV call.)
        source = CANDIDATE.special_cv_source()
        if source:
            system += f"\n{RULE}\n{CANDIDATE.system_label} - full source for special_cv tailoring\n{RULE}\n{source}\n"
    user = CANDIDATE.cv_user_prompt.replace(
        "{{JOB_DETAILS}}",
        f"Title: {job['title']}\nCompany: {job['company']}\n"
        f"Location: {job['location']}\nURL: {job['url']}\n\n{(job.get('description') or '')[:DESCRIPTION_CHARS]}",
    ).replace("{{EVAL_METADATA}}", cv_eval_metadata(job, track))
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]

    try:
        cv = llm_parse(client, model=MODEL_CV, messages=messages, response_format=TailoredCV)
        leaks = cv_leaks(cv)
        if leaks:
            log.warning("  cv for %s breaks disclosure rules (%s) - asking for a correction",
                        job["title"], " / ".join(leaks[:3]))
            messages += [
                {"role": "assistant", "content": cv.model_dump_json()},
                {
                    "role": "user",
                    "content": "This CV breaks the confidentiality / disclosure rules in your instructions. "
                    f"It contains: {' / '.join(leaks)}. Return the complete CV JSON again with every one "
                    "of these removed. Keep everything else, including non-monetary scale indicators "
                    "the rules allow.",
                },
            ]
            cv = llm_parse(client, model=MODEL_CV, messages=messages, response_format=TailoredCV)
            if cv_leaks(cv):
                log.warning("  cv for %s still breaks disclosure rules - removing those lines", job["title"])
                cv = scrub_cv(cv)
        return cv
    except Exception as exc:  # noqa: BLE001 - a failed CV must not lose the digest
        log.error("  cv failed (%s): %s", job["title"], exc)
        return None


def load_cv_profile() -> dict:
    if CANDIDATE.cv_fixed:                          # a profile saved in the app
        return CANDIDATE.cv_fixed()
    path = CANDIDATE.cv_profile_file
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    log.warning("cv: %s missing - CVs will have no contact/education section", path)
    return {}


# pPr children that must come after <w:pBdr> (OOXML sequence) - Word flags the
# file as damaged when they are out of order.
_PBDR_SUCCESSORS = (
    "w:shd", "w:tabs", "w:suppressAutoHyphens", "w:kinsoku", "w:wordWrap", "w:overflowPunct",
    "w:topLinePunct", "w:autoSpaceDE", "w:autoSpaceDN", "w:bidi", "w:adjustRightInd",
    "w:snapToGrid", "w:spacing", "w:ind", "w:contextualSpacing", "w:mirrorIndents",
    "w:suppressOverlap", "w:jc", "w:textDirection", "w:textAlignment", "w:textboxTightWrap",
    "w:outlineLvl", "w:divId", "w:cnfStyle", "w:rPr", "w:sectPr", "w:pPrChange",
)


def _bottom_border(paragraph, color: str) -> None:
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    border = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    for key, value in (("w:val", "single"), ("w:sz", "6"), ("w:space", "1"), ("w:color", color)):
        bottom.set(qn(key), value)
    border.append(bottom)
    paragraph._p.get_or_add_pPr().insert_element_before(border, *_PBDR_SUCCESSORS)


def render_cv_docx(cv: TailoredCV, profile: dict | None = None) -> bytes:
    """The CV as a Word file: one clean A4 column that applicant-tracking systems read (no tables or
    text boxes), the job-specific content from the CV writer, and the fixed facts (contact, education,
    certifications, languages) from the profile. Dates sit on the right of each role, like a printed CV."""
    from io import BytesIO

    from docx import Document
    from docx.enum.text import WD_TAB_ALIGNMENT
    from docx.shared import Mm, Pt, RGBColor

    profile = profile or {}
    ink = RGBColor(0x1B, 0x1A, 0x17)
    accent_hex = "1F3A5F"
    accent = RGBColor.from_string(accent_hex)
    muted = RGBColor(0x5F, 0x5D, 0x57)

    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Mm(210), Mm(297)
    section.top_margin = section.bottom_margin = Mm(16)
    section.left_margin = section.right_margin = Mm(18)
    text_width = section.page_width - section.left_margin - section.right_margin
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = ink
    normal.paragraph_format.space_after = Pt(2)
    normal.paragraph_format.line_spacing = 1.08

    name = profile.get("name") or CANDIDATE.name
    doc.core_properties.author = name
    doc.core_properties.title = f"{name} - CV"

    def para(before: float = 0, after: float = 2, keep: bool = False):
        p = doc.add_paragraph()
        p.paragraph_format.space_before, p.paragraph_format.space_after = Pt(before), Pt(after)
        p.paragraph_format.keep_with_next = keep
        return p

    def write(p, text: str, size: float | None = None, bold: bool = False, italic: bool = False, color=None):
        r = p.add_run(text)
        if size:
            r.font.size = Pt(size)
        r.bold, r.italic = bold, italic
        if color is not None:
            r.font.color.rgb = color
        return r

    def heading(text: str) -> None:
        p = para(12, 5, keep=True)
        # No letter-spacing: in a PDF copy it splits words ("PROFE SSIONAL") for applicant-tracking systems.
        write(p, text.rstrip(":").upper(), 10, bold=True, color=accent)
        _bottom_border(p, accent_hex)

    def bullet(text: str) -> None:
        p = doc.add_paragraph(text, style="List Bullet")
        p.paragraph_format.space_after = Pt(1.5)

    def with_right(p, left_parts, right: str) -> None:
        """A line with the dates (or year) pushed to the right margin."""
        p.paragraph_format.tab_stops.add_tab_stop(text_width, WD_TAB_ALIGNMENT.RIGHT)
        for text, kw in left_parts:
            write(p, text, **kw)
        if right:
            write(p, "\t" + right, 9.5, color=muted)

    # Name, the role this CV is for, and how to reach them.
    write(para(0, 1), name, 22, bold=True, color=ink)
    if cv.headline:
        write(para(0, 3), cv.headline, 11.5, bold=True, color=accent)
    contact = [profile.get(k) for k in ("location", "phone", "email", "linkedin")]
    if any(contact):
        write(para(0, 4), "  ·  ".join(c for c in contact if c), 9.5, color=muted)

    if cv.about_paragraphs:
        heading(profile.get("profile_heading") or "Executive Profile")
        for text in cv.about_paragraphs:
            write(para(0, 4), text)
    if cv.core_competencies:
        heading("Core Skills")
        skills = [s.strip() for s in re.split(r"\s*[|·•]\s*", cv.core_competencies) if s.strip()]
        write(para(0, 2), "  ·  ".join(skills))
    if cv.key_achievements:
        heading(cv.achievements_title or "Key Achievements")
        for item in cv.key_achievements:
            bullet(item)
    if cv.work_experience:
        heading("Professional Experience")
        for i, entry in enumerate(cv.work_experience):
            with_right(para(8 if i else 2, 0, keep=True), [(entry.role_title, {"size": 11, "bold": True})], entry.period)
            if entry.company:
                write(para(0, 2, keep=True), entry.company, 10, italic=True, color=muted)
            if entry.role_description:
                write(para(0, 2, keep=bool(entry.bullets)), entry.role_description)
            for item in entry.bullets:
                bullet(item)
    if profile.get("education"):
        heading("Education")
        for edu in profile["education"]:
            detail = edu.get("detail", "")
            short = detail if len(detail) <= 24 else ""
            with_right(para(2, 0, keep=True), [(edu.get("credential", ""), {"size": 10.5, "bold": True})], short)
            below = "  ·  ".join(x for x in (edu.get("institution", ""), "" if short else detail) if x)
            if below:
                write(para(0, 3), below, 10, color=muted)
    for key, title in (("certifications", "Professional Certifications"), ("training", "Training"), ("awards", "Awards")):
        if profile.get(key):
            heading(title)
            for item in profile[key]:
                bullet(item)
    if profile.get("languages"):
        heading("Languages")
        write(para(0, 2), "  ·  ".join(profile["languages"]))

    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def cv_file_name(job: dict) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", f"{job['company']}_{job['title']}").strip("_")[:60].rstrip("_") or "Role"
    person = re.sub(r"[^A-Za-z0-9]+", "_", CANDIDATE.name).strip("_")
    return f"{slug}_{person}_CV.docx"


def attach_cvs(jobs: list[dict], profile: dict, out_dir: Path) -> None:
    """Render each stored CV to DOCX, give it a unique attachment name, and keep
    a copy in the run folder."""
    used: set[str] = set()
    for job in jobs:
        if not job.get("cv"):
            continue
        try:
            data = render_cv_docx(TailoredCV.model_validate(job["cv"]), profile)
        except Exception as exc:  # noqa: BLE001 - one broken CV must not lose the digest
            log.error("  cv render failed (%s): %s", job["title"], exc)
            continue
        name = base = cv_file_name(job)
        n = 2
        while name in used:
            name = base.replace(".docx", f"_{n}.docx")
            n += 1
        used.add(name)
        job["cv_file_name"], job["cv_bytes"] = name, data
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / name).write_bytes(data)
        log.info("  cv %7s bytes  %s", f"{len(data):,}", name)


# ------------------------------------------------------------ 8. email --
def _e(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _card(job: dict, num: int) -> str:
    """One job card - production markup minus the web-only download/generate blocks.
    Everything scraped or model-written is HTML-escaped."""
    fit_verdict = job.get("fit_verdict") or verdict(int(job.get("fit_score") or 0))
    badge = BADGE[fit_verdict]

    names = CANDIDATE.track_names
    track = job.get("selected_track") if job.get("selected_track") in names else 1
    track_name = _e(names[track])
    secondary = job.get("secondary_track")
    conf = CONFIDENCE_CONFIG.get(job.get("track_selection_confidence") or "", CONFIDENCE_CONFIG["medium"])
    tailor = TAILORING_CONFIG.get(job.get("tailoring_level") or "", TAILORING_CONFIG["moderate"])

    fit_score = _clamp(job.get("fit_score"))
    ats_score = _clamp(job.get("ats_score"))
    interview_score = _clamp(job.get("interview_score"))

    summary = _e(str(job.get("summary") or "").replace("ملخص الوظيفة:", "").strip())
    reasoning = _e(str(job.get("reasoning") or "").replace("سبب التصنيف:", "").strip())
    arabic_box = ""
    if (summary or reasoning) and not ARABIC_RE.search(summary + reasoning):
        # Free mode writes English (an excerpt of the posting + what matched): same box, left to right.
        arabic_box = (
            '<div style="background:#F8FAFC;border:1px solid #E2E8F0;'
            "border-left:4px solid #2563EB;padding:14px 18px;border-radius:8px;"
            'margin-bottom:18px;font-size:13px;color:#1E293B;line-height:1.6;">'
            '<ul style="margin:0;padding-left:20px;list-style-type:disc;">'
            + (f'<li style="margin-bottom:8px;"><strong>About the role:</strong> {summary}</li>' if summary else "")
            + (f"<li><strong>Why it fits:</strong> {reasoning}</li>" if reasoning else "")
            + "</ul></div>"
        )
    elif summary or reasoning:
        arabic_box = (
            '<div dir="rtl" style="background:#F8FAFC;border:1px solid #E2E8F0;'
            "border-right:4px solid #2563EB;padding:14px 18px;border-radius:8px;"
            'margin-bottom:18px;font-size:13px;color:#1E293B;line-height:1.6;text-align:right;">'
            '<ul style="margin:0;padding-right:20px;list-style-type:disc;">'
            f'<li style="margin-bottom:8px;"><strong>1. ملخص للوظيفة:</strong> {summary}</li>'
            f"<li><strong>2. سبب التصنيف ({conf['text']}):</strong> {reasoning}</li>"
            "</ul></div>"
        )

    secondary_line = ""
    if secondary in names and secondary != track:
        secondary_line = (
            '<div style="margin-top:4px;font-size:12px;color:#64748B;">'
            f"↳ Secondary Track {secondary}: {_e(names[secondary])}</div>"
        )

    attachment_box = ""
    if job.get("cv_file_name"):
        attachment_box = (
            '<div style="background:#FEF3C7;border:1px solid #F59E0B;border-radius:6px;'
            'padding:12px 16px;margin-bottom:18px;font-size:12.5px;color:#78350F;">'
            f"📎 <strong>Attached CV File #{num}:</strong> "
            f'<code style="background:#FDE68A;padding:2px 6px;border-radius:4px;font-weight:700;">'
            f'{_e(job["cv_file_name"])}</code></div>'
        )

    url = job["url"] if str(job.get("url", "")).startswith(("https://", "http://")) else "#"
    url = _e(url)
    return f"""<!-- JOB CARD #{num} -->
<div style="background:#FFFFFF;border:1px solid #E2E8F0;border-radius:10px;padding:24px;margin-bottom:26px;box-shadow:0 2px 8px rgba(0,0,0,0.03);">
  <table width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-bottom:12px;">
    <tr>
      <td style="vertical-align:middle;">
        <span style="display:inline-block;background:#0F172A;color:#FFF;font-size:11px;font-weight:800;padding:4px 10px;border-radius:4px;letter-spacing:0.5px;">JOB #{num}</span>
        <span style="display:inline-block;background:{tailor["bg"]};color:{tailor["color"]};font-size:11px;font-weight:700;padding:3px 9px;border-radius:12px;border:1px solid {tailor["border"]};margin-left:6px;">{tailor["icon"]} {tailor["text"]}</span>
      </td>
      <td align="right" style="vertical-align:middle;">
        <span dir="ltr" style="display:inline-block;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:800;white-space:nowrap;line-height:1.2;{badge["style"]}">{badge["text"]}</span>
      </td>
    </tr>
  </table>
  <h2 style="font-size:18px;font-weight:800;color:#0F172A;margin:6px 0 4px 0;line-height:1.3;word-wrap:break-word;overflow-wrap:break-word;">{_e(job["title"])}</h2>
  <div style="font-size:12.5px;color:#64748B;font-weight:600;margin-bottom:16px;">{_e(job["company"])} &bull; 📍 {_e(job["location"])}</div>
  <div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:8px;padding:14px 16px;margin-bottom:18px;">
    <table width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-bottom:10px;">
      <tr>
        <td width="34%" style="vertical-align:middle;">
          <div style="font-size:11px;font-weight:700;color:#64748B;text-transform:uppercase;letter-spacing:0.5px;">Weighted Overall Fit</div>
          <div style="font-size:20px;font-weight:800;color:#0F172A;">{fit_score}%</div>
        </td>
        <td width="33%" style="vertical-align:middle;border-left:1px solid #E2E8F0;padding-left:12px;">
          <div style="font-size:11px;font-weight:700;color:#64748B;text-transform:uppercase;letter-spacing:0.5px;">ATS Match (45%)</div>
          <div style="font-size:18px;font-weight:800;color:#2563EB;">{ats_score}%</div>
        </td>
        <td width="33%" style="vertical-align:middle;border-left:1px solid #E2E8F0;padding-left:12px;">
          <div style="font-size:11px;font-weight:700;color:#64748B;text-transform:uppercase;letter-spacing:0.5px;">Interview Match (55%)</div>
          <div style="font-size:18px;font-weight:800;color:#7C3AED;">{interview_score}%</div>
        </td>
      </tr>
    </table>
    <div style="background:#E2E8F0;height:8px;border-radius:4px;overflow:hidden;">
      <div style="background:{badge["bar"]};width:{fit_score}%;height:100%;border-radius:4px;"></div>
    </div>
  </div>
  <div style="margin-bottom:14px;font-size:12.5px;color:#334155;">
    <strong>🎯 Primary Track {track}:</strong> {track_name}
    <span style="display:inline-block;background:{conf["bg"]};color:{conf["color"]};font-size:10.5px;font-weight:700;padding:2px 7px;border-radius:4px;border:1px solid {conf["border"]};margin-left:4px;">{conf["icon"]} {conf["text"]}</span>
    {secondary_line}
  </div>
  {arabic_box}
  {attachment_box}
  <table cellspacing="0" cellpadding="0" border="0">
    <tr>
      <td>
        <a href="{url}" target="_blank" style="display:inline-block;background:#059669;color:#FFF;text-decoration:none;font-size:13px;font-weight:700;padding:10px 20px;border-radius:6px;margin-right:10px;">🚀 Apply Now</a>
        <a href="{url}" target="_blank" style="display:inline-block;background:#FFF;color:#2563EB;text-decoration:none;font-size:13px;font-weight:700;padding:9px 18px;border-radius:6px;border:1px solid #2563EB;margin-right:10px;">🔗 View Job Posting</a>
      </td>
    </tr>
  </table>
</div>"""


def render_email(jobs: list[dict], considered: list[dict] | None = None) -> str:
    """Jinja render with the production template and context keys.

    `jobs` become cards; `considered` (everything evaluated, default `jobs`)
    drives the counters, so Total / Moderate / Weak mean what they say.
    The web-only pieces (download button, generate-my-CV box, regenerate links)
    are left empty - this script has no web app behind it.
    """
    from jinja2 import Template

    ordered = sort_jobs(jobs)
    pool = jobs if considered is None else considered
    stats = {name: 0 for name in VERDICT_RANK}
    for job in pool:
        stats[job.get("fit_verdict") or "weak"] += 1
    cards = [_card(job, idx) for idx, job in enumerate(ordered, start=1)]

    return Template(EMAIL_TEMPLATE, autoescape=False).render(
        date_today=datetime.now().strftime("%b %d, %Y"),
        total_jobs=len(pool),
        high_fit_count=stats["strong"] + stats["good"],
        strong_count=stats["strong"],
        good_count=stats["good"],
        moderate_count=stats["moderate"],
        weak_count=stats["weak"],
        attachments_count=sum(1 for j in ordered if j.get("cv_bytes")),
        job_cards_html="\n".join(cards),
        download_btn="",
        period_label="Last 24 hours",
        strong_min=STRONG_MIN,
        good_min=GOOD_MIN,
        moderate_min=MODERATE_MIN,
        candidate_name=_e(CANDIDATE.name),
        system_label=_e(CANDIDATE.system_label),
        digest_title=_e(CANDIDATE.digest_title),
        footer_positioning=_e(CANDIDATE.footer_positioning),
    )


def send_email(jobs: list[dict], html_content: str) -> None:
    """Brevo transactional send. Raises on failure so the caller keeps the
    matches pending instead of marking them emailed."""
    import brevo
    from brevo.transactional_emails.types import (
        SendTransacEmailRequestAttachmentItem,
        SendTransacEmailRequestCcItem,
        SendTransacEmailRequestSender,
        SendTransacEmailRequestToItem,
    )

    def addresses(raw: str) -> list[str]:
        return [a.strip() for a in raw.split(",") if a.strip()]

    client = brevo.Brevo(api_key=need("BREVO_API_KEY"))
    # Each candidate has their own recipient variable and no fallback, so one
    # person's matches and CVs can never be mailed to another.
    recipients = addresses(need(CANDIDATE.email_to_env))
    cc = [SendTransacEmailRequestCcItem(email=a) for a in addresses(os.environ.get(CANDIDATE.email_cc_env, ""))]
    attachments = [
        SendTransacEmailRequestAttachmentItem(
            name=job["cv_file_name"],
            content=base64.b64encode(job["cv_bytes"]).decode("ascii"),
        )
        for job in jobs
        if job.get("cv_bytes")
    ]
    client.transactional_emails.send_transac_email(
        sender=SendTransacEmailRequestSender(
            email=need("EMAIL_FROM"),
            name=os.environ.get("BREVO_SENDER_NAME", "Executive Job Alerts"),
        ),
        to=[SendTransacEmailRequestToItem(email=a) for a in recipients],
        cc=cc or None,
        attachment=attachments or None,
        subject=CANDIDATE.email_subject.format(count=len(jobs), date=f"{datetime.now():%d %b}"),
        html_content=html_content,
    )
    log.info("emailed %d jobs (%d CVs) to %s", len(jobs), len(attachments), ", ".join(recipients))


# ------------------------------------------------------------- candidates ----
@dataclass
class Candidate:
    """Everything that differs between the people this pipeline serves.

    The built-in candidate is Ahmed (data/ + the prompts above). Others live in
    candidates/<key>/: candidate.json (search, tracks, rules), prompts/*.md and
    their knowledge base - see load_candidate()."""

    key: str
    name: str
    system_label: str               # digest header badge
    digest_title: str               # "<period> <digest_title>"
    footer_positioning: str         # plain text after the name in the digest footer
    email_subject: str              # str.format(count=..., date=...)
    email_to_env: str               # env var with this candidate's recipient(s); no fallback
    email_cc_env: str
    state_name: str                 # state file under STATE_DIR
    keywords: list[str]
    experience_levels: list[str]    # LinkedIn experienceLevel
    bayt_experience_levels: list[str]
    title_block_re: re.Pattern
    title_hint_re: re.Pattern
    track_names: dict[int, str]
    eval_system_prompt: str
    eval_user_prompt: str
    cv_system_prompt: str
    cv_user_prompt: str
    kb_placeholder: str             # where the knowledge base goes in eval_system_prompt
    knowledge: Callable[[], str]    # evaluator's knowledge base
    blueprint: Callable[[int], str | None]   # CV source for a track
    special_cv_source: Callable[[], str]     # appended for tailoring_level=special_cv
    cv_profile_file: Path
    cv_forbidden: list[tuple[str, re.Pattern]]  # (label, pattern) never allowed in a CV
    cv_free_text_metadata: bool     # pass the evaluator's free-text reasons to the CV call
    # Set from the person's profile (profiles.py) - edited in the web app.
    kind: str = "builtin"           # builtin (Ahmed) | advanced (candidate.json) | simple (made in the app)
    location: str = ""              # country searched; "" = LOCATION
    sources: list[str] = field(default_factory=list)          # default job sites; [] = SOURCES
    track_keywords: dict[int, list[str]] = field(default_factory=dict)   # free scoring's terms per track
    cv_content: Callable[[], dict] | None = None   # the standard CV (free mode), demo.json's "cv" shape
    cv_fixed: Callable[[], dict] | None = None     # contact + fixed CV sections, cv_profile.json's shape
    former_names: list[str] = field(default_factory=list)     # earlier names (CV file names)


def standard_cv(key: str) -> dict:
    """The standard CV for the original people, from data/demo.json (approved facts only)."""
    data = json.loads((DATA_DIR / "demo.json").read_text(encoding="utf-8"))
    return (data.get(key) or data["ahmed"])["cv"]


def seed_profile(c: Candidate) -> dict:
    """A profile for one of the original people, from their existing setup - what the app shows
    (and saves to profile.json) the first time their profile is edited."""
    p = profiles.blank(c.name)
    fixed = json.loads(c.cv_profile_file.read_text(encoding="utf-8")) if c.cv_profile_file.exists() else {}
    cv = standard_cv(c.key)
    place = [x.strip() for x in (fixed.get("location") or "").split(",")]
    p.update(headline=cv.get("pillar", ""), email=fixed.get("email", ""), phone=fixed.get("phone", ""),
             linkedin=fixed.get("linkedin", ""), city=place[0] if len(place) > 1 else "")
    country = c.location or LOCATION
    p["search"] = {"titles": list(c.keywords), "country": country if country in profiles.COUNTRIES else "Saudi Arabia",
                   "levels": [lv for lv in c.experience_levels if lv in profiles.LEVELS] or ["mid-senior"],
                   "sites": list(c.sources or SOURCES), "exclude": []}
    sep = next((s for s in (" | ", " · ", " • ", ", ") if s in cv.get("competencies", "")), " | ")
    p["cv"].update(
        summary=list(cv.get("about", [])), achievements=list(cv.get("achievements", [])),
        experience=[dict(e) for e in cv.get("experience", [])],
        skills=[s.strip() for s in cv.get("competencies", "").split(sep) if s.strip()],
        education=list(fixed.get("education", [])),
        **{k: list(fixed.get(k, [])) for k in ("certifications", "languages", "training", "awards")},
    )
    return p


def profile_for(c: Candidate) -> dict:
    """The person's profile: profile.json when saved, otherwise built from their setup."""
    return profiles.read(CANDIDATES_DIR, c.key) or seed_profile(c)


def _extend(pattern: re.Pattern, extra: list[str]) -> re.Pattern:
    return re.compile(f"(?:{pattern.pattern})|{word_pattern(extra).pattern}", re.I) if extra else pattern


def apply_profile(c: Candidate, prof: dict) -> Candidate:
    """A saved profile overrides an original person's search and CV facts. Their prompts and
    knowledge base (what ChatGPT reads) stay as they are."""
    s = prof["search"]
    c.name = prof.get("name") or c.name
    c.keywords = s["titles"] or c.keywords
    c.experience_levels = s["levels"] or c.experience_levels
    c.location, c.sources = s["country"], list(s["sites"])
    # New titles must get past the title filter; the person's own exclusions are added to it.
    c.title_hint_re = _extend(c.title_hint_re, [profiles._phrase_pattern(t) for t in s["titles"]])
    c.title_block_re = _extend(c.title_block_re, [profiles._phrase_pattern(w) for w in s["exclude"]])
    c.cv_content = lambda: profiles.cv_content(prof)
    c.cv_fixed = lambda: profiles.cv_fixed(prof)
    c.former_names = list(prof.get("former_names") or [])
    return c


def simple_candidate(key: str, prof: dict) -> Candidate:
    """Someone added in the app: everything comes from their profile.json."""
    s, name = prof["search"], prof.get("name") or key
    env = re.sub(r"[^A-Z0-9]+", "_", key.upper())
    titles = s["titles"] or ([prof["headline"]] if prof.get("headline") else [])
    track = profiles.track_name(prof)
    fill = {"{{NAME}}": name, "{{COUNTRY}}": s["country"], "{{TRACKS}}": profiles.tracks_text(prof)}

    def render(template: str) -> str:
        for placeholder, value in fill.items():
            template = template.replace(placeholder, value)
        return template

    return Candidate(
        key=key, name=name,
        system_label="Job Search Profile",
        digest_title="Job Digest",
        footer_positioning=" • ".join(x for x in (prof.get("headline"), profiles.location(prof)) if x),
        email_subject="{count} matching roles - {date}",
        email_to_env=f"EMAIL_TO_{env}", email_cc_env=f"EMAIL_CC_{env}",
        state_name=f"jobs_{key}.json",
        keywords=titles,
        experience_levels=s["levels"],
        bayt_experience_levels=BAYT_EXPERIENCE_LEVELS,
        title_block_re=word_pattern(profiles.block_patterns(prof)),
        title_hint_re=word_pattern(profiles.hint_patterns(prof)),
        track_names={1: track},
        eval_system_prompt=render(profiles.EVAL_SYSTEM),
        eval_user_prompt=profiles.EVAL_USER,
        cv_system_prompt=render(profiles.CV_SYSTEM),
        cv_user_prompt=render(profiles.CV_USER),
        kb_placeholder="{{PROFILE}}",
        knowledge=lambda: profiles.knowledge(prof),
        blueprint=lambda n: profiles.blueprint(prof) if n == 1 else None,
        special_cv_source=lambda: "",
        cv_profile_file=profiles.path(CANDIDATES_DIR, key),
        cv_forbidden=[],                # the person's own facts, written by them
        cv_free_text_metadata=True,
        kind="simple",
        location=s["country"], sources=list(s["sites"]),
        track_keywords={1: list(dict.fromkeys(prof["cv"]["skills"] + titles))},
        cv_content=lambda: profiles.cv_content(prof),
        cv_fixed=lambda: profiles.cv_fixed(prof),
        former_names=list(prof.get("former_names") or []),
    )


def _read_text(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.exists() else None


def ahmed_candidate() -> Candidate:
    return Candidate(
        key="ahmed",
        name="Ahmed Ramzy",
        system_label="Executive Intelligence System (EIS)",
        digest_title="Executive Job Digest",
        footer_positioning="Business Solutions & Strategic Advisory Leader • Riyadh, KSA",
        email_subject="{count} matching executive roles - {date}",
        email_to_env="EMAIL_TO",
        email_cc_env="EMAIL_CC",
        state_name="jobs.json",
        keywords=KEYWORDS,
        experience_levels=EXPERIENCE_LEVELS,
        bayt_experience_levels=BAYT_EXPERIENCE_LEVELS,
        title_block_re=word_pattern(TITLE_BLOCKLIST),
        title_hint_re=word_pattern(TITLE_HINTS),
        track_names=TRACK_NAMES,
        eval_system_prompt=EVAL_SYSTEM_PROMPT,
        eval_user_prompt=EVAL_USER_PROMPT,
        cv_system_prompt=CV_SYSTEM_PROMPT,
        cv_user_prompt=CV_USER_PROMPT,
        kb_placeholder="{{EIS}}",
        knowledge=lambda: EIS_FILE.read_text(encoding="utf-8"),
        blueprint=lambda track: _read_text(DATA_DIR / TRACK_FILES[track]) if track in TRACK_FILES else None,
        special_cv_source=lambda: EIS_FILE.read_text(encoding="utf-8"),
        cv_profile_file=CV_PROFILE_FILE,
        cv_forbidden=[("monetary value", MONEY_RE)],
        cv_free_text_metadata=True,
    )


# --- CIS (Career Intelligence System) knowledge bases -----------------------
# A CIS is the Phase-1 discovery record: sections of records, each with a
# classification and an allowed_use per channel. One record, two views:
#   evaluation  every record, tagged with its disclosure class (internal use)
#   cv          only records whose allowed_use.cv is exactly true
_CIS_TAGS = {"Use with caution": "Caution", "Confidential": "Confidential", "Unknown": "Unknown"}


def cis_allows(record: dict, channel: str) -> bool:
    """Export rule: a channel is open only on an explicit true. false and null
    (= not approved yet) are both closed - the record's default-deny policy."""
    return (record.get("allowed_use") or {}).get(channel) is True


def _cis_line(record: dict, channel: str | None, omit: set[str]) -> str | None:
    if record["id"] in omit or (channel and not cis_allows(record, channel)):
        return None
    line = f"- {record['label_ar']}: {record['value']}"
    if record.get("notes_ar"):
        line += f" ({record['notes_ar']})"
    if channel is None:
        tags = [_CIS_TAGS[record["classification"]]] if record["classification"] in _CIS_TAGS else []
        if record.get("verification_status") not in (None, "Candidate confirmed"):
            tags.append(record["verification_status"])
        if tags:
            line += f" [{' | '.join(tags)}]"
    return line


def render_cis(cis: dict, *, channel: str | None, sections, omit=()) -> str:
    """Render a CIS record as Markdown for a model. channel=None is the internal
    evaluation view; channel="cv" keeps only records cleared for CVs."""
    omit = set(omit)
    out: list[str] = []
    for section in cis["sections"]:
        if section["number"] not in sections:
            continue
        body = [line for line in (_cis_line(r, channel, omit) for r in section.get("records", [])) if line]
        for group in section.get("groups", []):
            lines = [line for line in (_cis_line(r, channel, omit) for r in group["records"]) if line]
            if not lines:
                continue                # a group with nothing cleared disappears, title included
            gid = group.get("achievement_id") or group.get("project_id") or group.get("story_id")
            meta = [group.get("evidence_grade"), f"see {group['achievement_ref']}" if group.get("achievement_ref") else None]
            meta = [m for m in meta if m]
            body.append(f"### {gid + ' — ' if gid else ''}{group['title_ar']}" + (f" ({'; '.join(meta)})" if meta else ""))
            if channel is None and group.get("evidence_basis_ar"):
                body.append(f"_{group['evidence_basis_ar']}_")
            body.extend(lines)
        if body:
            out.append(f"## {section['number']}. {section['title_en']} — {section['title_ar']}")
            if section.get("description_ar"):
                out.append(section["description_ar"])
            out.extend(body)
            out.append("")
    return "\n".join(out).strip() + "\n"


def render_tracks(tracks: dict[int, dict]) -> str:
    """Track list for an evaluation prompt's {{TRACKS}} placeholder."""
    return "\n\n".join(
        f"   - **Track {n}: {t['name']}**\n"
        f"     Select when center of gravity is: {t['center_of_gravity']}\n"
        f"     Keywords: {', '.join(t['keywords'])}."
        for n, t in sorted(tracks.items())
    )


def track_blueprint(number: int, track: dict, fact_sheet: str) -> str:
    """A CIS candidate's CV source for one track: the track's focus on top of
    the CV-approved fact sheet (the same facts for every track)."""
    lines = [
        f"TRACK {number}: {track['name']}",
        f"Positioning: {track['positioning']}",
        f"Center of gravity: {track['center_of_gravity']}",
        f"Track keywords: {', '.join(track['keywords'])}",
        f"Lead evidence, in this order: {', '.join(track.get('lead_evidence', []))}",
    ]
    if track.get("notes"):
        lines.append(f"Track notes: {track['notes']}")
    lines += [
        "",
        "CV-APPROVED FACT SHEET - every record below is cleared for CV use; nothing else is.",
        "Records are in Arabic; the CV is written in English.",
        "",
        fact_sheet,
    ]
    return "\n".join(lines)


def load_candidate(key: str | None) -> Candidate:
    """A person by key: Ahmed (built in), a candidates/<key>/candidate.json setup, or a
    profile made in the app. A saved profile.json applies to all three."""
    key = (key or "ahmed").strip().lower()
    prof = profiles.read(CANDIDATES_DIR, key) if profiles.KEY_RE.match(key) else None
    if key == "ahmed":
        c = ahmed_candidate()
    elif (CANDIDATES_DIR / key / "candidate.json").exists():
        c = _advanced_candidate(key)
    elif prof:
        return simple_candidate(key, prof)
    else:
        sys.exit(f"unknown candidate {key!r} (known: {', '.join(profiles.keys(CANDIDATES_DIR))})")
    if prof:
        return apply_profile(c, prof)
    c.cv_content = lambda: standard_cv(key)
    return c


def _advanced_candidate(key: str) -> Candidate:
    base = CANDIDATES_DIR / key
    config_file = base / "candidate.json"
    cfg = json.loads(config_file.read_text(encoding="utf-8"))

    tracks = {int(n): t for n, t in cfg["tracks"].items()}
    if set(tracks) != {1, 2, 3, 4, 5}:
        sys.exit(f"{config_file}: define tracks 1-5 (the evaluation schema has five)")
    prompts = {}
    for name in ("eval_system", "eval_user", "cv_system", "cv_user"):
        text = _read_text(base / "prompts" / f"{name}.md")
        if text is None:
            sys.exit(f"missing prompt {base / 'prompts' / (name + '.md')}")
        prompts[name] = text

    kb = cfg["knowledge"]
    if kb.get("format") != "cis-json":
        sys.exit(f"{config_file}: knowledge.format must be 'cis-json'")
    omit = kb.get("omit_ids", [])
    cache: dict[str, dict] = {}

    def cis() -> dict:
        if "cis" not in cache:
            cache["cis"] = json.loads((base / kb["file"]).read_text(encoding="utf-8"))
        return cache["cis"]

    def fact_sheet() -> str:
        return render_cis(cis(), channel="cv", sections=kb["cv_sections"], omit=omit)

    forbidden = [("monetary value", MONEY_RE)] if cfg.get("money_guard", True) else []
    forbidden += [(rule["label"], re.compile(rule["pattern"])) for rule in cfg.get("cv_forbidden", [])]

    return Candidate(
        key=key,
        name=cfg["name"],
        system_label=cfg["system_label"],
        digest_title=cfg["digest_title"],
        footer_positioning=cfg["footer_positioning"],
        email_subject=cfg["email_subject"],
        email_to_env=cfg["email_to_env"],
        email_cc_env=cfg.get("email_cc_env", f"EMAIL_CC_{key.upper()}"),
        state_name=cfg.get("state_file", f"jobs_{key}.json"),
        keywords=cfg["keywords"],
        experience_levels=cfg.get("experience_levels", EXPERIENCE_LEVELS),
        bayt_experience_levels=cfg.get("bayt_experience_levels", BAYT_EXPERIENCE_LEVELS),
        title_block_re=word_pattern(cfg.get("title_blocklist", TITLE_BLOCKLIST)),
        title_hint_re=word_pattern(cfg.get("title_hints", TITLE_HINTS)),
        track_names={n: t["name"] for n, t in tracks.items()},
        eval_system_prompt=prompts["eval_system"].replace("{{TRACKS}}", render_tracks(tracks)),
        eval_user_prompt=prompts["eval_user"],
        cv_system_prompt=prompts["cv_system"],
        cv_user_prompt=prompts["cv_user"],
        kb_placeholder=kb.get("placeholder", "{{CIS}}"),
        knowledge=lambda: render_cis(cis(), channel=None, sections=kb["evaluation_sections"], omit=omit),
        blueprint=lambda track: track_blueprint(track, tracks[track], fact_sheet()) if track in tracks else None,
        special_cv_source=lambda: "",
        cv_profile_file=base / cfg.get("cv_profile", "cv_profile.json"),
        cv_forbidden=forbidden,
        cv_free_text_metadata=cfg.get("cv_free_text_metadata", False),
        kind="advanced",
        track_keywords={n: list(t.get("keywords", [])) for n, t in tracks.items()},
    )


def export_knowledge(out_dir: Path) -> Path:
    """Write exactly what the models will see, for review before a real run."""
    out_dir.mkdir(parents=True, exist_ok=True)
    knowledge = CANDIDATE.knowledge()
    (out_dir / "evaluation_knowledge.md").write_text(knowledge, encoding="utf-8")
    (out_dir / "eval_system_prompt.md").write_text(
        CANDIDATE.eval_system_prompt.replace(CANDIDATE.kb_placeholder, knowledge), encoding="utf-8"
    )
    for track in sorted(CANDIDATE.track_names):
        blueprint = CANDIDATE.blueprint(track)
        if blueprint:
            (out_dir / f"track_{track}_cv_system_prompt.md").write_text(
                CANDIDATE.cv_system_prompt.replace("{{TRACK_BLUEPRINT}}", blueprint), encoding="utf-8"
            )
    return out_dir


CANDIDATE = ahmed_candidate()       # replaced in main() by --candidate / env CANDIDATE


# ---------------------------------------------------------------- state ----
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_state() -> dict:
    state: dict = {}
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    state.setdefault("seen", {})
    state.setdefault("pending", {})
    return state


def save_state(state: dict) -> None:
    """Atomic write - a crash mid-write must not wipe the seen list."""
    tmp = STATE_FILE.with_name(STATE_FILE.name + ".tmp")
    tmp.write_text(json.dumps(state, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, STATE_FILE)


def storable(job: dict) -> dict:
    return {k: v for k, v in job.items() if k not in ("cv_bytes", "cv_file_name")}


def prune_pending(state: dict) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=PENDING_MAX_AGE_DAYS)
    for url, job in list(state["pending"].items()):
        try:
            selected = datetime.fromisoformat(job.get("selected_at", ""))
        except ValueError:
            continue
        if selected < cutoff:
            log.warning("pending: dropping %s - %s (never emailed, older than %d days)",
                        job.get("title"), job.get("company"), PENDING_MAX_AGE_DAYS)
            del state["pending"][url]


def candidate_runs_dir() -> Path:
    return RUNS_DIR / CANDIDATE.key


def new_run_dir() -> Path:
    path = candidate_runs_dir() / datetime.now().strftime("%Y%m%d-%H%M%S")
    path.mkdir(parents=True, exist_ok=True)
    return path


def prune_runs() -> None:
    if not candidate_runs_dir().exists():
        return
    cutoff = time.time() - RUNS_KEEP_DAYS * 86400
    for path in candidate_runs_dir().iterdir():
        if path.is_dir() and path.stat().st_mtime < cutoff:
            shutil.rmtree(path, ignore_errors=True)


LOCK_STALE_SECONDS = 3 * 3600       # a lock older than this is from a crashed run


def lock_path() -> Path:
    return candidate_runs_dir() / ".lock"


def acquire_lock() -> Path | None:
    """One run per candidate at a time (cron, a terminal and the web page can
    all start one). Returns the lock path, or None if another run holds it."""
    path = lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            age = time.time() - path.stat().st_mtime
        except FileNotFoundError:
            return acquire_lock()       # released between the two calls
        if age < LOCK_STALE_SECONDS:
            return None
        log.warning("removing stale lock %s (%.0f min old)", path, age / 60)
        path.unlink(missing_ok=True)
        return acquire_lock()
    with os.fdopen(fd, "w") as handle:
        handle.write(f"{os.getpid()} {now_iso()}")
    return path


# ------------------------------------------------------------------ main ----
DEMO = False                        # --demo: sample postings + simulated AI, nothing emailed (demo_mode.py)


def main(argv: list[str] | None = None) -> int:
    global CANDIDATE, STATE_FILE, STATE_DIR, RUNS_DIR, DEMO, LOCATION
    parser = argparse.ArgumentParser(
        description="Job automation: scrape, evaluate, tailor CVs; keep them for the web app (and email them if EMAIL_DIGEST=on).")
    parser.add_argument("--candidate",
                        help="whose search this is: ahmed (default) or a folder in candidates/ (env CANDIDATE)")
    parser.add_argument("--dry-run", action="store_true",
                        help="do everything except the email; matches stay pending for the next real run")
    parser.add_argument("--limit", type=int, default=0, help="evaluate at most N new jobs")
    parser.add_argument("--from-file", type=Path,
                        help="replay a saved scrape (e.g. runs/<candidate>/<stamp>/raw.json) instead of calling Apify")
    parser.add_argument("--sources", help="comma-separated sources for this run, e.g. linkedin,bayt")
    parser.add_argument("--no-cv", action="store_true", help="skip CV generation")
    parser.add_argument("--export-knowledge", action="store_true",
                        help="write what the models will see to runs/<candidate>/knowledge/ and exit (no API calls)")
    parser.add_argument("--demo", action="store_true",
                        help="try the app without API keys: sample postings, simulated AI, nothing emailed")
    parser.add_argument("--data-dir", type=Path,
                        help="keep jobs*.json and runs/ in this folder instead of next to this script")
    args = parser.parse_args(argv)

    setup_logging()
    load_env()
    apply_env()
    DEMO = args.demo
    if args.data_dir:
        STATE_DIR, RUNS_DIR = args.data_dir, args.data_dir / "runs"
    CANDIDATE = load_candidate(args.candidate or os.environ.get("CANDIDATE"))
    STATE_FILE = STATE_DIR / CANDIDATE.state_name
    if CANDIDATE.location:
        LOCATION = CANDIDATE.location           # the country chosen in this person's profile
    if args.export_knowledge:
        out = export_knowledge(candidate_runs_dir() / "knowledge")
        log.info("knowledge for %s written to %s", CANDIDATE.name, out)
        return 0
    if not CANDIDATE.keywords:
        log.error("stopped: %s's profile has no job titles to search - add some in Profile", CANDIDATE.name)
        return 1
    sources = ([s.strip().lower() for s in args.sources.split(",") if s.strip()] if args.sources
               else CANDIDATE.sources or SOURCES)
    check_sources(sources)

    lock = acquire_lock()
    if lock is None:
        log.error("another run for %s is in progress (%s) - not starting a second one", CANDIDATE.name, lock_path())
        return 2
    try:
        return run(args, sources)
    except RunStopped as exc:
        log.error("stopped: %s", exc)
        return 1
    finally:
        lock.unlink(missing_ok=True)


def run(args: argparse.Namespace, sources: list[str]) -> int:
    """One full pipeline run for the active CANDIDATE (main() holds the lock)."""
    state = load_state()
    prune_pending(state)
    prune_runs()
    run_dir = new_run_dir()
    log.info("run %s - %s, %s, sources: %s", run_dir.name, CANDIDATE.name, LOCATION, ", ".join(sources))

    # 1-4: scrape -> normalize -> dedupe -> filter
    if args.from_file:
        raw = json.loads(args.from_file.read_text(encoding="utf-8"))
        log.info("scrape: replaying %d items from %s", len(raw), args.from_file)
    elif DEMO:
        import demo_mode

        raw = demo_mode.postings(CANDIDATE.key, base=CANDIDATES_DIR)
        log.info("scrape: demo - %d sample postings (no Apify call)", len(raw))
        write_json(run_dir / "raw.json", raw)
    else:
        raw = scrape(CANDIDATE.keywords, sources, SEARCH_HOURS)     # exactly the look-back chosen in Settings
        write_json(run_dir / "raw.json", raw)
    jobs = normalize(raw)
    if not args.from_file and not DEMO:
        jobs = recent_only(jobs, SEARCH_HOURS)
    remember_logos(state, jobs)
    seen_signatures = {v["signature"] for v in state["seen"].values() if v.get("signature")}
    seen_keys = {same_job_key(v.get("title", ""), v.get("company", "")) for v in state["seen"].values()} - {""}
    jobs = dedupe(jobs, set(state["seen"]) | set(state["pending"]), seen_signatures, seen_keys)
    jobs = filter_jobs(jobs)
    if args.limit:
        jobs = jobs[: args.limit]
    if not args.from_file and not DEMO:
        fill_descriptions(jobs)                     # before scoring, so the score can read the whole posting

    client = None

    def ai_client():
        nonlocal client
        if client is None:
            if DEMO:
                import demo_mode

                client = demo_mode.DemoAI(CANDIDATE, sys.modules[__name__])
            elif AI_MODE == "basic":
                import basic_ai

                log.info("scoring: free keyword matching (no AI service; AI_MODE=basic)")
                client = basic_ai.BasicAI(CANDIDATE, sys.modules[__name__])
            else:
                client = make_ai_client()
        return client

    # 5-6: evaluate -> verdict
    try:
        evaluated = evaluate(jobs, ai_client(), CANDIDATE.knowledge()) if jobs else []
    except AIUnavailable as exc:
        if DEMO or AI_MODE != "chatgpt":
            raise
        # ChatGPT is on but can't be used (no credit, rejected key): still give a result, for free.
        import basic_ai

        log.warning("chatgpt unavailable: %s - this search is scored with the free matching instead", exc)
        client = basic_ai.BasicAI(CANDIDATE, sys.modules[__name__])
        evaluated = evaluate(jobs, client, CANDIDATE.knowledge())
    stamp = now_iso()
    for job in evaluated:
        state["seen"][job["url"]] = {
            "title": job["title"],
            "company": job["company"],
            "signature": job["signature"],
            "fit_score": job["fit_score"],
            "fit_verdict": job["fit_verdict"],
            "evaluated_at": stamp,
            "emailed_at": None,
        }
    fresh = [j for j in evaluated if j["fit_verdict"] in MIN_VERDICT]
    for job in fresh:
        job["selected_at"] = stamp
        state["pending"][job["url"]] = storable(job)
    save_state(state)                   # paid-for evaluations persist before anything else can fail
    write_json(run_dir / "evaluated.json", [storable(j) for j in evaluated])

    fresh_urls = {j["url"] for j in fresh}
    carried = [dict(job) for url, job in state["pending"].items() if url not in fresh_urls]
    if carried:
        log.info("pending: %d earlier matches not emailed yet are included", len(carried))
    digest = fresh + carried

    # 7: tailored CVs (stored in state, so a dry run's CVs are reused by the real run)
    if not args.no_cv:
        cv_jobs = [j for j in digest if j["fit_score"] >= CV_MIN_FIT_SCORE and not j.get("cv")]
        if cv_jobs:
            log.info("cv: generating %d tailored CVs (>= %d fit)", len(cv_jobs), CV_MIN_FIT_SCORE)
        for job in cv_jobs:
            cv = tailor_cv(job, ai_client())
            if cv:
                job["cv"] = cv.model_dump()
                state["pending"][job["url"]]["cv"] = job["cv"]
                save_state(state)
        attach_cvs(digest, load_cv_profile(), run_dir / "cvs")

    if hasattr(client, "usage_line"):
        log.info(client.usage_line())

    # 8: digest
    html_content = render_email(digest, evaluated + carried)
    (run_dir / "digest.html").write_text(html_content, encoding="utf-8")
    for job in sort_jobs(digest):
        log.info("  %-8s %3d  %s - %s%s", job["fit_verdict"], job["fit_score"], job["title"], job["company"],
                 "  [cv]" if job.get("cv_bytes") else "")
    log.info("selected %d of %d evaluated, %d carried over -> %s",
             len(fresh), len(evaluated), len(carried), run_dir / "digest.html")

    def record(outcome: str) -> None:
        """runs/<stamp>/run.json - what this run was and what happened to its digest."""
        write_json(run_dir / "run.json", {
            "mode": "replay" if args.from_file else ("preview" if args.dry_run else "live"),
            "outcome": outcome,                     # previewed | nothing_to_send | saved | sent | send_failed
            "email": EMAIL_DIGEST,
            # Who wrote the CVs: ChatGPT ones are kept as written; free ones are rebuilt per job on download.
            "ai": "demo" if DEMO else ("chatgpt" if isinstance(client, OpenAIAI) else "basic"),
            "evaluated": len(evaluated),
            "digest_jobs": len(digest),
            "recipients": ("demo inbox" if DEMO else os.environ.get(CANDIDATE.email_to_env, "")) if outcome == "sent" else "",
            "demo": DEMO,
            "finished_at": now_iso(),
        })

    if args.dry_run:
        log.info("dry run: email not sent; %d matches stay pending for the next real run", len(digest))
        record("previewed")
        return 0
    if not digest:
        log.info("nothing to send")
        record("nothing_to_send")
        return 0
    if not EMAIL_DIGEST:
        # App-only delivery: the matches, their links and CVs are read in the web app.
        for job in digest:
            state["pending"].pop(job["url"], None)
        save_state(state)
        log.info("saved: %d matches and their CVs are in the app (the email digest is off)", len(digest))
        record("saved")
        return 0
    if DEMO:
        log.info("demo: the digest was not emailed - %d matches are marked as sent in the demo data only", len(digest))
    else:
        try:
            send_email(digest, html_content)
        except Exception:  # noqa: BLE001 - keep them pending, fail the run for cron/systemd
            log.exception("email failed - %d matches stay pending and are retried next run", len(digest))
            record("send_failed")
            return 1
    sent_at = now_iso()
    for job in digest:
        state["pending"].pop(job["url"], None)
        if job["url"] in state["seen"]:
            state["seen"][job["url"]]["emailed_at"] = sent_at
    save_state(state)
    record("sent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
