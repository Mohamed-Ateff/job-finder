"""Read a CV (PDF, Word or text) into profile fields - on this computer, for free.

No AI and no online service: the text is pulled out of the file (pypdf / python-docx) and
sorted by the usual CV headings (Summary, Experience, Education, Skills, ...). CVs vary a
lot, so this is a head start, not the final word: the app shows everything it filled in
for the person to check and correct.
"""

from __future__ import annotations

import re
import unicodedata
from io import BytesIO

MAX_BYTES = 8 * 1024 * 1024
MAX_PAGES = 12
KINDS = {".pdf": "pdf", ".docx": "docx", ".txt": "txt", ".md": "txt"}

HEADINGS = {
    "summary": ["summary", "profile", "professional summary", "executive summary", "career summary", "about",
                "about me", "objective", "career objective", "executive profile", "personal profile",
                "professional profile", "overview", "personal statement", "الملخص", "نبذة", "نبذة عني",
                "الملخص المهني", "الهدف الوظيفي"],
    "experience": ["experience", "work experience", "professional experience", "employment history",
                   "work history", "career history", "relevant experience", "employment", "career",
                   "professional background", "الخبرات", "الخبرة", "الخبرة العملية", "الخبرات العملية",
                   "الخبرات المهنية"],
    "education": ["education", "academic background", "qualifications", "education and qualifications",
                  "education & qualifications", "academic qualifications", "academic history", "التعليم",
                  "المؤهلات", "المؤهلات العلمية", "المؤهل العلمي"],
    "skills": ["skills", "core competencies", "key skills", "technical skills", "competencies",
               "areas of expertise", "expertise", "core skills", "skills and competencies",
               "skills & competencies", "professional skills", "key competencies", "tools", "skills & tools",
               "المهارات", "المهارات الأساسية", "الكفاءات"],
    "certifications": ["certifications", "certificates", "licenses and certifications",
                       "licenses & certifications", "professional certifications", "courses",
                       "certifications and courses", "certifications & courses", "الشهادات",
                       "الشهادات المهنية", "الدورات"],
    "languages": ["languages", "language skills", "اللغات"],
    "achievements": ["achievements", "key achievements", "accomplishments", "highlights", "career highlights",
                     "selected achievements", "key accomplishments", "الإنجازات"],
    "training": ["training", "professional development", "trainings", "التدريب"],
    "awards": ["awards", "honors", "honours", "awards and recognition", "awards & recognition",
               "recognition", "الجوائز"],
    "ignore": ["references", "interests", "hobbies", "personal details", "personal information",
               "volunteering", "volunteer experience", "projects", "publications", "contact", "contact details",
               "additional information", "المعلومات الشخصية", "الهوايات"],
}
_HEADING_OF = {alias: section for section, aliases in HEADINGS.items() for alias in aliases}

MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
DATE = rf"(?:{MONTH}\s*\d{{4}}|\d{{1,2}}\s*/\s*\d{{4}}|\d{{4}})"
RANGE_RE = re.compile(
    rf"({DATE})\s*(?:-|–|—|to|until|till|→)\s*({DATE}|present|current|now|today|date|الآن|حتى الآن)", re.I)
YEAR_RE = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")
BULLET_RE = re.compile(r"^\s*(?:[•·▪◦●○■□➢➤►✓✔\-–*]|\d{1,2}[.)])\s*")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"(?<![\w/])(?:\+|00)?\d[\d \-().]{7,}\d(?![\w/])")
LINKEDIN_RE = re.compile(r"(?:https?://)?(?:[a-z]{2,3}\.)?linkedin\.com/in/[\w\-%.]+/?", re.I)
ROLE_WORDS = re.compile(
    r"\b(?:manager|director|head|lead|leader|engineer|analyst|specialist|officer|consultant|developer|"
    r"designer|accountant|coordinator|executive|president|owner|architect|administrator|supervisor|"
    r"assistant|intern|advisor|adviser|associate|partner|founder|chief|vp|cto|ceo|cfo|coo|cmo|editor|"
    r"writer|teacher|lecturer|professor|researcher|scientist|nurse|doctor|technician|representative|"
    r"agent|controller|auditor|planner|strategist|marketer|recruiter|translator|programmer)\b|مدير|رئيس|أخصائي|مهندس|محاسب",
    re.I)
