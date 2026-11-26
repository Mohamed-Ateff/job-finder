"""People the app searches for, and everything about them that is edited in the app.

Each person is a folder in candidates/<key>/ holding profile.json: who they are, what to
search for, and the facts their CV is built from. A profile made in the app has only that
file. The two original people keep their richer setup (Ahmed's is built into
job_automation.py; Atef's is candidate.json plus his discovery record). For them,
profile.json - written the first time their profile is saved in the app - overrides the
search settings and the CV facts, while ChatGPT still reads their knowledge base.

Pure data: this module never imports job_automation, so the pipeline and the web app can
both use it. Folders are passed in (`base` = the candidates folder).
"""

from __future__ import annotations

import json
import re
import shutil
import time
import unicodedata
from pathlib import Path

PROFILE_FILE = "profile.json"
BUILTIN = "ahmed"                       # Ahmed's setup lives in job_automation.py, not in a folder
DELETED = "_deleted"                    # deleted profiles are moved here, never erased
LEVELS = ["entry", "associate", "mid-senior", "director", "executive"]
EARLY_LEVELS = {"entry", "associate"}
COUNTRIES = ["Saudi Arabia", "United Arab Emirates", "Qatar", "Kuwait", "Bahrain", "Oman", "Egypt"]
SITES = ["linkedin", "indeed", "bayt"]
WORK_MODES = ["on-site", "hybrid", "remote"]
JOB_TYPES = ["full-time", "part-time", "contract"]
# How the person wants to work (mostly from the questionnaire): shown in the app and read by
# ChatGPT, never written into a CV.
PREFERENCE_TEXT = {"years": 20, "relocate": 160, "notice": 160, "salary": 160, "visa": 160}
KEY_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")

# Limits keep a profile a profile (and a pasted book out of every prompt).
SHORT, LONG, ITEMS = 160, 2000, 60
CV_LISTS = ("achievements", "skills", "certifications", "languages", "training", "awards")
GROUPS = ("search", "cv", "preferences")         # the parts of a profile that are dicts of their own

# Words that say nothing about the field: "manager" alone would let every manager job through.
GENERIC_TITLE_WORDS = {
    "manager", "senior", "sr", "lead", "leader", "head", "director", "the", "of", "for", "and", "in", "to",
    "a", "an", "jr", "junior", "associate", "assistant", "executive", "officer", "specialist", "chief",
    "vice", "president", "general", "principal", "staff", "team", "remote", "hybrid", "full", "time",
}
JUNIOR_TITLE_PATTERNS = [r"interns?", r"internships?", r"trainees?"]
JUNIOR_EXTRA_PATTERNS = [r"junior", r"jr", r"graduates?"]


def blank(name: str = "") -> dict:
    return {
        "version": 1,
        "name": name,
        "headline": "",
        "email": "", "phone": "", "linkedin": "", "website": "", "city": "", "nationality": "",
        "notify_email": "",                 # where the best matches of each search are emailed, with their CVs
        # keywords: words that show a posting is in the person's field (free scoring looks for them);
        # exclude_companies: employers whose jobs are dropped before scoring.
        "search": {"titles": [], "country": "Saudi Arabia", "levels": ["mid-senior"],
                   "sites": ["linkedin", "indeed"], "exclude": [], "keywords": [], "exclude_companies": []},
        "cv": {"summary": [], "achievements": [], "experience": [], "skills": [], "education": [],
               "certifications": [], "languages": [], "training": [], "awards": []},
        "preferences": {"years": "", "work_modes": [], "job_types": [], "relocate": "", "notice": "",
                        "salary": "", "visa": "", "other": ""},
        "notes": "",
        "former_names": [],
    }


# ------------------------------------------------------------------ cleaning --
def _text(value, limit: int = SHORT) -> str:
    if value is None:
        return ""
    text = re.sub(r"[ \t\r\f\v]+", " ", str(value)).strip()
    return text[:limit]


