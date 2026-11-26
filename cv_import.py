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
MAX_PAGES = 60                          # a CV plus a discovery record runs to 30 pages
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
# A heading in capitals that isn't one of the usual ones ("PRODUCT LEADERSHIP STRENGTHS", "SELECTED
# CERTIFICATIONS AND PROFESSIONAL DEVELOPMENT", "TOOLS AND METHODS") goes by its key word. First match wins.
FUZZY_HEADINGS = (
    ("certifications", r"certific|licen[cs]es?\b|courses\b"),
    ("experience", r"experience\b|employment\b|work history|career history"),
    ("education", r"education\b|qualifications?\b|academic\b"),
    ("skills", r"strengths\b|competenc|skills\b|expertise\b|tools\b|technologies\b"),
    ("languages", r"languages\b"),
    ("awards", r"awards?\b|honou?rs\b"),
    ("achievements", r"achievements\b|accomplishments\b"),
    ("training", r"training\b|professional development"),
    ("summary", r"summary\b|profile\b|objective\b"),
)
SMALL_WORDS = {"AND", "OF", "THE", "FOR", "IN", "TO", "AT", "ON", "A", "AN", "WITH", "BY"}
GROUP_RE = re.compile(r"^[A-Z][\w &/+.\-]{1,40}:\s+\S")         # "Styling & UI: Tailwind CSS, Sass"
SITE_RE = re.compile(r"(?<![@\w.])((?:https?://)?(?:www\.)?[a-z0-9-]+\.(?:dev|io|me|com|net|org|app|site|tech|co|ai)"
                     r"(?:/[\w\-./]*)?)(?![\w@])", re.I)
ABBREVIATIONS = ("Co.", "Inc.", "Ltd.", "Corp.", "Bros.", "Jr.", "Sr.", "S.A.", "L.L.C.")

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
def _page_by_position(page, plain: str) -> str:
    """A page's text in the order it reads on the page: top to bottom, and left to right along each line.
    Design tools (Canva and the like) store text in any order - a job's dates after its points - so the
    stored order can pin the wrong dates on every job. Pieces split mid-word are joined back the way the
    stored text has them; a wide gap on a line (a date pushed to the right margin) becomes three spaces."""
    import math

    pieces = []

    def visit(text, cm, tm, font, size):
        if not text or not text.strip() or not size:
            return
        a, b = tm[0] * cm[0] + tm[1] * cm[2], tm[0] * cm[1] + tm[1] * cm[3]
        c, d = tm[2] * cm[0] + tm[3] * cm[2], tm[2] * cm[1] + tm[3] * cm[3]
        x, y = tm[4] * cm[0] + tm[5] * cm[2] + cm[4], tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
        pieces.append((x, y, size * (math.hypot(c, d) or 1), size * (math.hypot(a, b) or 1), d, text.replace("\n", " ")))

    page.extract_text(visitor_text=visit)
    if not pieces:
        return ""
    down = -1 if sum(1 if p[4] >= 0 else -1 for p in pieces) >= 0 else 1      # flipped pages read with +y
    compact = re.sub(r"\s+", " ", plain)
    lines: list[list[tuple]] = []
    for p in sorted(pieces, key=lambda p: (down * p[1], p[0])):
        if lines and abs(p[1] - lines[-1][0][1]) < 0.5 * max(p[2], lines[-1][0][2]):
            lines[-1].append(p)
        else:
            lines.append([p])
    out = []
    for line in lines:
        text = ""
        last = None
        for p in sorted(line, key=lambda q: q[0]):
            piece = p[5]
            if last is None:
                text = piece
            else:
                gap = p[0] - (last[0] + 0.5 * last[3] * len(last[5]))     # roughly where the last piece ended
                joined = text.rstrip()[-20:] + piece.lstrip()[:20]
                if joined in compact:
                    text = text.rstrip() + piece.lstrip()
                elif gap > 2.5 * last[3]:
                    text = text.rstrip() + "   " + piece.lstrip()
                else:
                    text = text.rstrip() + " " + piece.lstrip()
            last = p
        out.append(text)
    return "\n".join(out)


def extract_texts(filename: str, data: bytes) -> list[str]:
    """The file's text, and for a PDF also its text in page order (see _page_by_position): read_document
    keeps whichever reads as the cleaner CV."""
    text = extract_text(filename, data)
    if not filename.lower().endswith(".pdf"):
        return [text]
    try:
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            reader.decrypt("")
        pages = [_page_by_position(p, p.extract_text() or "") for p in reader.pages[:MAX_PAGES]]
        positioned = unicodedata.normalize("NFKC", "\n".join(pages).replace(" ", " "))
        links = _links(reader)
    except Exception:  # noqa: BLE001 - the stored order still works
        return [text]
    texts = [text, positioned] if len(re.sub(r"\s", "", positioned)) >= 80 else [text]
    if links:
        # A CV that shows only "linkedin" or "portfolio" keeps the real addresses in its links:
        # they go under the first line (the name), where the contact details are read.
        texts = [t.split("\n", 1)[0] + "\n" + "  ".join(links) + "\n" + (t.split("\n", 1)[1] if "\n" in t else "")
                 for t in texts]
    return texts