DEGREE_WORDS = re.compile(
    r"\b(?:bachelor|master|mba|msc|m\.sc|bsc|b\.sc|ba|b\.a|ma|phd|ph\.d|doctorate|diploma|degree|"
    r"associate degree|high school|certificate)\b|بكالوريوس|ماجستير|دكتوراه|دبلوم", re.I)
SCHOOL_WORDS = re.compile(r"\b(?:university|college|institute|school|academy|faculty)\b|جامعة|كلية|معهد", re.I)
COUNTRY_WORDS = {
    "Saudi Arabia": ["saudi", "ksa", "riyadh", "jeddah", "dammam", "khobar", "mecca", "makkah", "medina",
                     "dhahran", "الرياض", "جدة", "الدمام", "السعودية"],
    "United Arab Emirates": ["united arab emirates", "uae", "dubai", "abu dhabi", "sharjah", "دبي", "الإمارات"],
    "Qatar": ["qatar", "doha", "قطر", "الدوحة"],
    "Kuwait": ["kuwait", "الكويت"],
    "Bahrain": ["bahrain", "manama", "البحرين"],
    "Oman": ["oman", "muscat", "عمان", "مسقط"],
    "Egypt": ["egypt", "cairo", "giza", "alexandria", "مصر", "القاهرة"],
}
CITIES = ["Riyadh", "Jeddah", "Dammam", "Khobar", "Dhahran", "Mecca", "Medina", "Dubai", "Abu Dhabi", "Sharjah",
          "Doha", "Kuwait City", "Manama", "Muscat", "Cairo", "Giza", "Alexandria"]
LEVEL_PATTERNS = (
    (re.compile(r"\b(?:chief|c[eotfm]o|vice\s+president|vp|svp|evp|general\s+manager|managing\s+director)\b", re.I), "executive"),
    (re.compile(r"\b(?:director|head)\b", re.I), "director"),
    (re.compile(r"\b(?:senior|sr\.?|lead|principal|manager)\b", re.I), "mid-senior"),
    (re.compile(r"\b(?:intern|trainee|graduate|junior|jr\.?)\b", re.I), "entry"),
)


class ImportError_(ValueError):
    """The file can't be read as a CV (wrong type, too big, scanned image, ...)."""