def _para(value, limit: int = LONG) -> str:
    lines = [re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in str(value or "").split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()[:limit]


def _items(values, limit: int = SHORT, most: int = ITEMS) -> list[str]:
    if isinstance(values, str):
        values = values.split("\n")
    out: list[str] = []
    for value in values or []:
        item = _text(value, limit).lstrip("•·-–*▪◦● ").strip()
        if item and item.lower() not in {o.lower() for o in out}:
            out.append(item)
    return out[:most]


def clean(data: dict, *, base: dict | None = None) -> dict:
    """A profile as the app sends it -> the stored shape. Unknown keys are dropped, text is
    trimmed and capped, choices are checked. Raises ValueError with a readable reason."""
    out = blank()
    base = base or {}
    data = data or {}
    out["name"] = _text(data.get("name"), 80)
    if not out["name"]:
        raise ValueError("Add the person's full name.")
    for key in ("headline", "city", "phone"):
        out[key] = _text(data.get(key))
    email = _text(data.get("email"))
    if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ValueError("The email address doesn't look right.")
    out["email"] = email
    linkedin = _text(data.get("linkedin"))
    if linkedin and re.search(r"[<>\"'\s]|javascript:", linkedin, re.I):
        raise ValueError("The LinkedIn address doesn't look right.")
    out["linkedin"] = re.sub(r"^https?://(www\.)?", "", linkedin)
    website = _text(data.get("website"))
    if website and re.search(r"[<>\"'\s]|javascript:", website, re.I):
        raise ValueError("The website address doesn't look right.")
    out["website"] = re.sub(r"^https?://(www\.)?", "", website).rstrip("/")
    out["nationality"] = _text(data.get("nationality"), 60)
    notify = _text(data.get("notify_email"))
    if notify and not all(re.fullmatch(r"[^@\s,]+@[^@\s,]+\.[^@\s,]+", a.strip()) for a in notify.split(",")):
        raise ValueError("The email for matches doesn't look right.")
    out["notify_email"] = ", ".join(a.strip() for a in notify.split(",") if a.strip())

    search = data.get("search") or {}
    out["search"]["titles"] = _items(search.get("titles"), 80, 24)
    country = _text(search.get("country")) or "Saudi Arabia"
    if country not in COUNTRIES:
        raise ValueError(f"Choose one of these countries: {', '.join(COUNTRIES)}.")
    out["search"]["country"] = country
    levels = [lv for lv in LEVELS if lv in (search.get("levels") or [])]
    out["search"]["levels"] = levels or ["mid-senior"]
    sites = [s for s in SITES if s in (search.get("sites") or [])]
    out["search"]["sites"] = sites or ["linkedin"]
    out["search"]["exclude"] = _items(search.get("exclude"), 40, 30)
    out["search"]["keywords"] = _items(search.get("keywords"), 60, 30)
    out["search"]["exclude_companies"] = _items(search.get("exclude_companies"), 80, 30)

    prefs = data.get("preferences") or {}
    for key, limit in PREFERENCE_TEXT.items():
        out["preferences"][key] = _text(prefs.get(key), limit)
    for key, allowed in (("work_modes", WORK_MODES), ("job_types", JOB_TYPES)):
        chosen = prefs.get(key) if isinstance(prefs.get(key), list) else []
        out["preferences"][key] = [x for x in allowed if x in chosen]
    out["preferences"]["other"] = _para(prefs.get("other"), LONG)

    cv = data.get("cv") or {}
    summary = cv.get("summary") or []
    if isinstance(summary, str):
        summary = re.split(r"\n\s*\n", summary)
    out["cv"]["summary"] = [p for p in (_para(s, 900) for s in summary) if p][:4]
    for key in CV_LISTS:
        out["cv"][key] = _items(cv.get(key), 300 if key == "achievements" else SHORT)
    out["cv"]["experience"] = [
        {
            "role_title": _text(e.get("role_title")),
            "company": _text(e.get("company")),
            "period": _text(e.get("period"), 60),
            "role_description": _text(e.get("role_description"), 400),
            "bullets": _items(e.get("bullets"), 300, 12),
        }
        for e in (cv.get("experience") or [])[:20]
        if isinstance(e, dict) and (_text(e.get("role_title")) or _text(e.get("company")))
    ]
    out["cv"]["education"] = [
        {"credential": _text(e.get("credential")), "institution": _text(e.get("institution")),
         "detail": _text(e.get("detail"))}
        for e in (cv.get("education") or [])[:10]
        if isinstance(e, dict) and (_text(e.get("credential")) or _text(e.get("institution")))
    ]
    out["notes"] = _para(data.get("notes"), LONG)

    former = list(base.get("former_names") or [])
    if base.get("name") and base["name"] != out["name"] and base["name"] not in former:
        former.append(base["name"])        # CVs already made keep the old name in their file name
    out["former_names"] = former[-10:]
    return out


# ------------------------------------------------------------------- storage --
def path(base: Path, key: str) -> Path:
    return base / key / PROFILE_FILE


def read(base: Path, key: str) -> dict | None:
    try:
        data = json.loads(path(base, key).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    merged = blank()
    merged.update({k: v for k, v in data.items() if k not in GROUPS})
    for group in GROUPS:
        merged[group].update(data.get(group) or {})
    return merged


def write(base: Path, key: str, data: dict) -> None:
    target = path(base, key)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(target)


REMOVED_MARK = "_removed_builtin"          # in the candidates folder: the built-in profile was deleted


def keys(base: Path) -> list[str]:
    """Everyone in the candidates folder (Ahmed, who is built in, comes first unless deleted)."""
    found = {p.parent.name for pattern in ("*/candidate.json", f"*/{PROFILE_FILE}") for p in base.glob(pattern)}
    found = {k for k in found if not k.startswith("_") and KEY_RE.match(k)}
    builtin = [] if (base / REMOVED_MARK).exists() else [BUILTIN]
    return [*builtin, *sorted(found - {BUILTIN})]


def kind(base: Path, key: str) -> str:
    """builtin (Ahmed), advanced (a candidate.json and knowledge base) or simple (made in the app)."""
    if key == BUILTIN:
        return "builtin"
    return "advanced" if (base / key / "candidate.json").exists() else "simple"


def slug(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")[:30].strip("-")


def new_key(base: Path, name: str, taken: set[str]) -> str:
    """A folder name for a new person: from the name, unique, never reusing old data files."""
    stem = slug(name) or "person"
    used = set(taken) | {p.name for p in base.iterdir() if p.is_dir()} if base.exists() else set(taken)

    deleted = {p.name.rsplit("-", 2)[0] for p in (base / DELETED).iterdir()} if (base / DELETED).is_dir() else set()

    def free(candidate: str) -> bool:
        # Never reuse a name with data behind it: a deleted profile, saved jobs or old searches.
        return (candidate not in used and candidate != BUILTIN and candidate not in deleted
                and not (base.parent / f"jobs_{candidate}.json").exists()
                and not (base.parent / "runs" / candidate).exists())

    key, n = stem, 2
    while not free(key):
        key, n = f"{stem}-{n}", n + 1
    return key


def create(base: Path, profile: dict, taken: set[str]) -> str:
    key = new_key(base, profile.get("name", ""), taken)
    write(base, key, profile)
    return key


def delete(base: Path, key: str) -> Path:
    """Remove anyone from the app by moving their folder to candidates/_deleted/ (it can be moved
    back by hand; their jobs and CVs stay where they are). The built-in profile has no folder of its
    own to move: its saved edits are moved, and a mark hides it."""
    if key not in keys(base):
        raise ValueError("There is no such profile.")
    target = base / DELETED / f"{key}-{time.strftime('%Y%m%d-%H%M%S')}"
    target.mkdir(parents=True, exist_ok=True)
    if key == BUILTIN:
        if (base / key).is_dir():
            for item in (base / key).iterdir():
                shutil.move(str(item), str(target / item.name))
        (base / REMOVED_MARK).write_text(time.strftime("%Y-%m-%d %H:%M"), encoding="utf-8")
    else:
        target.rmdir()
        shutil.move(str(base / key), str(target))
    return target


# ------------------------------------------------------------------- reading --
def missing(profile: dict) -> list[str]:
    """What a search can't do without: a name, a job title to search, and something for a CV."""
    out = []
    if not profile.get("name"):
        out.append("name")
    if not profile["search"]["titles"]:
        out.append("titles")
    cv = profile["cv"]
    if not (cv["summary"] or cv["experience"] or cv["achievements"]):
        out.append("cv")
    return out


def location(profile: dict) -> str:
    return ", ".join(p for p in (profile.get("city"), profile["search"]["country"]) if p)


# What must never print on a CV: contact details read as a job, a date or a job title read as a skill.
CONTACT_RE = re.compile(r"[✉☎⚲📞📧🔗📍☏✆]|@[\w-]+\.\w|(?:\+|00)\d[\d \-]{7,}\d|https?://|www\.|linkedin", re.I)
DATE_RE = re.compile(r"\b(?:19|20)\d\d\b.*(?:–|-|to|present)|^(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4}", re.I)


def clean_skill(skill: str) -> bool:
    """A skill worth printing: not a date, contact detail, sentence fragment or stray word."""
    s = skill.strip()
    if not s or CONTACT_RE.search(s) or DATE_RE.search(s):
        return False
    if ":" in s:                                 # a group: "Frameworks & Libraries: React, Next.js"
        return True
    words = s.split()
    if len(words) > 6 or s.endswith((" and", " or", " the", ",")):
        return False
    if re.search(r"\b(?:Co|Inc|Ltd|LLC|Corp|Group|Company)\.?$", s) or \
            re.search(r"\b(?:Developer|Engineer|Manager|Director|Designer|Analyst|Consultant|Officer|Specialist)$", s):
        return False                             # a company or a job title read as a skill
    return not (s[0].islower() and len(words) == 1 and not re.search(r"[A-Z0-9.+#]", s))   # "integrations"


def skill_terms(skills: list[str]) -> list[str]:
    """Grouped skills as single terms: "Styling & UI: Tailwind CSS, Sass" -> Tailwind CSS, Sass."""
    out = []
    for s in skills:
        body = s.split(":", 1)[1] if ":" in s else s
        out += [p.strip(" .") for p in re.split(r",(?![^()]*\))", body) if p.strip(" .")] if ":" in s else [s]
    return list(dict.fromkeys(out))


BRANDS = ("WordPress", "JavaScript", "TypeScript", "GitHub", "GitLab", "LinkedIn", "HubSpot", "WooCommerce",
          "Next.js", "Node.js", "React.js", "Vue.js", "PostgreSQL", "MySQL", "MongoDB", "jQuery", "Tailwind CSS",
          "PowerPoint", "YouTrack", "SharePoint", "Salesforce", "Shopify", "Figma", "Power BI", "iOS", "macOS")
_BRAND_RE = re.compile(r"(?<![\w.])(" + "|".join(re.escape(b) for b in BRANDS) + r")(?![\w])", re.I)


def brand_case(text: str) -> str:
    """'Wordpress' -> 'WordPress', 'Javascript' -> 'JavaScript': tech names spelled as their makers do."""
    canon = {b.lower(): b for b in BRANDS}
    return _BRAND_RE.sub(lambda m: canon[m.group(1).lower()], text) if text else text


def _language(item: str) -> str:
    return item[:1].upper() + item[1:] if item else item


def cv_content(profile: dict) -> dict:
    """The standard CV (free mode's CV, the same for every job but its skills order): the same shape as
    demo.json's 'cv'. Anything that isn't CV material (a role made of contact details, a date as a
    skill) is left out, so a badly read file can't put it on a CV."""
    cv = profile["cv"]
    b = brand_case
    skills = [s for s in (b(x) for x in cv["skills"]) if clean_skill(s)]
    experience = [e for e in cv["experience"]
                  if not CONTACT_RE.search(f"{e['role_title']} {e['company']}") and (e["role_title"] or e["company"])]
    return {
        "pillar": b(profile.get("headline") or (profile["search"]["titles"] or [""])[0]),
        "about": [b(p) for p in cv["summary"]],
        "achievements_title": "Key Achievements:",
        "achievements": [b(a) for a in cv["achievements"]],
        "experience": [{"company": e["company"], "period": e["period"], "role_title": b(e["role_title"]),
                        "role_description": b(e["role_description"]),
                        "bullets": [b(x) for x in e["bullets"] if not CONTACT_RE.search(x)]}
                       for e in experience],
        "competencies": " | ".join(skills[:8]),
        "skills": skills,                       # all of them: the CV for a job leads with the ones it asks for
    }


def cv_fixed(profile: dict) -> dict:
    """Contact details and the fixed sections of every CV (the same shape as cv_profile.json)."""
    cv = profile["cv"]
    # "Executive Profile" only for someone looking for executive roles alone; everyone else gets a summary.
    executive = set(profile["search"]["levels"]) <= {"director", "executive"}
    return {
        "name": profile.get("name", ""),
        "profile_heading": "Executive Profile" if executive else "Professional Summary",
        "location": location(profile),
        "phone": profile.get("phone", ""),
        "email": profile.get("email", ""),
        "linkedin": profile.get("linkedin", ""),
        "website": profile.get("website", ""),
        "education": cv["education"],
        "certifications": [re.sub(r"\s+:\s*", ": ", brand_case(x)) for x in cv["certifications"]],
        "training": cv["training"],
        "awards": cv["awards"],
        "languages": [_language(x) for x in cv["languages"]],
    }


def _phrase_pattern(text: str) -> str:
    return r"\s+".join(re.escape(w) for w in text.split())


def hint_patterns(profile: dict) -> list[str]:
    """Job titles a search keeps: each target title, and each distinctive word in them
    ("accountant", "product"), so "Senior Accountant" and "Product Lead" pass too."""
    titles = profile["search"]["titles"] or [profile.get("headline", "")]
    out = [_phrase_pattern(t) for t in titles if t.strip()]
    for title in titles:
        for word in re.findall(r"[^\W\d_][\w\-]+", title.lower()):
            if len(word) >= 3 and word not in GENERIC_TITLE_WORDS:
                out.append(re.escape(word) + r"\w*")
    return list(dict.fromkeys(out)) or [r"\w+"]


def block_patterns(profile: dict) -> list[str]:
    """Titles a search drops: internships unless the person is early-career, plus their own list."""
    levels = set(profile["search"]["levels"])
    out = [] if levels & EARLY_LEVELS else JUNIOR_TITLE_PATTERNS + JUNIOR_EXTRA_PATTERNS
    out += [_phrase_pattern(w) for w in profile["search"]["exclude"]]
    return out or [r"(?!x)x"]               # matches nothing


def company_patterns(profile: dict) -> list[str]:
    """Employers the person doesn't want jobs from ("Aramco" also drops "Saudi Aramco")."""
    return [_phrase_pattern(c) for c in profile["search"].get("exclude_companies") or [] if c.strip()]


def field_keywords(profile: dict) -> list[str]:
    """Words that show a posting is in the person's field: their skills and their own list."""
    return list(dict.fromkeys(skill_terms([s for s in map(brand_case, profile["cv"]["skills"]) if clean_skill(s)])
                              + profile["search"].get("keywords", [])))


PREFERENCE_LINES = (("years", "Years of experience"), ("relocate", "Relocation"), ("notice", "Notice period / start"),
                    ("salary", "Expected monthly salary"), ("visa", "Residency / visa"))


def preference_lines(profile: dict) -> list[str]:
    p = profile.get("preferences") or {}
    out = [f"- {label}: {p[key]}" for key, label in PREFERENCE_LINES if p.get(key)]
    if p.get("work_modes"):
        out.append(f"- Work arrangement: {', '.join(p['work_modes'])}")
    if p.get("job_types"):
        out.append(f"- Job type: {', '.join(p['job_types'])}")
    if p.get("other"):
        out.append(f"- In their own words: {p['other']}")
    return out


def _lines(title: str, items: list[str]) -> list[str]:
    return [f"## {title}", *(f"- {i}" for i in items), ""] if items else []


def cv_facts(profile: dict) -> str:
    """Every CV fact as Markdown - what ChatGPT may use. Contact details are left out on purpose."""
    cv = profile["cv"]
    out = [f"# {profile.get('name', '')}"]
    if profile.get("headline"):
        out.append(f"Headline: {profile['headline']}")
    out += [f"Based in: {location(profile)}", ""]
    if cv["summary"]:
        out += ["## Summary", *cv["summary"], ""]
    out += _lines("Key achievements", cv["achievements"])
    if cv["experience"]:
        out.append("## Experience (official titles, companies and periods)")
        for e in cv["experience"]:
            out.append(f"### {e['role_title']} — {e['company']}" + (f" ({e['period']})" if e["period"] else ""))
            if e["role_description"]:
                out.append(e["role_description"])
            out += [f"- {b}" for b in e["bullets"]]
        out.append("")
    out += _lines("Skills", cv["skills"])
    out += _lines("Education", [" — ".join(x for x in (e["credential"], e["institution"], e["detail"]) if x)
                                for e in cv["education"]])
    for key, title in (("certifications", "Certifications"), ("training", "Training"),
                       ("awards", "Awards"), ("languages", "Languages")):
        out += _lines(title, cv[key])
    return "\n".join(out).strip() + "\n"


def knowledge(profile: dict) -> str:
    """What ChatGPT scores jobs against: the CV facts, the search, and the person's own notes."""
    s = profile["search"]
    parts = [cv_facts(profile), "## Job search",
             f"- Target job titles (roles sought, not necessarily held): {', '.join(s['titles']) or 'none'}",
             f"- Seniority sought: {', '.join(s['levels'])}",
             f"- Country searched: {s['country']}"]
    if s.get("keywords"):
        parts.append(f"- Their field (industries, specialities, tools): {', '.join(s['keywords'])}")
    if profile.get("nationality"):
        parts.append(f"- Nationality: {profile['nationality']}")
    parts.append("")
    prefs = preference_lines(profile)
    if prefs:
        parts += ["## How they want to work (for scoring only - never written into a CV)", *prefs, ""]
    if profile.get("notes"):
        parts += ["## Notes from the person (for scoring only - never written into a CV)", profile["notes"], ""]
    return "\n".join(parts).strip() + "\n"


def track_name(profile: dict) -> str:
    return profile.get("headline") or (profile["search"]["titles"] or ["Target role"])[0]


def tracks_text(profile: dict) -> str:
    keywords = list(dict.fromkeys(profile["search"]["titles"] + field_keywords(profile)))[:20]
    return (f"   - **Track 1: {track_name(profile)}**\n"
            "     This profile has one track: select it for every job.\n"
            f"     Keywords: {', '.join(keywords) or 'none'}.")


def blueprint(profile: dict) -> str:
    return "\n".join([
        f"TRACK 1: {track_name(profile)}",
        f"Target roles: {', '.join(profile['search']['titles']) or track_name(profile)}",
        "",
        "CV SOURCE - every fact below may be used; nothing else may.",
        "",
        cv_facts(profile),
    ])


# --------------------------------------------------- ChatGPT prompts (new people) --
EVAL_SYSTEM = """You are the Job Evaluation Agent for {{NAME}}.
Evaluate each job posting against {{NAME}}'s profile below, select the CV track, score the fit, and choose the CV tailoring level.

=====================================================================
{{NAME}} — PROFILE
=====================================================================
{{PROFILE}}

=====================================================================
EVALUATION RULES
=====================================================================
1. job_url: return exactly one evaluation for EVERY job in the input - N jobs in, N evaluations out - with job_url copied character-for-character.
2. The profile is the only source of truth. Never invent experience, titles, employers, metrics or credentials. The target job titles are roles sought, not titles held, unless the experience shows them.
3. Nationality: if a posting is restricted to a nationality or citizenship that the profile (its Nationality line and notes) does not show (e.g. "Saudi nationals only", "Saudization", "GCC nationals only", "توطين"), set ats_score 0, interview_score 0, fit_score 0, selected_track 1, secondary_track null, track_selection_confidence "high", tailoring_level "light", summary null, and both selected_track_reason and reasoning to: "تم استبعاد الوظيفة تلقائياً نظراً لاشتراط جنسية محددة."
4. Location: the search covers {{COUNTRY}}. Respect any relocation or city preference in the notes, and mention the city in reasoning when it matters.
5. Scores, each 0-100:
   A. ats_score - how well a CV tailored truthfully from this profile can carry the posting's keywords, tools, domain terms and role phrasing. Do not over-estimate.
   B. interview_score - how credibly {{NAME}} can defend the role in an interview with real evidence from the profile: level, scope, domain and years of experience.
   C. fit_score = round(ats_score * 0.45 + interview_score * 0.55). Do not output a verdict; the system computes it.
6. Tracks:
{{TRACKS}}
   selected_track: 1. secondary_track: null. track_selection_confidence: "high", "medium" or "low" (low when the posting is vague). selected_track_reason: one sentence in Arabic.
7. tailoring_level: "light" (direct match), "moderate" (re-order and re-emphasise), "deep" (stretch: restructure achievements and experience) or "special_cv" (needs a bespoke structure).
8. summary (Arabic, about the job only, 2-4 sentences, no mention of the person) and reasoning (Arabic: why it fits, real gaps, how competitive {{NAME}} is). No prefixes or labels. For fit_score <= 50 set both to null.
"""

EVAL_USER = """Evaluate the following job postings against the profile in the system prompt. Return exactly one evaluation per job, matching each job_url character-for-character.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
JOBS YOU NEED TO EVALUATE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{{JOBS_TEXT}}
"""

CV_SYSTEM = """You are {{NAME}}'s CV Tailoring Agent.
Use ONLY the facts in the CV source below. Never invent employers, titles, dates, metrics, clients, tools, certifications or achievements.

RULES
1. Source-faithful: every line must be backed by the CV source. Where it gives no figure, keep the result qualitative.
2. Official titles only: copy each role's title, company and period exactly as the source gives them. Never put the posting's job title anywhere as if the person held it - not in the headline either.
3. It must read as the person's own CV, written by a human: keep their wording; change a phrase only to use the posting's exact term for the same thing. No stock phrases ("results-driven", "proven track record", "passionate", "dynamic", "leverage", "spearheaded", "brings hands-on experience in ... to the ... role"), no sentence that only restates the posting, no adjective lists.
4. The whole CV, with its fixed sections, must fit on two pages. Never add a skill or tool only for ATS.
5. Contact details, education, certifications, training, awards and languages are added from the profile after your JSON. Do not write them into any field.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CV SOURCE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{{TRACK_BLUEPRINT}}

TAILORING (whatever the tailoring level in the metadata): select and order the person's real material
for this job; do not rewrite it into new prose.

FIELDS
- headline: the person's own headline from the source, unchanged.
- about_paragraphs: their own summary; only swap in the posting's exact term where it names the same thing.
- achievements_title: e.g. "Key Achievements:".
- key_achievements: the achievements from the source, word for word, most relevant to this job first (none if the source has none).
- work_experience: every role in the source, most recent first, with its title, company, period and description as given, and its bullets word for word - the ones this job cares about first.
- core_competencies: 8-12 of their skills separated by " | ", the ones this posting asks for first.
Return only JSON matching the schema.
"""

CV_USER = """Tailor {{NAME}}'s CV for this position, using only the CV source in the system prompt.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TARGET JOB DETAILS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{{JOB_DETAILS}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EVALUATION METADATA (Fit Scores & Tailoring Directives)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{{EVAL_METADATA}}
"""
