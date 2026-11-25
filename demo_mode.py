"""Demo Mode: sample postings and a simulated AI, so the whole app can be tried
before the client's API keys arrive.

Used only by `job_automation.py --demo` (the web app's Demo Mode). Nothing in
here calls an external service: no Apify, no OpenAI, no Brevo. Postings and
companies are invented; CVs are assembled from each person's approved facts
(data/demo.json), and they still pass through the normal disclosure guard.
"""

from __future__ import annotations

import json
import random
import re
import time
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent / "data" / "demo.json"
CANDIDATES_DIR = Path(__file__).resolve().parent / "candidates"
NATIONALITY_REASON = "تم استبعاد الوظيفة تلقائياً نظراً لاشتراط جنسية محددة (السعودية / الإماراتية / جنسيات الخليج) غير متطابقة."
PACE = {"scrape": 1.4, "evaluate": 1.0, "cv": 0.6}   # seconds, so the progress view has something to show
SAMPLE_COMPANIES = ["Northwind Holding", "Contoso Group", "Fabrikam Industries", "Tailspin Ventures",
                    "Litware Partners", "Adatum Corporation", "Proseware Capital", "Woodgrove Financial"]
SAMPLE_TEAMS = ["Head Office", "Regional", "Growth", "Operations", "Strategy", "Transformation", "Projects",
                "Shared Services", "New Ventures"]
CAPITALS = {"Saudi Arabia": "Riyadh", "United Arab Emirates": "Dubai", "Qatar": "Doha", "Kuwait": "Kuwait City",
            "Bahrain": "Manama", "Oman": "Muscat", "Egypt": "Cairo"}


def profile(key: str, base: Path | None = None) -> dict:
    """Demo data for a person: data/demo.json for the original people; for someone added in
    the app, sample postings made from their own job titles."""
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    if key in data and not key.startswith("_"):
        return data[key]
    import profiles

    p = profiles.read(base or CANDIDATES_DIR, key)
    return _from_profile(p, profiles) if p else data["ahmed"]


def _from_profile(p: dict, profiles) -> dict:
    titles = p["search"]["titles"] or [profiles.track_name(p)]
    country = p["search"]["country"]
    city = p.get("city") or CAPITALS.get(country, "")
    fits = [90, 86, 82, 77, 73, 70, 62, 55, 42]
    posts = [{"title": f"{titles[i % len(titles)]} ({SAMPLE_TEAMS[i]})", "track": 1, "fit": fit}
             for i, fit in enumerate(fits)]
    posts.append({"title": f"{titles[0]} (Nationals Programme)", "track": 1, "fit": 80, "note": "nationality"})
    strength = (p["cv"]["achievements"] or p["cv"]["skills"] or [profiles.track_name(p)])[0]
    return {
        "name_ar": p.get("name", ""),
        "companies": [[c, f"{city}, {country}" if city else country] for c in SAMPLE_COMPANIES],
        "postings": posts,
        "tracks": {"1": {"en": f"leads {profiles.track_name(p)} work", "ar": profiles.track_name(p),
                         "strength": strength, "gap": "قد تتوقع الوظيفة خبرة أوسع في هذا القطاع."}},
        "cv": profiles.cv_content(p),
    }


def postings(key: str, count: int = 9, rng: random.Random | None = None, base: Path | None = None) -> list[dict]:
    """Sample postings shaped like scraped items, each with a fresh id."""
    rng = rng or random.Random()
    d = profile(key, base)
    stamp = int(time.time() * 1000)
    picks = rng.sample(d["postings"], min(count, len(d["postings"])))
    items = []
    for i, post in enumerate(picks):
        company, city = rng.choice(d["companies"])
        if post.get("note") == "abroad":
            city = "Dubai, United Arab Emirates"
        focus = d["tracks"][str(post["track"])]["en"]
        description = (
            f"{company} is hiring a {post['title']} based in {city}. The role {focus}, working closely with "
            "senior leadership and cross-functional teams. Requirements: 12+ years of relevant experience, strong "
            "stakeholder management, and excellent written Arabic and English."
        )
        if post.get("note") == "nationality":
            description += " This position is open to Saudi nationals only."
        items.append({
            "_source": "demo",
            "url": f"https://example.com/demo-jobs/{stamp}{i:02d}",
            "title": post["title"],
            "company": company,
            "location": city,
            "description": description,
        })
    time.sleep(PACE["scrape"])
    return items


