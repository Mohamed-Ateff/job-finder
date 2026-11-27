"""Applying faster: what the web app hands the person for one job.

- answers: what application forms ask for (name, email, phone, LinkedIn, notice, salary...), each
  ready to copy, and the same values for the one-click "Fill form" bookmark;
- a short cover note for this job, from the person's own summary and the CV points that match
  the posting best;
- for postings that take CVs by email, the subject line to use.

Only the person's own profile and their approved CV facts are used (the CV passed in has already
been through the disclosure guard). Nothing is sent anywhere: the person reads, edits and pastes it.
"""

from __future__ import annotations

import re

import basic_ai


def _url(value: str) -> str:
    value = (value or "").strip()
    return value if not value or value.startswith(("http://", "https://")) else f"https://{value}"


def _split_name(name: str) -> tuple[str, str]:
    parts = (name or "").split()
    if len(parts) < 2:
        return (parts[0] if parts else ""), ""
    return parts[0], " ".join(parts[1:])


def _education(item) -> str:
    if isinstance(item, dict):
        return ", ".join(x for x in (item.get("credential", ""), item.get("institution", "")) if x)
    return str(item or "")


def _get(item, key: str) -> str:
    """One field of a CV entry, whether it's the CV writer's object or a profile dict."""
    value = item.get(key, "") if isinstance(item, dict) else getattr(item, key, "")
    return str(value or "").strip()


def answers(profile: dict, cv=None) -> list[dict]:
    """[{key, label, value}] for every answer the profile has, in the order forms usually ask."""
    prefs = profile.get("preferences") or {}
    facts = profile.get("cv") or {}
    experience = list(getattr(cv, "work_experience", None) or facts.get("experience") or [])
    latest = experience[0] if experience else {}
    first, last = _split_name(profile.get("name", ""))
    education = next((_education(e) for e in facts.get("education") or [] if _education(e)), "")
    languages = ", ".join(str(x.get("language", x)) if isinstance(x, dict) else str(x)
                          for x in facts.get("languages") or [] if x)
    rows = [
        ("name", "Full name", profile.get("name", "")),
        ("first", "First name", first),
        ("last", "Last name", last),
        ("email", "Email", profile.get("email", "")),
        ("phone", "Phone", profile.get("phone", "")),
        ("city", "City", profile.get("city", "")),
        ("nationality", "Nationality", profile.get("nationality", "")),
        ("linkedin", "LinkedIn", _url(profile.get("linkedin", ""))),
        ("website", "Website", _url(profile.get("website", ""))),
        ("title", "Current title", profile.get("headline") or _get(latest, "role_title")),
        ("company", "Most recent employer", _get(latest, "company")),
        ("years", "Years of experience", prefs.get("years", "")),
        ("notice", "Notice period", prefs.get("notice", "")),
        ("salary", "Expected salary", prefs.get("salary", "")),
        ("visa", "Residency / visa", prefs.get("visa", "")),
        ("relocate", "Relocation", prefs.get("relocate", "")),
        ("languages", "Languages", languages),
        ("education", "Education", education),
    ]
    return [{"key": k, "label": label, "value": str(v).strip()} for k, label, v in rows if str(v or "").strip()]


def _sentences(text: str, limit: int = 320) -> str:
    """The first sentences of a paragraph, up to about the limit, cut at a sentence end."""
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    return cut[: end + 1] if end > 80 else cut.rsplit(" ", 1)[0] + "…"


def best_points(cv, job: dict, most: int = 3) -> list[str]:
    """The person's own CV points that match this posting best (ties keep the CV's order),
    each with the employer it was done at."""
    title = (job.get("title") or "").strip()
    weights = basic_ai._weights(f"{title}\n{title}\n{title}\n{job.get('description') or ''}")
    found: list[tuple[str, str]] = [(str(p), "") for p in getattr(cv, "key_achievements", None) or []]
    for entry in getattr(cv, "work_experience", None) or []:
        bullets = entry.get("bullets") if isinstance(entry, dict) else getattr(entry, "bullets", None)
        found += [(str(b), _get(entry, "company")) for b in bullets or []]

    def score(point: str) -> int:
        stems = {w[:7] for w in re.findall(r"[a-z]{4,}", point.lower()) if w not in basic_ai.FILLER}
        return sum(weights.get(s, 0) for s in stems) + (2 if re.search(r"\d", point) else 0)   # results count

    ranked = sorted(enumerate(found), key=lambda x: (-score(x[1][0]), x[0]))
    out, used = [], set()
    for _, (point, company) in ranked:
        text = re.sub(r"\s+", " ", point).strip().rstrip(".;")
        if not text or text.lower() in used:
            continue
        used.add(text.lower())
        out.append(f"{text} ({company})" if company else text)
        if len(out) == most:
            break
    return out


def cover_note(profile: dict, job: dict, cv) -> str:
    """A short, plain cover note: who the person is in their own words, three matching points
    from their CV, and their contact details. Meant to be read and adjusted before sending."""
    title = basic_ai._clean_title(re.sub(r"\s+", " ", job.get("title") or "").strip()) or "this role"
    company = (job.get("company") or "").split("|")[0].strip()
    about = next((p for p in getattr(cv, "about_paragraphs", None) or [] if p and p.strip()), "")
    lines = [f"Dear {company} Hiring Team," if company else "Dear Hiring Manager,", ""]
    opening = f"I am applying for the {title} position{f' at {company}' if company else ''}."
    lines.append(f"{opening} {_sentences(about)}" if about else opening)
    points = best_points(cv, job)
    if points:
        lines += ["", "A few things from my experience that match this role:"]
        lines += [f"- {p}" for p in points]
    lines += ["", f"My CV is attached. I would welcome the chance to discuss how I can contribute to "
                  f"{company or 'your team'}.", "", "Kind regards,", profile.get("name", "")]
    lines += [x for x in (profile.get("phone", ""), profile.get("email", ""), _url(profile.get("linkedin", ""))) if x]
    return "\n".join(lines).strip() + "\n"


def email_subject(profile: dict, job: dict) -> str:
    title = basic_ai._clean_title(re.sub(r"\s+", " ", job.get("title") or "").strip()) or "the open position"
    return f"Application for {title} - {profile.get('name', '')}".strip(" -")