# ------------------------------------------------------------------- text --
def extract_text(filename: str, data: bytes) -> str:
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    kind = KINDS.get(ext)
    if not kind:
        raise ImportError_("Choose a PDF or Word (.docx) file.")
    if len(data) > MAX_BYTES:
        raise ImportError_("That file is larger than 8 MB.")
    if kind == "pdf":
        from pypdf import PdfReader

        try:
            reader = PdfReader(BytesIO(data))
            if reader.is_encrypted:
                reader.decrypt("")
            text = "\n".join((page.extract_text() or "") for page in reader.pages[:MAX_PAGES])
        except Exception as exc:  # noqa: BLE001 - any broken PDF gets the same answer
            raise ImportError_("This PDF couldn't be opened. Try saving it again, or use the Word file.") from exc
    elif kind == "docx":
        from docx import Document

        try:
            doc = Document(BytesIO(data))
        except Exception as exc:  # noqa: BLE001
            raise ImportError_("This Word file couldn't be opened.") from exc
        # Word keeps bullets in the paragraph style, not the text: put the mark back.
        lines = [("• " if (p.style is not None and p.style.name.lower().startswith("list")) else "") + p.text
                 for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                cells = list(dict.fromkeys(c.text.strip() for c in row.cells if c.text.strip()))
                lines.extend(cells)
        text = "\n".join(lines)
    else:
        text = data.decode("utf-8", errors="replace")
    # NFKC turns PDF ligatures ("ﬁ") and Arabic presentation forms back into plain letters.
    text = unicodedata.normalize("NFKC", text.replace("\r", "\n").replace(" ", " "))
    if len(re.sub(r"\s", "", text)) < 80:
        raise ImportError_("No text was found in this file. If it's a scanned image, use the Word or text version.")
    return text


# ------------------------------------------------------------------ parse --
def _norm(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip()


def _heading(line: str) -> str | None:
    text = _norm(line).rstrip(":：").strip().lower()
    text = re.sub(r"^[^\w؀-ۿ]+|[^\w؀-ۿ)]+$", "", text)
    if not text or len(text) > 42:
        return None
    return _HEADING_OF.get(text)


def _is_bullet(line: str) -> bool:
    return bool(BULLET_RE.match(line)) and not RANGE_RE.match(line.strip())


def _strip_bullet(line: str) -> str:
    return _norm(BULLET_RE.sub("", line, count=1))


def _split_list(lines: list[str]) -> list[str]:
    items: list[str] = []
    for line in lines:
        for part in re.split(r"\s*(?:[•·|▪●;]|,(?![^()]*\)))\s*", _strip_bullet(line)):
            part = part.strip(" .")
            if 1 < len(part) <= 60 and part.lower() not in {i.lower() for i in items}:
                items.append(part)
    return items[:40]


def _bullets(lines: list[str]) -> list[str]:
    """Bullet points, joining the lines a PDF wrapped back onto their bullet: a line that
    starts in lower case, or follows a full-width line that didn't end its sentence."""
    out: list[str] = []
    last_raw = ""
    for line in lines:
        text = _norm(line)
        if not text:
            continue
        wrapped = out and (text[0].islower() or (len(last_raw) > 70 and not last_raw.endswith((".", ":", ";"))))
        if _is_bullet(line) or not wrapped:
            out.append(_strip_bullet(line))
        else:
            out[-1] = f"{out[-1]} {text}"
        last_raw = text
    return [b for b in out if len(b) > 2]


def _is_place(text: str) -> bool:
    low = text.lower().strip()
    return low in {c.lower() for c in CITIES} or any(low == w for words in COUNTRY_WORDS.values() for w in words)


def _paragraphs(lines: list[str]) -> list[str]:
    paras, current = [], []
    for line in lines:
        if not _norm(line):
            if current:
                paras.append(" ".join(current))
                current = []
        else:
            current.append(_strip_bullet(line) if _is_bullet(line) else _norm(line))
    if current:
        paras.append(" ".join(current))
    return [p for p in paras if len(p) > 20][:3]


def _sections(lines: list[str]) -> tuple[list[str], dict[str, list[str]]]:
    head: list[str] = []
    found: dict[str, list[str]] = {}
    current = None
    for line in lines:
        section = _heading(line)
        if section:
            current = section
            found.setdefault(section, [])
            continue
        (found[current] if current else head).append(line)
    return head, found


def _split_header(text: str) -> list[str]:
    parts = re.split(r"\s+(?:\||—|–|-|@|at)\s+|\s*[|,]\s*", text)
    return [p.strip(" ,|-–—") for p in parts if p.strip(" ,|-–—")]


def _period(text: str) -> str:
    period = re.sub(r"\s*(?:-|–|—|to|until|till|→)\s*", " – ", _norm(text), count=1)
    return re.sub(r"\b(present|current|now|today)\b", lambda m: m.group(1).title(), period, flags=re.I)


def _experience(lines: list[str]) -> list[dict]:
    """Each role is anchored on the line with its dates ("Jan 2019 – Present"). The title and
    company are on that line or the one or two lines above it (or, failing that, the line below);
    everything after it, up to the next role, is its description and bullets."""
    items = [(_norm(line), _is_bullet(line)) for line in lines if _norm(line)]
    heads = []                              # (date line, first line of this role, header bits, period)
    previous = -1
    for i, (text, bullet) in enumerate(items):
        match = None if bullet else RANGE_RE.search(text)
        if not match:
            continue
        rest = _norm(text[: match.start()] + " " + text[match.end():]).strip(" ,|-–—()")
        bits = _split_header(rest) if rest else []
        has_role = any(ROLE_WORDS.search(b) for b in bits)
        # Enough on the dates line itself? Otherwise the title (and company) are just above it.
        want = 0 if has_role and len(bits) >= 2 else 1 if has_role or len(bits) >= 2 else 2
        above: list[str] = []
        j = i - 1
        while (j > previous and len(above) < want and not items[j][1] and len(items[j][0]) < 90
               and not items[j][0].endswith(".") and not RANGE_RE.search(items[j][0])):
            above.insert(0, items[j][0])
            j -= 1
        heads.append((i, i - len(above), [b for a in above for b in _split_header(a)] + bits, _period(match.group(0))))
        previous = i

    entries = []
    for n, (i, _, bits, period) in enumerate(heads):
        end = heads[n + 1][1] if n + 1 < len(heads) else len(items)
        body = items[i + 1:end]
        if not bits and body and not body[0][1]:
            bits, body = _split_header(body[0][0]), body[1:]
        title = next((b for b in bits if ROLE_WORDS.search(b)), bits[0] if bits else "")
        company = next((b for b in bits if b != title and not _is_place(b)), "")
        first_bullet = next((k for k, (_, bullet) in enumerate(body) if bullet), None)
        if first_bullet is not None:
            description = " ".join(t for t, _ in body[:first_bullet])
            bullets = _bullets([t for t, _ in body[first_bullet:]])
        else:
            # No bullet marks survived (common in PDFs): every line is a point.
            description, bullets = "", _bullets([t for t, _ in body])
        entries.append({"role_title": title[:160], "company": company[:160], "period": period,
                        "role_description": description[:400], "bullets": bullets[:12]})
    return [e for e in entries if e["role_title"] or e["company"]][:15]


def _education(lines: list[str]) -> list[dict]:
    entries: list[dict] = []
    for raw in lines:
        line = _strip_bullet(raw) if _is_bullet(raw) else _norm(raw)
        if not line:
            continue
        year = YEAR_RE.findall(line)
        is_degree, is_school = bool(DEGREE_WORDS.search(line)), bool(SCHOOL_WORDS.search(line))
        if is_degree and is_school:
            parts = _split_header(RANGE_RE.sub("", line))
            credential = next((p for p in parts if DEGREE_WORDS.search(p)), parts[0] if parts else line)
            institution = next((p for p in parts if SCHOOL_WORDS.search(p) and p != credential), "")
            entries.append({"credential": credential, "institution": institution, "detail": year[-1] if year else ""})
        elif is_degree or not entries:
            entries.append({"credential": RANGE_RE.sub("", line).strip(" ,|-–—"), "institution": "",
                            "detail": year[-1] if year else ""})
        elif is_school and not entries[-1]["institution"]:
            entries[-1]["institution"] = RANGE_RE.sub("", line).strip(" ,|-–—")
            if year and not entries[-1]["detail"]:
                entries[-1]["detail"] = year[-1]
        elif year and not entries[-1]["detail"] and len(line) < 30:
            entries[-1]["detail"] = year[-1]
    return [e for e in entries if e["credential"] or e["institution"]][:8]


def _name(head: list[str]) -> str:
    for raw in head[:8]:
        line = _norm(raw)
        if (not line or EMAIL_RE.search(line) or PHONE_RE.search(line) or LINKEDIN_RE.search(line)
                or _heading(line) or len(line) > 50 or re.search(r"\d", line)):
            continue
        words = line.split()
        if 1 < len(words) <= 5 and all(re.match(r"^[^\W\d_][\w.'\-]*$", w) for w in words):
            return line.title() if line.isupper() else line
    return ""


def _headline(head: list[str], name: str) -> str:
    seen_name = not name
    for raw in head[:10]:
        line = _norm(raw)
        if not line:
            continue
        if not seen_name:
            seen_name = line == name or line.lower() == name.lower()
            continue
        if EMAIL_RE.search(line) or PHONE_RE.search(line) or LINKEDIN_RE.search(line) or len(line) > 90:
            continue
        if ROLE_WORDS.search(line) or "|" in line:
            return line.strip(" |")
    return ""


def _country(text: str) -> tuple[str, str]:
    low = text.lower()
    city = next((c for c in CITIES if c.lower() in low), "")
    best, at = "", len(low) + 1
    for country, words in COUNTRY_WORDS.items():
        for word in words:
            pos = low.find(word)
            if 0 <= pos < at:
                best, at = country, pos
    return city, best


def _levels(titles: list[str]) -> list[str]:
    found = []
    for title in titles[:3]:
        level = next((lv for rx, lv in LEVEL_PATTERNS if rx.search(title)), None)
        if level and level not in found:
            found.append(level)
    order = ["entry", "associate", "mid-senior", "director", "executive"]
    return sorted(found, key=order.index) or ["mid-senior"]


def parse(text: str) -> dict:
    """CV text -> {'fields': partial profile, 'found': which parts were filled in}."""
    lines = text.split("\n")
    head, sections = _sections(lines)
    contact_zone = "\n".join(head[:25]) + "\n" + "\n".join(lines[:40])

    email = (EMAIL_RE.search(contact_zone) or EMAIL_RE.search(text))
    phone = PHONE_RE.search(contact_zone)
    linkedin = LINKEDIN_RE.search(text)
    name = _name(head or lines)
    headline = _headline(head or lines, name)
    city, country = _country(contact_zone)

    experience = _experience(sections.get("experience", []))
    titles = [e["role_title"] for e in experience if e["role_title"]]
    summary = _paragraphs(sections.get("summary", []))
    if not summary:
        # Many CVs open with a profile paragraph and no heading: the first long lines after the contact block.
        long_lines = [_norm(x) for x in head if len(_norm(x)) > 120]
        summary = long_lines[:2]
    skills = _split_list(sections.get("skills", []))
    cv = {
        "summary": summary,
        "achievements": _bullets(sections.get("achievements", []))[:12],
        "experience": experience,
        "skills": skills,
        "education": _education(sections.get("education", [])),
        "certifications": _bullets(sections.get("certifications", []))[:30],
        "languages": _split_list(sections.get("languages", []))[:8],
        "training": _bullets(sections.get("training", []))[:15],
        "awards": _bullets(sections.get("awards", []))[:10],
    }
    search_titles = []
    for t in [headline.split("|")[0].strip() if headline else "", *titles[:2]]:
        t = re.sub(r"\s*[,(].*$", "", t).strip()
        if t and len(t) <= 60 and ROLE_WORDS.search(t) and t.lower() not in {s.lower() for s in search_titles}:
            search_titles.append(t)
    fields = {
        "name": name,
        "headline": headline,
        "email": email.group(0) if email else "",
        "phone": _norm(phone.group(0)) if phone else "",
        "linkedin": re.sub(r"^https?://(www\.)?", "", linkedin.group(0)).rstrip("/") if linkedin else "",
        "city": city,
        "search": {"titles": search_titles, "levels": _levels([headline, *titles])},
        "cv": cv,
    }
    if country:
        fields["search"]["country"] = country
    found = [k for k in ("name", "headline", "email", "phone", "linkedin", "city") if fields[k]]
    found += [k for k, v in cv.items() if v]
    if search_titles:
        found.append("titles")
    return {"fields": fields, "found": found}


def merge(profile: dict, fields: dict) -> dict:
    """Fill a profile from imported fields: whatever the CV provides replaces what was there;
    whatever it doesn't provide is kept."""
    out = {**profile, "search": dict(profile["search"]), "cv": dict(profile["cv"])}
    for key in ("name", "headline", "email", "phone", "linkedin", "city"):
        if fields.get(key):
            out[key] = fields[key]
    for key, value in (fields.get("search") or {}).items():
        if value:
            out["search"][key] = value
    for key, value in (fields.get("cv") or {}).items():
        if value:
            out["cv"][key] = value
    return out