def _links(reader) -> list[str]:
    """Web addresses behind the CV's links (LinkedIn, portfolio): not email links, at most a few."""
    out = []
    for page in reader.pages[:2]:
        for annot in page.get("/Annots") or []:
            try:
                uri = str(annot.get_object().get("/A", {}).get("/URI", "")).strip()
            except Exception:  # noqa: BLE001
                continue
            if uri.lower().startswith(("http://", "https://")) and uri not in out:
                out.append(uri)
    return out[:6]


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
        from docx.table import Table
        from docx.text.paragraph import Paragraph

        # Paragraphs and tables in the order they come (a table's rows belong to the heading above it).
        # Word keeps bullets in the paragraph style, not the text: put the mark back.
        lines = []
        for child in doc.element.body.iterchildren():
            kind = child.tag.rsplit("}", 1)[-1]
            if kind == "p":
                p = Paragraph(child, doc)
                lines.append(("• " if (p.style is not None and p.style.name.lower().startswith("list")) else "") + p.text)
            elif kind == "tbl":
                for row in Table(child, doc).rows:
                    lines.extend(dict.fromkeys(c.text.strip() for c in row.cells if c.text.strip()))
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


def _capitals(text: str) -> bool:
    return bool(re.search(r"[A-Z]", text)) and text == text.upper()


def _tidy(text: str) -> str:
    """'ARGAAM INVESTMENT' -> 'Argaam Investment'; short capitals stay ('AI', 'IBM'); text not in capitals is left alone."""
    if not _capitals(text) or len(text) <= 4:
        return text
    words = text.split()
    out = []
    for n, w in enumerate(words):
        if n and w in SMALL_WORDS:
            out.append(w.lower())
        elif len(re.sub(r"\W", "", w)) <= 3 and w.isalpha() and w not in SMALL_WORDS:
            out.append(w)
        else:
            out.append(w.capitalize())
    return " ".join(out)


def _subhead(text: str) -> bool:
    """A short line in capitals inside a role ('DELIVERED PRODUCT ENHANCEMENTS'): a label, not a point."""
    return _capitals(text) and len(text.split()) <= 7 and "|" not in text and not re.search(r"\d", text)


def _heading(line: str) -> str | None:
    raw = _norm(line).rstrip(":：").strip()
    text = re.sub(r"^[^\w؀-ۿ]+|[^\w؀-ۿ)]+$", "", raw.lower())
    if not text:
        return None
    if len(text) <= 42 and text in _HEADING_OF:
        return _HEADING_OF[text]
    if len(text) <= 60 and _subhead(raw):
        return next((section for section, rx in FUZZY_HEADINGS if re.search(rx, text)), None)
    return None


def _is_bullet(line: str) -> bool:
    return bool(BULLET_RE.match(line)) and not RANGE_RE.match(line.strip())


def _strip_bullet(line: str) -> str:
    return _norm(BULLET_RE.sub("", line, count=1))


def _split_list(lines: list[str]) -> list[str]:
    items: list[str] = []
    lines = [line for line in lines if not re.fullmatch(r"\s*\d{1,3}\s*", line)]     # page numbers
    # Skills in groups ("Frameworks & Libraries: React, Next.js"): each group stays one line, as written.
    text_lines = [_strip_bullet(line) for line in lines if _norm(line)]
    grouped = [line for line in text_lines if GROUP_RE.match(line)]
    if len(grouped) >= 2 and len(grouped) * 2 >= len(text_lines):
        return list(dict.fromkeys(re.sub(r"\s*:\s*", ": ", line, count=1).strip(" .") for line in grouped))[:20]
    # "A  •  B  •  Product Requirements and" + "Acceptance Criteria  •  C": items run on across lines.
    # A blank line (between two sections of the same kind) still ends an item.
    if any(re.search(r"\S\s*[•·▪●]\s*\S", _strip_bullet(line)) for line in lines):
        groups, current = [], []
        for line in lines + [""]:
            if _norm(line):
                current.append(_strip_bullet(line))
            elif current:
                groups.append(" ".join(current))
                current = []
        lines = groups
    for line in lines:
        for part in re.split(r"\s*(?:[•·|▪●;]|,(?![^()]*\)))\s*", _strip_bullet(line)):
            part = re.sub(r"\(\s+", "(", re.sub(r"\s+\)", ")", part)).strip(" .")
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
    seen: set[str] = set()
    unique = []
    for b in out:                           # a point repeated in the CV is kept once
        if len(b) > 2 and b.lower() not in seen:
            seen.add(b.lower())
            unique.append(b)
    return unique


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
            found.setdefault(section, []).append("")      # a second "skills" heading starts a new run
            continue
        (found[current] if current else head).append(line)
    return head, found


