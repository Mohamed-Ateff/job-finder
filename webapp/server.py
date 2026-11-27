"""Local web app for the job automation: a JSON API plus a static front end.

    python -m webapp            # opens http://localhost:8501

The pipeline is unchanged. Runs are started as `job_automation.py` processes,
and everything shown is read from the files they write (jobs*.json and
runs/<candidate>/<stamp>/). Listens on 127.0.0.1 only; set APP_PASSWORD in
.env to require a password as well.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, Response  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

import cv_import  # noqa: E402
import job_automation as ja  # noqa: E402
import cv_pdf  # noqa: E402
import mailer  # noqa: E402
import profiles  # noqa: E402
import questionnaire  # noqa: E402

STATIC_DIR = Path(__file__).resolve().parent / "static"
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"
CHECKLIST_FILE = ROOT / "client_checklist.json"
DEMO_DIR = ROOT / "demo"                # Demo Mode keeps its own jobs*.json and runs/ here
HOST = os.environ.get("WEB_HOST", "127.0.0.1")
PORT = int(os.environ.get("WEB_PORT", "8501"))

STAMP = re.compile(r"^\d{8}-\d{6}$")
SESSION_COOKIE = "jobauto_session"
CSRF_HEADER, CSRF_VALUE = "x-requested-with", "jobauto"
OPEN_PATHS = {"/api/session", "/api/login"}
PLACEHOLDER_SUFFIXES = ("@example.com",)

# Job search is free and built in (no account). ChatGPT is an optional upgrade for scoring and CVs.
AI_TOGGLE = {"id": "ai", "kind": "toggle", "env": "AI_MODE", "on_value": "chatgpt", "off_value": "basic", "optional": True,
             "title": "Use ChatGPT",
             "why": "Off is free. On, ChatGPT scores jobs and writes CVs, paid per search."}
CHATGPT_ITEMS = [                       # only asked for when AI_MODE=chatgpt
    {"id": "openai", "env": "OPENAI_API_KEY", "secret": True, "title": "OpenAI (ChatGPT) API key",
     "why": "Scores jobs and writes the CVs.",
     "where": "platform.openai.com/api-keys (an API key, not a ChatGPT Plus subscription)"},
]
CORE_ACCOUNT_ITEMS = CHATGPT_ITEMS
EMAIL_ACCOUNT_ITEMS = [                 # only asked for when EMAIL_DIGEST=on
    {"id": "brevo", "env": "BREVO_API_KEY", "secret": True, "title": "Brevo API key",
     "why": "Sends the daily digest email with the CVs attached.",
     "where": "Brevo → SMTP & API → API keys (the API key, not the SMTP key)"},
    {"id": "sender", "env": "EMAIL_FROM", "secret": False, "title": "Verified sender address",
     "why": "The address the digest is sent from. It has to be verified in Brevo.",
     "where": "Brevo → Senders, domains & IPs → Senders"},
]
ACCOUNT_ITEMS = CHATGPT_ITEMS + EMAIL_ACCOUNT_ITEMS
EMAIL_TASKS = {"domain"}
CHATGPT_TASKS = {"credit"}
SHARED_TASKS = [
    {"id": "credit", "title": "OpenAI API credit added",
     "why": "Paid per use, separate from ChatGPT Plus. Searches use {model}.",
     "where": "platform.openai.com → Settings → Billing"},
    {"id": "domain", "title": "Sender domain authenticated (SPF and DKIM)",
     "why": "Without it the digest lands in spam or is rejected.",
     "where": "Brevo → Senders, domains & IPs → Domains"},
]
BUILTIN_CHECKLISTS = {
    "ahmed": [
        {"id": "sources", "title": "Which job sites to search",
         "why": "LinkedIn and Indeed are on. Bayt can be added too. All of them are searched for free."},
    ],
}
SEARCH_PERIODS = (24, 72, 168)          # Settings → How far back each search looks (hours)
ENV_LABELS = {
    "OPENAI_API_KEY": "OpenAI API key",
    "BREVO_API_KEY": "Brevo API key",
    "EMAIL_FROM": "Sender address",
}
STAGES = [("collect", "Search"), ("filter", "Filter"), ("score", "Score"), ("cvs", "CVs"), ("send", "Save")]
STAGE_MARKERS = [
    ("scrape:", "collect"), ("normalize:", "filter"), ("dedupe:", "filter"), ("filter:", "filter"),
    ("evaluate:", "score"), ("cv:", "cvs"), ("selected ", "send"), ("emailed ", "send"), ("nothing to send", "send"),
]


# ------------------------------------------------------------------- .env ----
def sync_env() -> None:
    """While the app runs, .env is the source of truth: mirror it into this
    process, and so into every run it starts."""
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        parsed = ja.parse_env_line(line)
        if parsed and parsed[1]:
            os.environ[parsed[0]] = parsed[1]


def env_value(name: str) -> str:
    return os.environ.get(name, "").strip()


def is_set(name: str) -> bool:
    value = env_value(name)
    return bool(value) and not value.lower().endswith(PLACEHOLDER_SUFFIXES)


# ------------------------------------------------------------- key checks ----
# A free, read-only call that only succeeds with a working key.
KEY_CHECK_URLS = {
    "OPENAI_API_KEY": "https://api.openai.com/v1/models",
}
KEY_HINTS = {
    "OPENAI_API_KEY": "OpenAI didn’t accept this key. Create one at platform.openai.com/api-keys. It starts with sk-.",
}
_key_results: dict[tuple[str, str], bool] = {}


def check_key(name: str, value: str) -> bool | None:
    """True if the service accepts the key, False if it rejects it, None if it can't be
    reached (or the key isn't one we can check). Answers are remembered per key value."""
    url = KEY_CHECK_URLS.get(name)
    if not url or not value:
        return None
    memo = (name, hashlib.sha256(value.encode()).hexdigest())
    if memo in _key_results:
        return _key_results[memo]
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {value}"})
    try:
        with urllib.request.urlopen(request, timeout=8):
            result = True
    except urllib.error.HTTPError as exc:
        result = False if exc.code == 401 else None
    except Exception:  # noqa: BLE001 - offline / DNS / timeout: can't tell
        result = None
    if result is not None:
        _key_results[memo] = result
    return result


def key_rejected(name: str) -> bool:
    return is_set(name) and check_key(name, env_value(name)) is False


def chatgpt_on() -> bool:
    """AI_MODE=chatgpt in .env: OpenAI scores the jobs and writes the CVs (paid).
    Anything else, or unset: the free built-in matching (basic_ai.py)."""
    sync_env()
    return env_value("AI_MODE").lower() == "chatgpt"


def email_on() -> bool:
    """EMAIL_DIGEST=on in .env also emails each digest (Brevo). Off by default:
    matches, job links and CVs are kept in the app only."""
    sync_env()
    return ja.env_flag("EMAIL_DIGEST")


def _env_quote(value: str) -> str:
    return f'"{value}"' if re.search(r"\s|#", value) else value


def write_env(updates: dict[str, str]) -> None:
    """Set keys in .env, keeping every other line (and the comments) as it was.
    A commented-out `# KEY=` line is replaced in place."""
    if ENV_FILE.exists():
        lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    elif ENV_EXAMPLE.exists():
        lines = ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
    else:
        lines = []
    done: set[str] = set()
    out = []
    for line in lines:
        match = re.match(r"^\s*#?\s*([A-Z][A-Z0-9_]*)\s*=", line)
        if match and match.group(1) in updates and match.group(1) not in done:
            out.append(f"{match.group(1)}={_env_quote(updates[match.group(1)])}")
            done.add(match.group(1))
        else:
            out.append(line)
    out += [f"{key}={_env_quote(value)}" for key, value in updates.items() if key not in done]
    ENV_FILE.write_text("\n".join(out) + "\n", encoding="utf-8")
    os.environ.update(updates)


# ------------------------------------------------------------------ demo ----
def demo_on() -> bool:
    return (DEMO_DIR / ".enabled").exists()


def state_dir() -> Path:
    """Where jobs*.json lives: the demo folder while Demo Mode is on."""
    return DEMO_DIR if demo_on() else ja.STATE_DIR


def runs_root() -> Path:
    return DEMO_DIR / "runs" if demo_on() else ja.RUNS_DIR


# ------------------------------------------------------------- candidates ----
def candidate_keys() -> list[str]:
    """Ahmed (built in), then everyone in candidates/: set up by hand or added in the app."""
    return profiles.keys(ja.CANDIDATES_DIR)


def candidate(key: str) -> ja.Candidate:
    if key not in candidate_keys():
        raise HTTPException(404, "Unknown candidate")
    try:
        return ja.load_candidate(key)
    except SystemExit as exc:
        raise HTTPException(500, f"Candidate config error: {exc}") from exc


def candidate_config(key: str) -> dict:
    return read_json(ja.CANDIDATES_DIR / key / "candidate.json", {}) or {}


def initials(name: str) -> str:
    return "".join(part[0] for part in name.split()[:2]).upper()


def first_name(name: str) -> str:
    return (name.split() or [""])[0]


def thresholds() -> dict[str, int]:
    return {
        "strong": int(os.environ.get("VERDICT_STRONG_MIN", ja.STRONG_MIN)),
        "good": int(os.environ.get("VERDICT_GOOD_MIN", ja.GOOD_MIN)),
        "moderate": int(os.environ.get("VERDICT_MODERATE_MIN", ja.MODERATE_MIN)),
    }


# ---------------------------------------------------------------- reading ----
def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def load_state(c: ja.Candidate) -> dict:
    state = read_json(state_dir() / c.state_name, {}) or {}
    state.setdefault("seen", {})
    state.setdefault("pending", {})
    return state


def applied_file(c: ja.Candidate) -> Path:
    """Jobs marked as applied in the app. Its own file, so a run saving
    jobs*.json at the same moment can never overwrite a mark."""
    return state_dir() / f"applied_{c.key}.json"


def load_applied(c: ja.Candidate) -> dict[str, str]:
    data = read_json(applied_file(c), {})
    return data if isinstance(data, dict) else {}


def hidden_file(c: ja.Candidate) -> Path:
    """Jobs deleted in the app. They stay in jobs*.json as 'seen', so no later search
    brings them back or scores them again - they're just never shown."""
    return state_dir() / f"hidden_{c.key}.json"


def load_hidden(c: ja.Candidate) -> dict[str, str]:
    data = read_json(hidden_file(c), {})
    return data if isinstance(data, dict) else {}


def write_marks(path: Path, marks: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(marks, indent=1), encoding="utf-8")
    tmp.replace(path)


def run_dirs(c: ja.Candidate) -> list[Path]:
    base = runs_root() / c.key
    if not base.exists():
        return []
    return sorted((p for p in base.iterdir() if p.is_dir() and STAMP.match(p.name)), reverse=True)


def run_dir(c: ja.Candidate, stamp: str) -> Path:
    if not STAMP.match(stamp):
        raise HTTPException(404, "Unknown run")
    path = runs_root() / c.key / stamp
    if not path.is_dir():
        raise HTTPException(404, "Unknown run")
    return path


def stamp_label(stamp: str) -> str:
    return datetime.strptime(stamp, "%Y%m%d-%H%M%S").strftime("%a %d %b %Y, %H:%M")


def run_summary(path: Path) -> dict:
    raw = read_json(path / "raw.json")
    evaluated = read_json(path / "evaluated.json", []) or []
    meta = read_json(path / "run.json", {}) or {}
    cvs = sorted(p.name for p in (path / "cvs").glob("*.docx")) if (path / "cvs").is_dir() else []
    top = sorted((j for j in evaluated if j.get("fit_verdict") in ("strong", "good")),
                 key=lambda j: -(j.get("fit_score") or 0))
    return {
        "stamp": path.name,
        "label": stamp_label(path.name),
        "started": datetime.strptime(path.name, "%Y%m%d-%H%M%S").isoformat(),
        "scraped": len(raw) if isinstance(raw, list) else None,
        "evaluated": len(evaluated),
        "matches": len(top),
        "top_titles": [j.get("title", "") for j in top[:3]],
        "mode": meta.get("mode") or ("preview" if raw is not None else "replay"),
        "outcome": meta.get("outcome"),
        "demo": bool(meta.get("demo")),
        "email": bool(meta.get("email", True)),     # runs from before EMAIL_DIGEST were email runs
        "recipients": meta.get("recipients", ""),
        "cvs": cvs,
        "digest": (path / "digest.html").exists(),
        "log": (path / "run.log").exists(),
        "replayable": (path / "raw.json").exists(),
    }


def expected_cv_name(c: ja.Candidate, title: str, company: str) -> str:
    """The file name job_automation.cv_file_name() gives this job's CV."""
    return expected_cv_name_for(c.name, title, company)


def expected_cv_name_for(name: str, title: str, company: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", f"{company}_{title}").strip("_")[:60] or "Role"
    person = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")
    return f"{slug}_{person}_CV.docx"


def cv_index(c: ja.Candidate) -> dict[str, str]:
    """CV file name -> newest run stamp that holds it."""
    index: dict[str, str] = {}
    for path in run_dirs(c):                    # newest first
        if (path / "cvs").is_dir():
            for f in (path / "cvs").glob("*.docx"):
                index.setdefault(f.name, path.name)
    return index


def description_file(c: ja.Candidate) -> Path:
    return ja.STATE_DIR / f"descriptions_{c.key}.json"


def job_rows(c: ja.Candidate) -> list[dict]:
    state = load_state(c)
    details: dict[str, dict] = {}
    for path in reversed(run_dirs(c)):          # oldest first; newer runs win
        for job in read_json(path / "evaluated.json", []) or []:
            if job.get("url"):
                details[job["url"]] = job
    for url, job in state["pending"].items():
        details[url] = {**details.get(url, {}), **job}

    cvs = cv_index(c)
    written_by = {p.name: (read_json(p / "run.json", {}) or {}).get("ai") for p in run_dirs(c)}
    applied = load_applied(c)
    hidden = load_hidden(c)
    # "New" = scored by the most recent search (a search that found nothing new marks nothing).
    recent = run_dirs(c)
    new_urls = {j.get("url") for j in (read_json(recent[0] / "evaluated.json", []) or [])} if recent else set()
    logos = state.get("logos") or {}
    fetched = read_json(description_file(c), {}) or {}     # descriptions read later, when a job was opened
    known_apply = read_json(apply_file(c), {}) or {}       # apply types learnt later, from LinkedIn
    names = [c.name, *reversed(c.former_names)]     # CVs made before a rename carry the old name
    rows = []
    for url, seen in state["seen"].items():
        if url in hidden:
            continue
        d = details.get(url, {})
        description = ja.fix_text((d.get("description") or "") if len(d.get("description") or "") >= 150
                                  else fetched.get(url, ""))
        how, emails = apply_type(c, {**d, "url": url, "description": description}, known_apply)
        track, secondary = d.get("selected_track"), d.get("secondary_track")
        saved_title = seen.get("title") or d.get("title", "")
        saved_company = seen.get("company") or d.get("company", "")
        title, company = ja.fix_text(saved_title), ja.fix_text(saved_company)   # jobs saved with garbled text read right
        cv_name = next((n for n in (expected_cv_name_for(name, saved_title, saved_company) for name in names)
                        if n in cvs), None)
        logo = d.get("logo") or logos.get(ja.company_key(company)) or ""
        stored = {"stamp": cvs[cv_name], "name": cv_name} if cv_name else None
        # A CV ChatGPT wrote is served as written; otherwise the CV is made for this job when it's downloaded.
        cv_url = (f"/api/runs/{c.key}/{stored['stamp']}/cvs/{urllib.parse.quote(stored['name'])}"
                  if stored and written_by.get(stored["stamp"]) == "chatgpt"
                  else f"/api/cv/{c.key}?url={urllib.parse.quote(url, safe='')}")
        rows.append({
            "url": url,
            "cv": stored,
            "cv_url": cv_url,
            "title": title,
            "company": company,
            "logo": logo if logo.startswith("https://") else "",
            "location": ja.fix_text(d.get("location", "")),
            "source": d.get("source", ""),
            "fit": int(seen.get("fit_score") or 0),
            "ats": d.get("ats_score"),
            "interview": d.get("interview_score"),
            "verdict": seen.get("fit_verdict") or "weak",
            "status": "emailed" if seen.get("emailed_at") else ("waiting" if url in state["pending"] else ""),
            "applied": applied.get(url),
            "new": url in new_urls,
            "posted": d.get("posted", ""),
            "evaluated": seen.get("evaluated_at", ""),
            "track": track,
            "track_name": c.track_names.get(track, ""),
            "secondary_track_name": c.track_names.get(secondary, "") if secondary != track else "",
            "tailoring": d.get("tailoring_level"),
            "confidence": d.get("track_selection_confidence"),
            "summary": d.get("summary"),
            "reasoning": d.get("reasoning"),
            "description": description,
            "apply": how,
            "emails": emails,
            "remote": bool(d.get("remote")) or ja.looks_remote(title, d.get("location", ""), description),
            "company_site": d.get("company_site") if str(d.get("company_site", "")).startswith("http") else "",
            "breakdown": d.get("breakdown"),
            "has_cv": bool(d.get("cv")),
        })
    rows.sort(key=lambda r: (r["evaluated"], r["fit"]), reverse=True)
    return rows


# ------------------------------------------------------------------ setup ----
def load_checks() -> dict:
    return read_json(CHECKLIST_FILE, {}) or {}


def candidate_checklist(c: ja.Candidate) -> list[dict]:
    return candidate_config(c.key).get("client_checklist") or BUILTIN_CHECKLISTS.get(c.key, [])


def env_item(item: dict) -> dict:
    ok = is_set(item["env"])
    if ok and key_rejected(item["env"]):
        return {**item, "kind": "env", "ok": False, "display": "", "problem": KEY_HINTS[item["env"]]}
    display = ("Saved" if item.get("secret") else env_value(item["env"])) if ok else ""
    return {**item, "kind": "env", "ok": ok, "display": display}


def _count(groups: list[dict]) -> tuple[int, int]:
    required = [i for g in groups for i in g["items"] if not i.get("optional")]
    return sum(1 for i in required if i["ok"]), len(required)


def settings_for() -> dict:
    """Settings: what applies to everyone - scoring (free or ChatGPT), the email digest when
    it's on, the search period and Demo Mode."""
    sync_env()
    shared = load_checks().get("_shared", {})
    model = env_value("OPENAI_MODEL_EVAL") or ja.MODEL_EVAL
    email, chatgpt = email_on(), chatgpt_on()

    def task(i: dict) -> dict:
        return {**i, "why": i["why"].format(model=model), "kind": "check", "scope": "_shared", "ok": bool(shared.get(i["id"]))}

    tasks = {i["id"]: i for i in SHARED_TASKS}
    scoring = [{**AI_TOGGLE, "ok": True, "on": chatgpt}]
    if chatgpt:      # just the key: the "credit added" tick box was a reminder, not a setting
        scoring += [env_item(i) for i in CHATGPT_ITEMS]
    groups = [{"id": "scoring", "title": "Scoring & CVs", "items": scoring}]
    if email:
        groups.append({"id": "email", "title": "Email digest",
                       "items": [env_item(i) for i in EMAIL_ACCOUNT_ITEMS] + [task(tasks["domain"])]})
    done, total = _count(groups)
    hours = int(env_value("SEARCH_HOURS") or ja.SEARCH_HOURS)
    return {"groups": groups, "done": done, "total": total, "email": email, "chatgpt": chatgpt,
            "search_hours": hours if hours in SEARCH_PERIODS else ja.SEARCH_HOURS,
            "search_periods": list(SEARCH_PERIODS), "demo": demo_on(), "model": model,
            "daily": daily_on(), "daily_hour": DAILY_HOUR,
            "daily_last": (read_json(daily_file(), {}) or {}).get("date", "")}


def profile_data(c: ja.Candidate) -> tuple[dict, bool]:
    """The person's editable profile, and whether it has been saved in the app yet."""
    saved = profiles.read(ja.CANDIDATES_DIR, c.key)
    return (saved, True) if saved else (ja.seed_profile(c), False)


def profile_groups(c: ja.Candidate) -> list[dict]:
    """The checklist part of a profile: the email recipients, when email is on."""
    groups = []
    if email_on():
        groups.append({"id": "recipients", "title": "Email recipients", "items": [
            env_item({"id": "recipient", "env": c.email_to_env, "secret": False,
                      "title": "Email address for the daily digest",
                      "why": f"Where {c.name}'s digest and CVs are sent. Only this address receives them."}),
            env_item({"id": "cc", "env": c.email_cc_env, "secret": False, "optional": True,
                      "title": "CC addresses",
                      "why": "Anyone else who should receive the digest (comma-separated)."}),
        ]})
    # The handover approvals ("go-ahead", "approve the tracks", ...) are no longer shown: they were
    # tasks between the developer and the client, not something the client uses day to day.
    return groups


def profile_readiness(c: ja.Candidate) -> dict:
    prof, _ = profile_data(c)
    missing = profiles.missing(prof)
    done, total = _count(profile_groups(c))
    return {"missing": missing, "open": len(missing) + total - done}


def settings_keys() -> set[str]:
    keys = {item["env"] for item in ACCOUNT_ITEMS} | {"AI_MODE", "OPENAI_MODEL_EVAL", "BREVO_SENDER_NAME", "SOURCES",
                                                     "SEARCH_HOURS", "DAILY_SEARCH"}
    for key in candidate_keys():
        c = candidate(key)
        keys |= {c.email_to_env, c.email_cc_env}
    return keys


def required_env(c: ja.Candidate, mode: str, email: bool, chatgpt: bool = False) -> list[str]:
    """Keys a run needs. The job search itself needs none; ChatGPT and email are opt-in."""
    ai = ["OPENAI_API_KEY"] if chatgpt else []
    return {
        "dry": ai,
        "replay": ai,
        "real": [*ai, *(["BREVO_API_KEY", "EMAIL_FROM", c.email_to_env] if email else [])],
    }[mode]


def configured_sources() -> list[str]:
    return [s.strip() for s in env_value("SOURCES").lower().split(",") if s.strip() in ja.SITES] or list(ja.SOURCES)


def env_label(c: ja.Candidate, name: str) -> str:
    return ENV_LABELS.get(name) or ("Recipient address" if name == c.email_to_env else name)


# ------------------------------------------------------------------- runs ----
def pipeline_command(args: list[str]) -> list[str]:
    return [sys.executable, "-u", str(ROOT / "job_automation.py"), *args]


class Run:
    def __init__(self, key: str, mode: str, args: list[str]):
        self.id = uuid.uuid4().hex[:12]
        self.candidate, self.mode, self.args = key, mode, args
        self.runs_root = runs_root()        # fixed at start, even if Demo Mode is switched meanwhile
        self.lines: list[str] = []
        self.status = "running"
        self.returncode: int | None = None
        self.stage = "collect"
        self.started, self.ended = time.time(), None
        self.stamp: str | None = None

    def feed(self, line: str) -> None:
        self.lines.append(line)
        match = re.search(r"\brun (\d{8}-\d{6})\b", line)
        if match and not self.stamp:
            self.stamp = match.group(1)
        order = [s for s, _ in STAGES]
        for marker, stage in STAGE_MARKERS:
            if marker in line and order.index(stage) > order.index(self.stage):
                self.stage = stage

    def to_dict(self, since: int = 0) -> dict:
        digest = bool(self.stamp) and (self.runs_root / self.candidate / self.stamp / "digest.html").exists()
        return {
            "id": self.id, "candidate": self.candidate, "mode": self.mode, "status": self.status,
            "returncode": self.returncode, "stage": self.stage, "stages": STAGES, "stamp": self.stamp,
            "digest": digest, "elapsed": round((self.ended or time.time()) - self.started),
            "lines": self.lines[since:], "next": len(self.lines),
        }


class RunManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._runs: dict[str, Run] = {}

    def _active(self, key: str) -> Run | None:
        return next((r for r in reversed(list(self._runs.values()))
                     if r.candidate == key and r.status == "running"), None)

    def active(self, key: str) -> Run | None:
        with self._lock:
            return self._active(key)

    def get(self, run_id: str) -> Run | None:
        with self._lock:
            return self._runs.get(run_id)

    def start(self, key: str, mode: str, args: list[str]) -> Run:
        with self._lock:
            if self._active(key):
                raise HTTPException(409, "A run for this candidate is already in progress.")
            run = Run(key, mode, args)
            self._runs[run.id] = run
        threading.Thread(target=self._work, args=(run,), daemon=True).start()
        return run

    def _work(self, run: Run) -> None:
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            proc = subprocess.Popen(
                pipeline_command(["--candidate", run.candidate, *run.args]), cwd=ROOT, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                errors="replace", creationflags=flags,
            )
        except OSError as exc:
            run.feed(f"Could not start the pipeline: {exc}")
            run.returncode, run.status, run.ended = -1, "failed", time.time()
            return
        for line in proc.stdout:
            run.feed(line.rstrip("\n"))
        run.returncode = proc.wait()
        if run.returncode == 0 and run.mode in ("real", "replay") and run.stamp and not demo_on():
            try:
                run.feed(email_run_matches(run.candidate, run.runs_root / run.candidate / run.stamp))
            except Exception as exc:  # noqa: BLE001 - the search itself worked; say why the email didn't
                run.feed(f"email: not sent - {exc}")
        run.status = {0: "finished", 2: "busy"}.get(run.returncode, "failed")
        run.ended = time.time()
        folder = run.runs_root / run.candidate / (run.stamp or "")
        if run.stamp and folder.is_dir():
            (folder / "run.log").write_text("\n".join(run.lines), encoding="utf-8")


RUNS = RunManager()


# ------------------------------------------------------------ daily search --
DAILY_HOUR = 7                          # local time (Cairo): the search runs once a day from this hour


def daily_on() -> bool:
    """The search runs by itself every morning. On by default on the cloud server (always on), off on a
    laptop (which may be asleep or closed); Settings can turn it on or off either way."""
    value = env_value("DAILY_SEARCH").lower()
    return value == "on" if value in ("on", "off") else bool(os.environ.get("RENDER_EXTERNAL_HOSTNAME"))


def local_now() -> datetime:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Africa/Cairo"))
    except Exception:  # noqa: BLE001 - no time-zone data on the server: Cairo's winter time
        from datetime import timedelta, timezone
        return datetime.now(timezone(timedelta(hours=2)))


def daily_file() -> Path:
    return ja.STATE_DIR / "daily_search.json"


def daily_due(now: datetime | None = None) -> bool:
    now = now or local_now()
    last = (read_json(daily_file(), {}) or {}).get("date", "")
    return daily_on() and not demo_on() and now.hour >= DAILY_HOUR and last != now.date().isoformat()


def run_daily_search(wait: float = 10.0) -> list[str]:
    """Everyone's search, one person after another (job sites slow down tools that rush them). Each
    finished search emails its best matches to people who set up email, as a search from the app does."""
    ja.write_json(daily_file(), {"date": local_now().date().isoformat(), "started": ja.now_iso()})
    started = []
    for key in candidate_keys():
        try:
            c = candidate(key)
        except HTTPException:
            continue
        if not c.keywords:
            continue
        sources = [s for s in (c.sources or configured_sources()) if s in ja.SITES]
        deadline = time.time() + 3 * 3600
        while RUNS.active(key) and time.time() < deadline:      # a search started by hand finishes first
            time.sleep(wait)
        try:
            run = RUNS.start(key, "real", ["--sources", ",".join(sources)] if sources else [])
        except HTTPException:
            continue
        started.append(key)
        while run.status == "running" and time.time() < deadline:
            time.sleep(wait)
    return started


def daily_loop() -> None:
    while True:
        try:
            if daily_due():
                run_daily_search()
        except Exception as exc:  # noqa: BLE001 - try again on the next check
            print(f"daily search failed: {exc}", flush=True)
        time.sleep(60)


_daily_started = False


def start_daily_search() -> None:
    global _daily_started
    if not _daily_started:
        _daily_started = True
        threading.Thread(target=daily_loop, daemon=True).start()


def activity(c: ja.Candidate) -> dict | None:
    run = RUNS.active(c.key)
    if run:
        return {**run.to_dict(len(run.lines)), "external": False}
    if (runs_root() / c.key / ".lock").exists():
        return {"external": True, "status": "running"}
    return None


# -------------------------------------------------------------------- app ----
app = FastAPI(title="Job Automation", docs_url=None, redoc_url=None, openapi_url=None)
sync_env()


def password() -> str:
    return os.environ.get("APP_PASSWORD", "")


def session_token(secret: str) -> str:
    return hmac.new(secret.encode(), b"jobauto-session-v1", hashlib.sha256).hexdigest()


def authed(request: Request) -> bool:
    secret = password()
    return not secret or hmac.compare_digest(request.cookies.get(SESSION_COOKIE, ""), session_token(secret))


def allowed_hosts() -> set[str]:
    extra = {h.strip().lower() for h in os.environ.get("APP_ALLOWED_HOSTS", "").split(",") if h.strip()}
    return {"127.0.0.1", "localhost", "::1", "[::1]"} | extra


def host_allowed(host: str) -> bool:
    """Exact names, or ".example.com" for any one subdomain of it (e.g. a tunnel's random name)."""
    hosts = allowed_hosts()
    return host in hosts or any(h.startswith(".") and host.endswith(h) and "." not in host[: -len(h)] for h in hosts)


@app.middleware("http")
async def guard(request: Request, call_next):
    # DNS-rebinding guard: only answer requests addressed to this machine.
    if not host_allowed((request.url.hostname or "").lower()):
        return PlainTextResponse("Forbidden host", status_code=403)
    # CSRF guard: a page on another site cannot add this header without a CORS
    # preflight, which this server never approves.
    if request.method not in ("GET", "HEAD") and request.headers.get(CSRF_HEADER) != CSRF_VALUE:
        return JSONResponse({"detail": "Missing request header"}, status_code=403)
    if request.url.path.startswith("/api/") and request.url.path not in OPEN_PATHS and not authed(request):
        return JSONResponse({"detail": "Sign in required"}, status_code=401)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    return response


class LoginRequest(BaseModel):
    password: str


class SettingsRequest(BaseModel):
    values: dict[str, str]


class CheckRequest(BaseModel):
    scope: str
    item: str
    done: bool


class RunRequest(BaseModel):
    candidate: str
    mode: Literal["dry", "replay", "real"]
    limit: int = Field(0, ge=0, le=500)
    sources: list[str] = Field(default_factory=list)
    no_cv: bool = False
    replay: str | None = None
    confirm: bool = False


@app.get("/api/session")
def session(request: Request):
    ok = authed(request)
    people = [{"key": k, "name": (c := candidate(k)).name, "initials": initials(c.name),
               "system_label": c.system_label, "kind": c.kind} for k in candidate_keys()] if ok else []
    return {"auth_required": bool(password()), "authed": ok, "candidates": people,
            "demo": demo_on() if ok else False, "email": email_on() if ok else False}


class AppliedRequest(BaseModel):
    candidate: str
    url: str
    applied: bool


@app.post("/api/applied")
def set_applied(body: AppliedRequest):
    """Mark a job as applied to (by hand) or clear the mark."""
    c = candidate(body.candidate)
    if body.url not in load_state(c)["seen"]:
        raise HTTPException(404, "Unknown job")
    marks = load_applied(c)
    if body.applied:
        marks.setdefault(body.url, ja.now_iso())
    else:
        marks.pop(body.url, None)
    write_marks(applied_file(c), marks)
    return {"applied": marks.get(body.url)}


_cv_lock = threading.Lock()                 # the CV writer reads the pipeline's current candidate


def job_detail(c: ja.Candidate, url: str) -> dict | None:
    """Everything known about one job: its row in jobs*.json plus the posting saved with its search."""
    state = load_state(c)
    if url not in state["seen"]:
        return None
    job: dict = {}
    for path in reversed(run_dirs(c)):          # oldest first; newer runs win
        for j in read_json(path / "evaluated.json", []) or []:
            if j.get("url") == url:
                job = j
    seen = state["seen"][url]
    return {**job, "url": url, "title": seen.get("title") or job.get("title", ""),
            "company": seen.get("company") or job.get("company", ""), "location": job.get("location", ""),
            "description": job.get("description", "")}


DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def guarded_cv(c: ja.Candidate, job: dict):
    """The person's CV content for one job, through the disclosure guard. Call with _cv_lock held."""
    import basic_ai

    track = job.get("selected_track") if job.get("selected_track") in c.track_names else min(c.track_names)
    cv = basic_ai.BasicAI(c, ja).tailor(job, track)
    return ja.scrub_cv(cv) if ja.cv_leaks(cv) else cv


def cv_files(c: ja.Candidate, job: dict, pdf: bool = False) -> tuple[str, bytes, bytes | None]:
    """The CV for one job, made now from the profile as it is: (Word file name, Word bytes, PDF bytes)."""
    with _cv_lock:
        previous = ja.CANDIDATE
        ja.CANDIDATE = c
        try:
            cv = guarded_cv(c, job)
            fixed = ja.load_cv_profile()
            docx = ja.render_cv_docx(cv, fixed)
            pdf_bytes = cv_pdf.render(cv, fixed, c.name) if pdf else None
            name = ja.cv_file_name(job)
        finally:
            ja.CANDIDATE = previous
    return name, docx, pdf_bytes


@app.get("/api/cv/{key}")
def tailored_cv(key: str, url: str, format: str = "docx"):
    """The CV for one job, made when it's downloaded (Word, or PDF with format=pdf)."""
    c = candidate(key)
    job = job_detail(c, url)
    if not job:
        raise HTTPException(404, "Unknown job")
    name, docx, pdf = cv_files(c, job, pdf=format == "pdf")
    if pdf:
        return Response(pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{name[:-5]}.pdf"'})
    return Response(docx, media_type=DOCX_TYPE, headers={"Content-Disposition": f'attachment; filename="{name}"'})


# ---------------------------------------------------------- applying faster --
def apply_file(c: ja.Candidate) -> Path:
    """How each older job is applied to, learnt from LinkedIn after it was saved (url -> type)."""
    return ja.STATE_DIR / f"apply_{c.key}.json"


_apply_file_lock = threading.Lock()


def remember_posting(c: ja.Candidate, url: str, page: dict) -> None:
    """Keep what a LinkedIn read found: the apply type, and the description if the job had none."""
    with _apply_file_lock:
        if page.get("apply"):
            known = read_json(apply_file(c), {}) or {}
            known[url] = page["apply"]
            ja.write_json(apply_file(c), known)
        if len(page.get("description") or "") >= 150:
            cache = read_json(description_file(c), {}) or {}
            if url not in cache:
                cache[url] = page["description"]
                ja.write_json(description_file(c), cache)


def apply_type(c: ja.Candidate, job: dict, known: dict | None = None) -> tuple[str, list[str]]:
    """(type, emails) for a job: what its search saw or was learnt later - or "email" when the posting
    asks for CVs by email - and every email address in the posting (the one for CVs first)."""
    kind = (known if known is not None else read_json(apply_file(c), {}) or {}).get(job["url"]) or job.get("apply") or ""
    emails = ja.job_emails(f"{job.get('apply_email', '')} {job.get('description', '')}")
    if kind in ("", "site") and (job.get("apply_email") or ja.apply_email(job.get("description", ""))):
        kind = "email"
    return kind, emails

class ApplyChecks:
    """Older LinkedIn jobs, saved before the app noted how they're applied to, are asked once each,
    gently and one at a time, in the background (matches first). Stops at the first refused read."""
    MOST = 60
    PAUSE = 2.5

    def __init__(self):
        self.lock = threading.Lock()
        self.busy: set[str] = set()

    def start(self, c: ja.Candidate, urls: list[str]) -> bool:
        urls = urls[: self.MOST]
        with self.lock:
            if not urls or c.key in self.busy:
                return c.key in self.busy
            self.busy.add(c.key)
        threading.Thread(target=self._work, args=(c, urls), daemon=True).start()
        return True

    def _work(self, c: ja.Candidate, urls: list[str]) -> None:
        try:
            for i, url in enumerate(urls):
                if i:
                    time.sleep(self.PAUSE)
                page = ja.fetch_posting(url)
                if page is None:
                    break                       # blocked or offline: try again another time
                remember_posting(c, url, page)
        finally:
            with self.lock:
                self.busy.discard(c.key)


APPLY_CHECKS = ApplyChecks()


def start_apply_checks(c: ja.Candidate, rows: list[dict]) -> bool:
    """Ask LinkedIn about jobs worth applying to whose apply type isn't known yet. True while it runs."""
    if demo_on():
        return False
    order = {"strong": 0, "good": 1, "moderate": 2}
    todo = sorted((r for r in rows if not r["apply"] and not r["applied"] and r["verdict"] in order
                   and "linkedin.com/jobs/view/" in r["url"]), key=lambda r: (order[r["verdict"]], -r["fit"]))
    return APPLY_CHECKS.start(c, [r["url"] for r in todo])


@app.get("/api/apply-type/{key}")
def check_apply_type(key: str, url: str):
    """How one job is applied to; an older LinkedIn job is asked now (once), when it's opened."""
    c = candidate(key)
    job = job_detail(c, url)
    if not job:
        raise HTTPException(404, "Unknown job")
    if len(job.get("description") or "") < 150:
        job["description"] = (read_json(description_file(c), {}) or {}).get(url, job.get("description", ""))
    kind, emails = apply_type(c, job)
    if not kind and "linkedin.com/jobs/view/" in url and not demo_on():
        page = ja.fetch_posting(url)
        if page:
            remember_posting(c, url, page)
            if len(job.get("description") or "") < 150 and page.get("description"):
                job["description"] = page["description"]
            kind, emails = apply_type(c, job)
    return {"apply": kind, "emails": emails}


def contacts_file() -> Path:
    """Company -> its website and role email addresses, found once (shared by everyone in the app)."""
    return ja.STATE_DIR / "company_contacts.json"


_contacts_lock = threading.Lock()
CONTACTS_RECHECK_DAYS = 30


@app.get("/api/company-contact/{key}")
def company_contact(key: str, url: str):
    """The company's website and its HR / careers / contact addresses for one job, from the company's own
    site (asked once per company, then remembered)."""
    import company_contacts

    c = candidate(key)
    job = job_detail(c, url)
    if not job:
        raise HTTPException(404, "Unknown job")
    firm = ja.company_key(job.get("company", ""))
    known = (read_json(contacts_file(), {}) or {}).get(firm) if firm else None
    if known and known.get("checked", "") >= (datetime.now() - timedelta(days=CONTACTS_RECHECK_DAYS)).isoformat():
        return {"site": known.get("site", ""), "emails": known.get("emails", [])}
    if demo_on() or not firm:
        return {"site": "", "emails": []}
    site = job.get("company_site", "") if str(job.get("company_site", "")).startswith("http") else ""
    if not site:
        site = company_contacts.linkedin_company_site(url)
        if site is None:                                # LinkedIn didn't answer: ask again next time
            return {"site": "", "emails": []}
    emails = company_contacts.site_emails(site) if site else []
    with _contacts_lock:
        cache = read_json(contacts_file(), {}) or {}
        cache[firm] = {"site": site, "emails": emails, "checked": datetime.now().isoformat(timespec="seconds")}
        ja.write_json(contacts_file(), cache)
    return {"site": site, "emails": emails}


# ------------------------------------------------------------------ email --
MAX_EMAIL_JOBS = 10
RUN_EMAIL_JOBS = 5                      # after a search: only the five best, so the email gets read


def _two_lines(text: str, limit: int = 260) -> str:
    """About two lines of a posting: whole sentences up to the limit."""
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    return cut[: end + 1] if end > limit * 0.45 else cut.rsplit(" ", 1)[0] + "…"


def email_html(person: str, jobs: list[dict], intro: str) -> str:
    """A plain, readable email (tables and inline styles, so every mail app shows it the same)."""
    from html import escape as e

    colours = {"strong": "#2f7a4d", "good": "#2e5e9e", "moderate": "#a2620f", "weak": "#9a978f"}
    rows = []
    for j in jobs:
        url = j["url"] if str(j.get("url", "")).startswith(("https://", "http://")) else ""
        verdict = j.get("fit_verdict") or ja.verdict(int(j.get("fit_score") or 0))
        about = _two_lines(j.get("summary") or j.get("description") or "")
        why = (j.get("reasoning") or "").strip()
        place = " · ".join(x for x in (j.get("company"), "Remote" if j.get("remote") else "", j.get("location")) if x)
        title = f'<a href="{e(url)}" style="color:#1b1a17;text-decoration:none">{e(j["title"])}</a>' if url else e(j["title"])
        site = ja.SITES.get(j.get("source", ""), "the site")
        how = {"easy": f"Easy Apply on {site} - a few minutes",
               "email": f"Apply by email: {', '.join(j.get('emails') or [])}",
               "site": "Apply on the company's site - a longer form"}.get(j.get("apply") or "", "")
        how_html = (f'<div style="font-size:13px;font-weight:600;margin:0 0 10px;color:'
                    f'{"#2f7a4d" if j.get("apply") in ("easy", "email") else "#5f5d57"}">{e(how)}</div>') if how else ""
        rows.append(f"""
<tr><td style="padding:20px 0;border-top:1px solid #e3e1db">
  <div style="font-size:12.5px;color:#5f5d57">{e(place)}</div>
  <div style="font-size:17px;font-weight:600;line-height:1.35;margin:3px 0 6px">{title}</div>
  <div style="font-size:13px;margin-bottom:10px"><b style="color:{colours.get(verdict, '#1b1a17')}">{int(j.get('fit_score') or 0)}</b>
    <span style="color:#5f5d57"> / 100 · {e(verdict.title())} fit</span></div>
  {how_html}
  {f'<p style="margin:0 0 8px;font-size:14px;line-height:1.55"><b>About the role.</b> {e(about)}</p>' if about else ''}
  {f'<p style="margin:0 0 12px;font-size:14px;line-height:1.55"><b>Why you fit.</b> {e(why)}</p>' if why else ''}
  {f'<a href="{e(url)}" style="display:inline-block;background:#1b1a17;color:#ffffff;text-decoration:none;font-size:13px;font-weight:600;padding:9px 16px;border-radius:7px">Open the job</a>' if url else ''}
  <span style="font-size:12px;color:#9a978f;padding-left:10px">CV attached: {e(j.get('cv_name', ''))} (PDF and Word)</span>
</td></tr>""")
    return f"""<!DOCTYPE html><html><body style="margin:0;background:#faf9f6">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#faf9f6"><tr><td align="center" style="padding:28px 16px">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:620px;font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#1b1a17">
<tr><td style="padding-bottom:14px"><div style="font-size:22px;font-weight:700">{e(intro)}</div>
<div style="font-size:13px;color:#5f5d57;margin-top:4px">For {e(person)} · {datetime.now():%d %b %Y}</div></td></tr>
{''.join(rows)}
<tr><td style="padding-top:18px;border-top:1px solid #e3e1db;font-size:12px;color:#9a978f">Each CV is made from the profile for that job. Check it before you send it.</td></tr>
</table></td></tr></table></body></html>"""


def resend_env(c: ja.Candidate) -> str:
    """Where one person's own Resend key is kept (.env, never sent to the browser)."""
    return "RESEND_API_KEY_" + re.sub(r"[^A-Z0-9]+", "_", c.key.upper())


def resend_key_for(c: ja.Candidate) -> str | None:
    return os.environ.get(resend_env(c), "").strip() or None


def send_jobs_email(c: ja.Candidate, jobs: list[dict], to: str, intro: str, subject: str) -> int:
    """One email: the jobs, each with its CV as PDF and Word. Returns how many were sent.
    Sent with the person's own Resend key when their profile has one, else the app's."""
    files = []
    for j in jobs:
        name, docx, pdf = cv_files(c, j, pdf=True)
        j["cv_name"] = name[:-5]
        files += [(f"{name[:-5]}.pdf", pdf, "application/pdf"), (name, docx, DOCX_TYPE)]
    mailer.send(to, subject, email_html(c.name, jobs, intro), files, from_name="Job Finder",
                resend_key=resend_key_for(c))
    return len(jobs)


def email_status(c: ja.Candidate) -> dict:
    prof, _ = profile_data(c)
    return {"key": c.key, "name": c.name, "email": prof.get("notify_email", ""),
            "has_key": bool(resend_key_for(c) or mailer.method())}


@app.get("/api/profile/{key}/email")
def profile_email(key: str):
    """One person's email setup (Settings, Email): where their matches go, and whether a key is saved."""
    return email_status(candidate(key))


class EmailSetupRequest(BaseModel):
    email: str = Field("", max_length=200)
    key: str = Field("", max_length=200)
    test: bool = True


@app.post("/api/profile/{key}/email")
def save_profile_email(key: str, body: EmailSetupRequest):
    """Save where one person's matches go and their Resend key (kept in .env, never shown again), then
    send them a test. Each person's emails go only to their own address. An empty address turns emails off."""
    c = candidate(key)
    email = body.email.strip()
    if email and not re.fullmatch(r"[^@\s,]+@[^@\s,]+\.[^@\s,]+", email):
        raise HTTPException(400, "The email address doesn't look right.")
    new = body.key.strip()
    if new:
        if not re.fullmatch(r"re_[A-Za-z0-9_]{8,}", new):
            raise HTTPException(400, "That isn't a Resend key. It starts with re_ - copy it from resend.com, API Keys.")
        write_env({resend_env(c): new})
    current, _ = profile_data(c)
    if current.get("notify_email", "") != email:
        profiles.write(ja.CANDIDATES_DIR, c.key, clean_profile({**current, "notify_email": email}, current))
    if email and body.test:
        if not (resend_key_for(c) or mailer.method()):
            raise HTTPException(400, "Paste the Resend key too: step 2.")
        try:
            mailer.send(email, "Job Finder: email works", f"<p>Email is set up for {c.name}. The best matches of each "
                        "search will arrive like this, with their CVs attached.</p>", resend_key=resend_key_for(c))
        except mailer.MailError as exc:
            raise HTTPException(400, str(exc)) from exc
    return email_status(candidate(key))


def email_run_matches(key: str, folder: Path) -> str:
    """After a search: its best matches in one email to the address in the profile. Returns a log line."""
    c = candidate(key)
    prof, _ = profile_data(c)
    to = prof.get("notify_email", "")
    if not to:
        return "email: not set up for this person (Settings, Email) - nothing sent"
    hidden = load_hidden(c)
    found = [j for j in read_json(folder / "evaluated.json", []) or []
             if j.get("fit_verdict") in ("strong", "good") and j.get("url") not in hidden]
    if not found:
        return "email: no strong or good matches this time - nothing sent"
    known = read_json(apply_file(c), {}) or {}
    for j in found:
        j["apply"], j["emails"] = apply_type(c, j, known)
    # The few best, quickest to apply to first: Easy Apply and by-email jobs, then the rest, best score first.
    quick = {"easy": 0, "email": 0}
    best = sorted(found, key=lambda j: (quick.get(j["apply"], 1), -int(j.get("fit_score") or 0)))[:RUN_EMAIL_JOBS]
    jobs = [{**(job_detail(c, j["url"]) or j), "apply": j["apply"], "emails": j["emails"]} for j in best]
    n = len(jobs)
    send_jobs_email(c, jobs, to, f"{n} new {'match' if n == 1 else 'matches'}",
                    f"{n} new job {'match' if n == 1 else 'matches'} for {first_name(c.name)} - {datetime.now():%d %b}")
    return f"email: sent {n} matches with their CVs to {to}"


class EmailJobRequest(BaseModel):
    candidate: str
    url: str


@app.post("/api/email-job")
def email_job(body: EmailJobRequest):
    """One job, with its CV as PDF and Word, to the address in the profile."""
    c = candidate(body.candidate)
    job = job_detail(c, body.url)
    if not job:
        raise HTTPException(404, "Unknown job")
    prof, _ = profile_data(c)
    to = prof.get("notify_email", "")
    if not to:
        raise HTTPException(400, "Set up email for this person first: Settings, Email.")
    try:
        send_jobs_email(c, [job], to, job["title"], f"{job['title']} - {job.get('company', '')}".strip(" -"))
    except mailer.MailError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True, "to": to}


@app.get("/api/mail")
def mail_setup():
    """Email setup: whether it's ready (the key itself is never sent back)."""
    return {"method": mailer.method(), "has_key": bool(os.environ.get("RESEND_API_KEY", "").strip())}


class MailSetupRequest(BaseModel):
    key: str = Field("", max_length=200)
    test_to: str = Field("", max_length=200)


@app.post("/api/mail")
def save_mail(body: MailSetupRequest):
    """Save the Resend key, then send a test email to check it works."""
    key = body.key.strip()
    if key:
        if not re.fullmatch(r"re_[A-Za-z0-9_]{8,}", key):
            raise HTTPException(400, "That isn't a Resend key. It starts with re_ - copy it from resend.com, API Keys.")
        write_env({"RESEND_API_KEY": key})
    to = body.test_to.strip()
    if to:
        if not re.fullmatch(r"[^@\s,]+@[^@\s,]+\.[^@\s,]+", to):
            raise HTTPException(400, "The test address doesn't look right.")
        try:
            mailer.send(to, "Job Finder: email works", "<p>Email is set up. The best matches of each search "
                        "will arrive like this, with their CVs attached.</p>")
        except mailer.MailError as exc:
            raise HTTPException(400, str(exc)) from exc
    return {"method": mailer.method()}


class DeleteJobRequest(BaseModel):
    candidate: str
    url: str
    deleted: bool = True                # False = undo


@app.post("/api/jobs/delete")
def delete_job(body: DeleteJobRequest):
    """Remove a job from the list for good (undo with deleted=false)."""
    c = candidate(body.candidate)
    if body.url not in load_state(c)["seen"]:
        raise HTTPException(404, "Unknown job")
    marks = load_hidden(c)
    if body.deleted:
        marks.setdefault(body.url, ja.now_iso())
    else:
        marks.pop(body.url, None)
    write_marks(hidden_file(c), marks)
    return {"deleted": body.url in marks}


class ClearJobsRequest(BaseModel):
    candidate: str


@app.post("/api/jobs/clear")
def clear_jobs(body: ClearJobsRequest):
    """Start one person's list from scratch: their jobs, marks, searches and CVs move to
    backups/ (never erased). The next search looks back further, as a first search does."""
    c = candidate(body.candidate)
    if RUNS.active(c.key) or (runs_root() / c.key / ".lock").exists():
        raise HTTPException(409, "Wait for the running search to finish first.")
    dest = ROOT / "backups" / f"{time.strftime('%Y%m%d-%H%M%S')}-{c.key}{'-demo' if demo_on() else ''}"
    moved = 0
    for path in (state_dir() / c.state_name, applied_file(c), hidden_file(c)):
        if path.exists():
            dest.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(dest / path.name))
            moved += 1
    for run in run_dirs(c):
        (dest / "runs").mkdir(parents=True, exist_ok=True)
        shutil.move(str(run), str(dest / "runs" / run.name))
        moved += 1
    return {"ok": True, "backup": str(dest.relative_to(ROOT)) if moved else None}


class DemoRequest(BaseModel):
    on: bool


@app.post("/api/demo")
def set_demo(body: DemoRequest):
    """Demo Mode: sample postings and a simulated AI, kept in demo/ - never the real data."""
    flag = DEMO_DIR / ".enabled"
    if body.on:
        DEMO_DIR.mkdir(parents=True, exist_ok=True)
        flag.write_text("Demo Mode is on. Delete this file (or switch it off in the app) to use real data.\n", encoding="utf-8")
    else:
        flag.unlink(missing_ok=True)
    return {"demo": demo_on()}


@app.post("/api/demo/reset")
def reset_demo():
    """Clear the demo data (only ever the demo folder)."""
    if any(RUNS.active(k) for k in candidate_keys()):
        raise HTTPException(409, "Wait for the running search to finish first.")
    for pattern in ("jobs*.json", "applied_*.json", "hidden_*.json"):
        for path in DEMO_DIR.glob(pattern):
            path.unlink()
    shutil.rmtree(DEMO_DIR / "runs", ignore_errors=True)
    return {"ok": True}


@app.post("/api/login")
def login(body: LoginRequest):
    secret = password()
    if secret and not hmac.compare_digest(body.password.encode(), secret.encode()):
        raise HTTPException(401, "Wrong password")
    response = JSONResponse({"ok": True})
    if secret:
        response.set_cookie(SESSION_COOKIE, session_token(secret), httponly=True, samesite="strict")
    return response


@app.get("/api/overview/{key}")
def overview(key: str):
    c = candidate(key)
    state = load_state(c)
    hidden = load_hidden(c)
    seen = {u: v for u, v in state["seen"].items() if u not in hidden}
    verdicts = Counter(v.get("fit_verdict") for v in seen.values())
    rows = job_rows(c)
    top = sorted((r for r in rows if r["verdict"] in ("strong", "good") and r["status"] != "emailed"),
                 key=lambda r: r["fit"], reverse=True)[:6]
    if not top:
        top = sorted((r for r in rows if r["verdict"] in ("strong", "good")), key=lambda r: r["fit"], reverse=True)[:6]
    settings = settings_for()
    ready = profile_readiness(c)
    keys_missing = not demo_on() and any(not is_set(e) or key_rejected(e)
                                         for e in required_env(c, "real", settings["email"], settings["chatgpt"]))
    blocked = "profile" if not c.keywords else ("settings" if keys_missing else None)
    return {
        "name": c.name,
        "first_name": first_name(c.name),
        "system_label": c.system_label,
        "thresholds": thresholds(),
        "metrics": {
            "evaluated": len(seen),
            "strong": verdicts.get("strong", 0),
            "good": verdicts.get("good", 0),
            "moderate": verdicts.get("moderate", 0),
            "pending": len(state["pending"]),
            "emailed": sum(1 for v in seen.values() if v.get("emailed_at")),
        },
        # What pressing Search does for this person, in plain terms.
        "plan": {
            "sites": [ja.SITES[s] for s in (c.sources or configured_sources()) if s in ja.SITES],
            "titles": len(c.keywords),
            "country": c.location or env_value("LOCATION") or ja.LOCATION,
            "hours": settings["search_hours"],
            "first": not state["seen"],
        },
        "runs": [run_summary(p) for p in run_dirs(c)[:6]],
        "top": top,
        # Sidebar badges: what's still open in this person's Profile, and in Settings.
        "readiness": {"profile": ready["open"], "settings": settings["total"] - settings["done"]},
        # Whether Run Search can start right now (job titles to search, no missing or rejected key),
        # and if not, which page fixes it.
        "can_run": not blocked,
        "blocked": blocked,
        "active": activity(c),
    }


@app.get("/api/jobs/{key}")
def jobs(key: str):
    c = candidate(key)
    rows = job_rows(c)
    return {"jobs": rows, "thresholds": thresholds(), "checking_apply": start_apply_checks(c, rows),
            "country": c.location or ja.LOCATION}


@app.get("/api/runs/{key}")
def runs(key: str):
    c = candidate(key)
    return {"runs": [run_summary(p) for p in run_dirs(c)]}


@app.get("/api/runs/{key}/{stamp}/digest", response_class=HTMLResponse)
def digest(key: str, stamp: str):
    path = run_dir(candidate(key), stamp) / "digest.html"
    if not path.exists():
        raise HTTPException(404, "No digest for this run")
    return HTMLResponse(
        path.read_text(encoding="utf-8"),
        headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src data: https:"},
    )


@app.get("/api/runs/{key}/{stamp}/log", response_class=PlainTextResponse)
def run_log(key: str, stamp: str):
    path = run_dir(candidate(key), stamp) / "run.log"
    if not path.exists():
        raise HTTPException(404, "No log for this run")
    return PlainTextResponse(path.read_text(encoding="utf-8"))


@app.get("/api/runs/{key}/{stamp}/cvs/{name}")
def cv_file(key: str, stamp: str, name: str):
    folder = run_dir(candidate(key), stamp) / "cvs"
    files = {p.name: p for p in folder.glob("*.docx")} if folder.is_dir() else {}
    if name not in files:
        raise HTTPException(404, "No such CV")
    return FileResponse(files[name], filename=name,
                        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


@app.get("/api/settings")
def settings():
    return settings_for()


@app.post("/api/settings")
def save_settings(body: SettingsRequest):
    allowed = settings_keys()
    updates = {}
    for name, raw in body.values.items():
        value = raw.strip()
        if name not in allowed:
            raise HTTPException(400, f"{name} cannot be set here")
        if not value:
            continue
        if any(ch in value for ch in '\r\n"'):
            raise HTTPException(400, f"{name}: line breaks and quotes are not allowed")
        if (name.startswith("EMAIL_") and not name.startswith("EMAIL_CC") and "@" not in value):
            raise HTTPException(400, f"{name} must be an email address")
        if name == "AI_MODE" and value not in ja.AI_MODES:
            raise HTTPException(400, "AI_MODE must be basic or chatgpt")
        if name == "SEARCH_HOURS" and value not in {str(h) for h in SEARCH_PERIODS}:
            raise HTTPException(400, "Choose 24 hours, 3 days or 7 days")
        if name == "DAILY_SEARCH" and value not in ("on", "off"):
            raise HTTPException(400, "DAILY_SEARCH must be on or off")
        if check_key(name, value) is False:          # None (offline) still saves
            raise HTTPException(400, KEY_HINTS[name])
        updates[name] = value
    if updates:
        write_env(updates)
    return {"ok": True, "saved": sorted(updates)}


@app.post("/api/checklist")
def save_check(body: CheckRequest):
    if body.scope != "_shared":
        c = candidate(body.scope)
        valid = {i["id"] for i in candidate_checklist(c)}
    else:
        valid = {i["id"] for i in SHARED_TASKS}
    if body.item not in valid:
        raise HTTPException(400, "Unknown checklist item")
    checks = load_checks()
    checks.setdefault(body.scope, {})[body.item] = body.done
    CHECKLIST_FILE.write_text(json.dumps(checks, indent=1), encoding="utf-8")
    return {"ok": True}


@app.get("/api/run-options/{key}")
def run_options(key: str):
    c = candidate(key)
    sync_env()
    email, chatgpt = email_on(), chatgpt_on()

    def missing(mode: str) -> list[dict]:
        out = [] if c.keywords else [{"env": "titles", "label": "job titles to search", "where": "profile"}]
        if not demo_on():
            out += [{"env": e, "where": "settings" if e in settings_keys() - {c.email_to_env, c.email_cc_env} else "profile",
                     "label": env_label(c, e) if not is_set(e) else f"working {env_label(c, e)}"}
                    for e in required_env(c, mode, email, chatgpt) if not is_set(e) or key_rejected(e)]
        return out

    return {
        "sources_all": [{"key": k, "label": label} for k, label in ja.SITES.items()],
        "sources_default": [s for s in (c.sources or configured_sources()) if s in ja.SITES],
        "replayable": [{"stamp": p.name, "label": stamp_label(p.name)} for p in run_dirs(c) if (p / "raw.json").exists()],
        "recipient": env_value(c.email_to_env),
        "demo": demo_on(),
        "email": email,
        "chatgpt": chatgpt,
        "missing": {mode: missing(mode) for mode in ("dry", "replay", "real")},
        "active": activity(c),
    }


@app.post("/api/run")
def start_run(body: RunRequest):
    c = candidate(body.candidate)
    sync_env()
    demo, email, chatgpt = demo_on(), email_on(), chatgpt_on()
    if not c.keywords:
        raise HTTPException(400, f"Add the job titles to search in {first_name(c.name)}’s Profile first.")
    missing = [] if demo else [env_label(c, e) for e in required_env(c, body.mode, email, chatgpt) if not is_set(e)]
    if missing:
        raise HTTPException(400, "Missing: " + ", ".join(missing))
    rejected = [] if demo else [e for e in required_env(c, body.mode, email, chatgpt) if key_rejected(e)]
    if rejected:
        raise HTTPException(400, KEY_HINTS[rejected[0]])
    if email and body.mode == "real" and not body.confirm:
        raise HTTPException(400, "Confirm the recipient before a live run")
    # Without email there is nothing to hold back: a search or a replay saves its matches to the app.
    dry = body.mode == "dry" or (body.mode == "replay" and email)
    args: list[str] = ["--dry-run"] if dry else []
    if demo:
        args += ["--demo", "--data-dir", str(DEMO_DIR)]
    if body.mode == "replay":
        if not body.replay:
            raise HTTPException(400, "Choose a saved scrape to replay")
        raw = run_dir(c, body.replay) / "raw.json"
        if not raw.exists():
            raise HTTPException(400, "That run has no saved scrape")
        args += ["--from-file", str(raw)]
    else:
        # No sites given (the one-click search): the person's own job sites from their profile.
        sources = body.sources or [s for s in (c.sources or configured_sources()) if s in ja.SITES]
        unknown = [s for s in sources if s not in ja.SITES]
        if unknown or not sources:
            raise HTTPException(400, "Choose at least one job site")
        args += ["--sources", ",".join(sources)]
    if body.limit:
        args += ["--limit", str(body.limit)]
    if body.no_cv:
        args.append("--no-cv")
    run = RUNS.start(c.key, body.mode, args)
    return run.to_dict()


@app.get("/api/run/{run_id}")
def run_status(run_id: str, since: int = 0):
    run = RUNS.get(run_id)
    if not run:
        raise HTTPException(404, "Unknown run")
    return run.to_dict(max(0, since))


class FileUpload(BaseModel):
    filename: str = Field(max_length=200)
    data: str = Field(max_length=12_000_000)       # base64; cv_import caps the file at 8 MB


class CreateProfileRequest(BaseModel):
    name: str = Field("", max_length=80)
    file: FileUpload | None = None


class SaveProfileRequest(BaseModel):
    profile: dict


def read_upload(upload: FileUpload) -> dict:
    """An uploaded questionnaire or CV -> {'fields', 'found', 'source'}; a readable 400 when it can't be used."""
    try:
        data = base64.b64decode(upload.data, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(400, "The file didn't arrive in one piece. Try again.") from exc
    try:
        answers = questionnaire.read(upload.filename, data) if len(data) <= cv_import.MAX_BYTES else None
        if answers:
            return answers
        # A CV, a Career Discovery record, or a CV followed by its record ("source" says which).
        texts = cv_import.extract_texts(upload.filename, data)        # a PDF: stored order, and page order
        return cv_import.read_document(texts[0], texts[1:])
    except cv_import.ImportError_ as exc:
        raise HTTPException(400, str(exc)) from exc


def clean_profile(data: dict, base: dict | None = None) -> dict:
    try:
        return profiles.clean(data, base=base)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


def profile_view(c: ja.Candidate, found: list[str] | None = None, source: str = "") -> dict:
    """Everything the Profile page shows and edits for one person."""
    prof, saved = profile_data(c)
    cfg = candidate_config(c.key)
    tracks = []
    if c.kind != "simple":
        for n in sorted(c.track_names):
            t = (cfg.get("tracks") or {}).get(str(n), {})
            tracks.append({"n": n, "name": c.track_names[n], "positioning": t.get("positioning", ""),
                           "lead": t.get("lead_evidence", []), "keywords": t.get("keywords", [])})
    groups = profile_groups(c)
    done, total = _count(groups)
    return {
        "key": c.key,
        "kind": c.kind,
        "saved": saved,
        "profile": prof,
        "missing": profiles.missing(prof),
        "open": len(profiles.missing(prof)) + total - done,
        "groups": groups,
        "options": {"countries": profiles.COUNTRIES, "levels": profiles.LEVELS,
                    "sites": [{"key": k, "label": label} for k, label in ja.SITES.items()],
                    "work_modes": profiles.WORK_MODES, "job_types": profiles.JOB_TYPES,
                    "remote_places": profiles.REMOTE_PLACES},
        "system_label": c.system_label,
        "tracks": tracks,
        "draft": c.kind == "advanced",          # Atef's tracks are a draft until the client approves them
        "knowledge": knowledge_files(c),
        "chatgpt": chatgpt_on(),
        "searches": max(1, -(-len(c.keywords) // ja.KEYWORDS_PER_QUERY)) if c.keywords else 0,
        "found": found or [],
        "source": source,                       # what was just imported: "questionnaire" or "cv"
        "mail": {"own_key": bool(resend_key_for(c)), "app_key": bool(mailer.method())},
    }


@app.get("/api/profile/{key}")
def profile(key: str):
    return profile_view(candidate(key))


@app.post("/api/profile/{key}")
def save_profile(key: str, body: SaveProfileRequest):
    """Save the whole profile (the page sends it after every change)."""
    c = candidate(key)
    current, _ = profile_data(c)
    # Where emails go is set in Settings, Email - the profile page never changes it.
    page = {**body.profile, "notify_email": current.get("notify_email", "")}
    profiles.write(ja.CANDIDATES_DIR, key, clean_profile(page, current))
    return profile_view(candidate(key))


@app.post("/api/profiles")
def create_profile(body: CreateProfileRequest):
    """Add a person: from a name, or from their filled-in questionnaire or CV, or both."""
    imported = read_upload(body.file) if body.file else {"fields": {}, "found": [], "source": ""}
    draft = cv_import.merge(profiles.blank(), imported["fields"])
    if body.name.strip():
        draft["name"] = body.name.strip()
    if not draft["name"]:
        where = {"questionnaire": "questionnaire", "record": "discovery record"}.get(imported["source"], "CV")
        raise HTTPException(400, f"No name was found in the {where}. Type the person's full name, then create the profile.")
    if not draft["search"]["titles"] and draft.get("headline"):
        draft["search"]["titles"] = [draft["headline"].split("|")[0].strip()]
    key = profiles.create(ja.CANDIDATES_DIR, clean_profile(draft), set(candidate_keys()))
    return {"key": key, "found": imported["found"], "source": imported["source"]}


@app.post("/api/profile/{key}/import")
def import_cv(key: str, body: FileUpload):
    """Fill this profile from a returned questionnaire or a CV: what the file provides replaces
    what was there; what it leaves empty is kept."""
    c = candidate(key)
    imported = read_upload(body)
    current, _ = profile_data(c)
    merged = cv_import.merge(current, imported["fields"])
    profiles.write(ja.CANDIDATES_DIR, key, clean_profile(merged, current))
    return profile_view(candidate(key), imported["found"], imported["source"])


def pdf_response(data: bytes, filename: str) -> Response:
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})


@app.get("/api/questionnaire")
def blank_questionnaire():
    """The questionnaire, blank: to send to someone new."""
    return pdf_response(questionnaire.build(), "Job_Search_Questionnaire.pdf")


@app.get("/api/profile/{key}/questionnaire")
def profile_questionnaire(key: str):
    """The questionnaire filled in with everything the profile has so far, for the person to
    check and complete."""
    c = candidate(key)
    prof, _ = profile_data(c)
    name = re.sub(r"[^A-Za-z0-9]+", "_", prof.get("name") or c.key).strip("_") or "Profile"
    return pdf_response(questionnaire.build(prof), f"{name}_Questionnaire.pdf")


@app.get("/api/job-description/{key}")
def job_description(key: str, url: str):
    """The full posting for a job that was saved without one (read from LinkedIn when it's opened,
    then kept). Bayt doesn't allow this, so its jobs come back empty."""
    c = candidate(key)
    cache = read_json(description_file(c), {}) or {}
    if url in cache:
        return {"description": cache[url]}
    if url not in load_state(c)["seen"]:
        raise HTTPException(404, "Unknown job")
    page = ja.fetch_posting(url) or {}
    remember_posting(c, url, page)                  # the same read also tells how the job is applied to
    return {"description": page.get("description", "")}


@app.post("/api/profile/{key}/delete")
def delete_profile(key: str):
    c = candidate(key)
    if RUNS.active(key):
        raise HTTPException(409, "Wait for the running search to finish first.")
    try:
        profiles.delete(ja.CANDIDATES_DIR, c.key)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True}


@app.get("/api/profile/{key}/cv")
def preview_cv(key: str):
    """The standard CV as a Word file, made here from the profile - what free mode sends with a
    match (headed with each job's title)."""
    c = candidate(key)
    prof, _ = profile_data(c)
    content = profiles.cv_content(prof)
    cv = ja.TailoredCV(
        headline=content["pillar"] or profiles.track_name(prof),
        about_paragraphs=content["about"], achievements_title=content["achievements_title"],
        key_achievements=content["achievements"],
        work_experience=[ja.WorkExperienceEntry(**e) for e in content["experience"]],
        core_competencies=content["competencies"],
    )
    data = ja.render_cv_docx(cv, profiles.cv_fixed(prof))
    name = re.sub(r"[^A-Za-z0-9]+", "_", prof.get("name") or c.key).strip("_") or "Profile"
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f'attachment; filename="{name}_CV.docx"'})


def knowledge_files(c: ja.Candidate) -> list[dict]:
    folder = ja.RUNS_DIR / c.key / "knowledge"
    return [{"name": p.name, "size": p.stat().st_size} for p in sorted(folder.glob("*.md"))] if folder.is_dir() else []


@app.post("/api/knowledge/{key}/export")
def export_knowledge(key: str):
    c = candidate(key)
    result = subprocess.run(
        pipeline_command(["--candidate", c.key, "--export-knowledge"]), cwd=ROOT, capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=180,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"}, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode != 0:
        raise HTTPException(500, (result.stdout + result.stderr).strip()[-600:] or "Export failed")
    return {"files": knowledge_files(c)}


@app.get("/api/knowledge/{key}/{name}", response_class=PlainTextResponse)
def knowledge_file(key: str, name: str):
    c = candidate(key)
    files = {f["name"] for f in knowledge_files(c)}
    if name not in files:
        raise HTTPException(404, "No such file")
    return PlainTextResponse((ja.RUNS_DIR / c.key / "knowledge" / name).read_text(encoding="utf-8"))


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