class DemoAI:
    """Stands in for the OpenAI client - the same parse() call the pipeline makes - and
    answers from data/demo.json instead of a model."""

    def __init__(self, candidate, pipeline):
        self.candidate = candidate
        self.ja = pipeline                   # the running job_automation module (its schema classes)
        self.d = profile(candidate.key, getattr(pipeline, "CANDIDATES_DIR", None))
        if getattr(candidate, "cv_content", None):
            self.d = {**self.d, "cv": candidate.cv_content()}     # the CV as edited in the app

    def parse(self, *, model, messages, response_format):
        if response_format is self.ja.BatchEvaluations:
            time.sleep(PACE["evaluate"])
            return self.ja.BatchEvaluations(evaluations=[self._evaluate(job) for job in self._jobs(messages[-1]["content"])])
        time.sleep(PACE["cv"])
        return self._cv(messages[1]["content"])

    @staticmethod
    def _jobs(prompt: str) -> list[dict]:
        jobs = []
        for block in prompt.split("\n\n---\n\n"):
            fields = dict(re.findall(r"^(job_url|title|company|location): (.*)$", block, re.M))
            if "job_url" in fields:
                fields["description"] = block.split("description:", 1)[-1]
                jobs.append(fields)
        return jobs

    def _evaluate(self, job: dict):
        ja = self.ja
        post = next((p for p in self.d["postings"] if p["title"] == job.get("title")), {"fit": 55, "track": 1})
        track = post["track"]
        if "Saudi nationals only" in job.get("description", ""):
            return ja.JobEvaluation(
                job_url=job["job_url"], ats_score=0, interview_score=0, fit_score=0, selected_track=1,
                secondary_track=None, track_selection_confidence="high", selected_track_reason=NATIONALITY_REASON,
                tailoring_level="light", summary=None, reasoning=NATIONALITY_REASON,
            )
        rng = random.Random(job["job_url"])
        base = post["fit"]
        ats = max(0, min(100, base + rng.randint(-3, 5)))
        interview = max(0, min(100, base + rng.randint(-5, 3)))
        fit = round(ats * .45 + interview * .55)
        t = self.d["tracks"][str(track)]
        name = self.d["name_ar"]
        written = fit > 50
        return ja.JobEvaluation(
            job_url=job["job_url"], ats_score=ats, interview_score=interview, fit_score=fit, selected_track=track,
            secondary_track=None if track == 1 else 1,
            track_selection_confidence="high" if base >= 80 else "medium",
            selected_track_reason=f"يتمحور الوصف الوظيفي حول {t['ar']}، وهو ما يطابق المسار {track}.",
            tailoring_level="light" if base >= 82 else "moderate" if base >= 72 else "deep",
            summary=(f"تبحث {job.get('company', '')} عن {job.get('title', '')} يقود {t['ar']}، بالتنسيق مع الإدارة العليا "
                     "والفرق المعنية، مع متطلبات خبرة طويلة وإتقان العربية والإنجليزية.") if written else None,
            reasoning=f"يتوافق الدور مع خبرة {name} في {t['strength']}. {t['gap']}" if written else None,
        )

    def _cv(self, prompt: str):
        ja, cv = self.ja, self.d["cv"]
        title = (re.search(r"^Title: (.+)$", prompt, re.M) or [None, "Target Role"])[1].strip()
        return ja.TailoredCV(
            headline=f"{title} | {cv['pillar']}",
            about_paragraphs=cv["about"],
            achievements_title=cv["achievements_title"],
            key_achievements=cv["achievements"],
            work_experience=[ja.WorkExperienceEntry(**entry) for entry in cv["experience"]],
            core_competencies=cv["competencies"],
        )