def _split_header(text: str) -> list[str]:
    # "COMPANY | site | Marketing, Digital Marketing & E-Commerce Manager": the bars are the separators,
    # and the commas belong to the parts.
    parts = text.split("|") if "|" in text else re.split(r"\s+(?:—|–|-|@|at)\s+|\s*,\s*", text)
    out = []
    for p in parts:
        p = p.strip(" ,|-–—")
        if p.endswith(".") and not p.endswith(ABBREVIATIONS):     # "Deep Business Partners Co." keeps its dot
            p = p.rstrip(". ")
        if p:
            out.append(p)
    return out


def _title_and_company(bits: list[str]) -> tuple[str, str]:
    names = [b for b in bits if not _is_place(b) and not re.fullmatch(r"(?:www\.)?[\w-]+(?:\.[\w-]+)+/?", b)]
    title = next((b for b in names if ROLE_WORDS.search(b)), "")
    if not title and len(names) >= 2 and _capitals(names[0]) and not _capitals(names[-1]):
        title = names[-1]                   # "MUBASHER INTERNATIONAL GROUP | ... | Product, Project & Management Roles"
    title = title or (names[0] if names else "")
    company = next((b for b in names if b != title), "")
    if _capitals(company) and re.search(r"\b(?:career|experience|roles?)\b", company, re.I):
        company = ""                        # "EARLIER CAREER | ...": a label, not an employer
    return _tidy(title), _tidy(company)


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
        before, after = text[: match.start()], text[match.end():]
        if re.match(r"\s*[•·▪]", after):
            after = ""                      # "Sep 2018 – Present • Financial data, Riyadh": the sector and place
        rest = _norm(before + " " + after).strip(" ,|-–—()•·")
        bits = _split_header(rest) if rest else []
        has_role = any(ROLE_WORDS.search(b) for b in bits)
        # Enough on the dates line itself? Otherwise the title (and company) are just above it.
        want = 0 if has_role and len(bits) >= 2 else 1 if has_role or len(bits) >= 2 else 2
        above: list[str] = []
        j = i - 1
        while (j > previous and len(above) < want and not items[j][1]
               and len(items[j][0]) < (120 if "|" in items[j][0] else 90)
               and not items[j][0].endswith(".") and not RANGE_RE.search(items[j][0])):
            above.insert(0, items[j][0])
            j -= 1
        first = i - len(above)                 # where this role starts
        if len(above) == 2 and "|" in above[0] and "|" not in above[1] and len(above[1].split()) <= 3:
            above = [f"{above[0]} {above[1]}"]   # a long "COMPANY | site | Title" line that wrapped
        heads.append((i, first, [b for a in above for b in _split_header(a)] + bits, _period(match.group(0))))
        previous = i

    entries = []
    for n, (i, _, bits, period) in enumerate(heads):
        end = heads[n + 1][1] if n + 1 < len(heads) else len(items)
        body = items[i + 1:end]
        if not bits and body and not body[0][1]:
            bits, body = _split_header(body[0][0]), body[1:]
        body = [(t, b) for t, b in body if b or not _subhead(t)]     # no in-role labels ("CURRENT INITIATIVES")
        title, company = _title_and_company(bits)
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
        years = YEAR_RE.findall(line)
        span = RANGE_RE.search(line)
        year = [_period(span.group(0))] if span else years       # "2023 – Present" stays: still studying
        is_degree, is_school = bool(DEGREE_WORDS.search(line)), bool(SCHOOL_WORDS.search(line))
        if is_degree and is_school:
            parts = _split_header(RANGE_RE.sub("", line))
            credential = next((p for p in parts if DEGREE_WORDS.search(p)), parts[0] if parts else line)
            schools = [p for p in parts if SCHOOL_WORDS.search(p) and p != credential]
            # "… | Faculty of Arts | Cairo University": the university, not its faculty.
            institution = next((p for p in schools if re.search(r"universit|college|institute|جامعة", p, re.I)),
                               schools[0] if schools else "")
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
            return _tidy(line.strip(" |"))
    return ""


def _country(text: str) -> tuple[str, str]:
    low = text.lower()
    # The city named first (the contact line), not one a later point mentions ("for audiences in Dubai").
    found = [(low.find(c.lower()), c) for c in CITIES if c.lower() in low]
    city = min(found)[1] if found else ""
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
    # The contact lines first; the first lines of the file only when they name no place.
    city, country = _country("\n".join(head[:25])) if head else ("", "")
    if not (city or country):
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
    # A portfolio or personal site in the contact lines ("mohamedatef.dev"), never LinkedIn or a company.
    site = next((m.group(1) for m in SITE_RE.finditer("\n".join((head or lines)[:12]))
                 if "linkedin" not in m.group(1).lower()), "")
    fields["website"] = re.sub(r"^https?://(?:www\.)?", "", site).rstrip("/")
    # "Riyadh, Saudi Arabia • Egyptian nationality • …" or "Nationality: Saudi"
    nat = re.search(r"\b([A-Z][a-z]+)\s+nationality\b|\bnationality\s*[:\-]\s*([A-Z][a-z]+)", contact_zone, re.I)
    fields["nationality"] = (nat.group(1) or nat.group(2)).capitalize() if nat else ""
    years = re.search(r"\b(\d{1,2})(\+?)\s*-?\s*(?:years?|yrs)\b", " ".join(summary))
    fields["preferences"] = {"years": years.group(1) + years.group(2)} if years else {}
    found = [k for k in ("name", "headline", "email", "phone", "linkedin", "website", "city", "nationality") if fields[k]]
    found += [k for k, v in cv.items() if v]
    if search_titles:
        found.append("titles")
    return {"fields": fields, "found": found}


JUNK_RE = re.compile(r"[✉☎⚲📞📧🔗📍☏✆]|@[\w-]+\.\w|(?:\+|00)\d[\d \-]{7,}\d|https?://|www\.", re.I)


def quality(result: dict) -> int:
    """How cleanly a CV was read: whole roles (title, company and dates) count; contact details read
    as a role, and dates or sentences read as skills, count against."""
    cv = result["fields"].get("cv") or {}
    exp = cv.get("experience") or []
    whole = sum(1 for e in exp if e["role_title"] and e["company"] and e["period"])
    junk = sum(1 for e in exp if JUNK_RE.search(" ".join([e["role_title"], e["company"], *e["bullets"]])))
    bad_skills = sum(1 for s in cv.get("skills") or [] if RANGE_RE.search(s) or ROLE_WORDS.search(s) and "," not in s
                     and len(s.split()) <= 5 and not re.search(r"[:&]", s) or len(s.split()) > 8)
    return 4 * whole + len(exp) - 10 * junk - bad_skills + len(cv.get("education") or [])


def read_document(text: str, alternatives: list[str] | tuple = ()) -> dict:
    """A file's text -> {'fields', 'found', 'source'}: a CV, a Career Discovery record (discovery_record.py),
    or a CV followed by its record. The CV gives the CV facts; the record gives what the person is looking
    for (roles, sectors, nationality, how and where they'll work), which comes first for the search.
    `alternatives`: the same file read another way (a PDF in page order); the cleaner CV reading wins."""
    import discovery_record

    cv_text, record = discovery_record.split(text)
    has_cv = len(re.sub(r"\s", "", cv_text)) >= 80
    result = parse(cv_text) if has_cv else {"fields": {"search": {}, "cv": {}}, "found": []}
    if has_cv:
        for other in alternatives:
            other_cv = discovery_record.split(other)[0]
            if len(re.sub(r"\s", "", other_cv)) >= 80:
                candidate = parse(other_cv)
                if quality(candidate) > quality(result):
                    result = candidate
    if record is None:
        return {**result, "source": "cv"}
    f, r = result["fields"], discovery_record.parse(record)
    rf = r["fields"]
    f["name"] = f.get("name") or rf["name"]
    f["nationality"] = rf["nationality"] or f.get("nationality", "")
    if rf["search"]["titles"]:
        f["search"]["titles"] = rf["search"]["titles"]
        f["search"]["levels"] = _levels(rf["search"]["titles"])
    if rf["search"]["keywords"]:
        f["search"]["keywords"] = rf["search"]["keywords"]
    f["cv"]["languages"] = f["cv"].get("languages") or rf["cv"]["languages"]
    f["preferences"] = {**(f.get("preferences") or {}), **{k: v for k, v in rf["preferences"].items() if v}}
    found = list(dict.fromkeys(result["found"] + r["found"]))
    return {"fields": f, "found": found, "source": "cv+record" if has_cv else "record"}


def merge(profile: dict, fields: dict) -> dict:
    """Fill a profile from imported fields (a CV's, or a questionnaire's): whatever the file
    provides replaces what was there; whatever it doesn't provide is kept."""
    out = {**profile, **{group: dict(profile.get(group) or {}) for group in ("search", "cv", "preferences")}}
    for key in ("name", "headline", "email", "phone", "linkedin", "website", "city", "nationality"):
        if fields.get(key):
            out[key] = fields[key]
    for group in ("search", "cv", "preferences"):
        for key, value in (fields.get(group) or {}).items():
            if value:
                out[group][key] = value
    return out
