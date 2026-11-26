"""Read a Career Discovery record (the Phase 1 "Career Discovery Output", in Arabic) for the search.

A person's file can be their CV followed by their discovery record, or the record alone (PDF or
Word). The CV part is read by cv_import as usual; this module reads the record's search facts:
the roles they want (in order), the sectors they prefer, nationality and languages, how and where
they will work, the lowest salary, notice period and residency. Everything else in the record
(achievements and their evidence, team sizes, clients, interview stories, disclosure rules) is
left out on purpose: it is not needed to find jobs, and much of it must never reach a CV.

PDF text from Arabic often loses the spaces between words, so labels are matched with the spaces
taken out, and Arabic answers are turned into short English ones (the profile and the search are
in English). No AI and no online service.
"""

from __future__ import annotations

import re

MARKER = "Career Discovery Output"
AR = "؀-ۿ"
ROLE = re.compile(r"\b(?:Director|Lead|Manager|Head|Owner|Officer|Chief|President|VP|Consultant|Specialist|Analyst|"
                  r"Engineer|Architect|Strategist|Advisor|Coordinator|Executive|Partner)\b")
LATIN_PHRASE = re.compile(r"[A-Za-z][A-Za-z0-9&+/\-]*(?: [A-Za-z0-9&+/\-]+)*")

NATIONALITIES = {
    "مصري": "Egyptian", "سعودي": "Saudi", "أردني": "Jordanian", "سوري": "Syrian", "لبناني": "Lebanese",
    "فلسطيني": "Palestinian", "سوداني": "Sudanese", "يمني": "Yemeni", "عراقي": "Iraqi", "مغربي": "Moroccan",
    "تونسي": "Tunisian", "جزائري": "Algerian", "ليبي": "Libyan", "إماراتي": "Emirati", "كويتي": "Kuwaiti",
    "قطري": "Qatari", "بحريني": "Bahraini", "عماني": "Omani", "هندي": "Indian", "باكستاني": "Pakistani",
    "فلبيني": "Filipino", "بريطاني": "British", "أمريكي": "American",
}
LANGUAGES = {"العربية": "Arabic", "الإنجليزية": "English", "الفرنسية": "French", "الألمانية": "German",
             "الأردية": "Urdu", "الهندية": "Hindi", "الإسبانية": "Spanish", "التركية": "Turkish"}
CITIES = {"الرياض": "Riyadh", "جدة": "Jeddah", "الدمام": "Dammam", "الخبر": "Khobar", "الظهران": "Dhahran",
          "مكة": "Mecca", "المدينةالمنورة": "Medina", "دبي": "Dubai", "أبوظبي": "Abu Dhabi", "الدوحة": "Doha",
          "الكويت": "Kuwait City", "المنامة": "Manama", "مسقط": "Muscat", "القاهرة": "Cairo"}
SECTORS = (("الخدماتالمالية", "Financial services"), ("أسواقالمال", "Capital markets"), ("البورصات", "Stock exchange"),
           ("البورصة", "Stock exchange"), ("البنوك", "Banking"), ("المصرفية", "Banking"), ("التأمين", "Insurance"),
           ("التجارةالإلكترونية", "E-commerce"), ("الاتصالات", "Telecom"), ("الطاقة", "Energy"),
           ("العقار", "Real estate"), ("الرعايةالصحية", "Healthcare"), ("التجزئة", "Retail"),
           ("الذكاءالاصطناعي", "Artificial intelligence"), ("الاستشارات", "Consulting"), ("الإعلام", "Media"),
           ("اللوجستية", "Logistics"))
NOTICE = (("فوري", "Immediately"), ("أسبوعان", "Two weeks"), ("أسبوعين", "Two weeks"), ("ثلاثةأشهر", "Three months"),
          ("شهران", "Two months"), ("شهرين", "Two months"), ("شهر", "One month"))
EMPLOYERS = (("الخاص", "private"), ("الاستشارات", "consulting"), ("شبهالحكومي", "semi-government"),
             ("الحكومي", "government"))
WANTS = (("إدارةفريق", "managing a team"), ("عدةمنتجات", "several products"), ("استراتيجيةمنتج", "product strategy"),
         ("قيادةالتنفيذ", "leading delivery"))
MUSTS = (("الاستقرارالمالي", "financial stability"), ("حسنالمعاملة", "good treatment"), ("التقدير", "recognition"),
         ("سلمواضح", "a clear salary and promotion scale"))
REJECTS = (("عدمالاستقرارالمالي", "financial instability"), ("سوءالإدارة", "poor management"),
           ("المعاملةغيراللائقة", "disrespectful treatment"))
# Sections of the record, by their English headings (the order they come in).
SECTIONS = ("Candidate Snapshot", "Current Professional Status", "Target Roles", "Job Search Constraints",
            "Strengths, Gaps")


def split(text: str) -> tuple[str, str | None]:
    """A file's text -> (the CV before the record, the record); the record is None when there is none."""
    at = text.find(MARKER)
    return (text, None) if at < 0 else (text[:at], text[at:])


def _squash(text: str) -> str:
    """Spaces next to Arabic letters taken out (the PDF lost most of them anyway); English keeps its spaces."""
    text = re.sub(rf"(?<=[{AR}])\s+|\s+(?=[{AR}])", "", text)
    return re.sub(r"[ \t]+", " ", text)


def _section(text: str, name: str) -> str:
    start = text.find(name)
    if start < 0:
        return ""
    later = [text.find(s, start + len(name)) for s in SECTIONS[SECTIONS.index(name) + 1:]]
    ends = [e for e in later if e > 0]
    return text[start:min(ends) if ends else len(text)]


def _value(label: str, block: str) -> str:
    """The answer in a row: what follows its label, up to the source tag ([INT], [CV] ...)."""
    # No \b: Arabic letters run straight into the tag ("مصريINT").
    m = re.search(re.escape(label) + r"(.{0,400}?)(?:(?<![A-Z])INT(?![a-z])|\Z)", block, re.S)
    return re.sub(r"[\[\]|:]+", " ", m.group(1)).strip() if m else ""


def _pick(value: str, table) -> list[str]:
    return list(dict.fromkeys(english for arabic, english in table if arabic in value))


def _join(items: list[str], conj: str = "and") -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + f" {conj} " + items[-1]


def parse(record: str) -> dict:
    """The record -> {'fields': partial profile, 'found': what it gave}."""
    t = _squash(record)
    snapshot, targets, limits = (_section(t, n) for n in ("Candidate Snapshot", "Target Roles", "Job Search Constraints"))
    snapshot, targets, limits = snapshot or t, targets or t, limits or t
    fields: dict = {"search": {}, "cv": {}, "preferences": {}}

    name = re.search(r"^\s*([A-Z][A-Za-z.'\- ]{2,60}?)\s*\|", record[len(MARKER):], re.M)
    fields["name"] = name.group(1).strip() if name else ""
    nationality = _value("الجنسية", snapshot)
    word = re.sub(r"ة$", "", re.sub(rf"[^{AR}A-Za-z]", "", nationality))
    fields["nationality"] = NATIONALITIES.get(word, word if word.isascii() else "") if word else ""

    languages = []
    for arabic, english in LANGUAGES.items():
        if re.search(re.escape(arabic) + r"\W*اللغةالأم", snapshot):
            languages.append(f"{english} (Native)")
        elif level := re.search(re.escape(arabic) + r"\W*([ABC][12])(?![0-9])", snapshot):
            languages.append(f"{english} ({level.group(1)})")
    fields["cv"]["languages"] = languages

    # The roles they want, in their order: the priorities, the AI roles, then the ones they'd accept.
    roles_end = targets.find("القطاعاتالمفضلة")
    titles = [p.strip() for p in LATIN_PHRASE.findall(targets[:roles_end if roles_end > 0 else None]) if ROLE.search(p)]
    fields["search"]["titles"] = list(dict.fromkeys(titles))[:24]
    sectors = _value("القطاعاتالمفضلة", targets)
    # English sector names written in as they are ("Fintech"); stray letters from the PDF ("T") are not words.
    latin = [w for w in LATIN_PHRASE.findall(sectors) if len(w) >= 3 and w not in ("INT", "CV")]
    fields["search"]["keywords"] = list(dict.fromkeys(_pick(sectors, SECTORS) + latin))

    prefs = fields["preferences"]
    model = _value("نموذجالعمل", snapshot)
    prefs["work_modes"] = [m for m, hit in (("on-site", "المكتب" in model or "حضوري" in model),
                                            ("hybrid", "hybrid" in model.lower() or "هجين" in model),
                                            ("remote", "remote" in model.lower() or "عنبعد" in model)) if hit]
    move = _value("الانتقالالجغرافي", snapshot)
    where = []
    if "داخلالسعوديةفقط" in move:
        where.append("Within Saudi Arabia only, not abroad.")
    main = [CITIES[c] for c in CITIES if c in _value("المدنالأساسية", limits)]
    lower = [CITIES[c] for c in CITIES if re.search(re.escape(c) + r"\W*أولويةأقل", limits)]
    if main:
        where.append(f"Main cities: {_join(main)}" + (f"; {_join(lower)} lower priority." if lower else "."))
    prefs["relocate"] = " ".join(where)

    floor = _value("الحدالأدنى", limits)
    amount = re.search(r"\d[\d,.]*", floor)
    if amount:
        prefs["salary"] = f"At least {amount.group(0)} SAR a month" + (", all allowances included" if "شامل" in floor else "")
    prefs["notice"] = next((english for arabic, english in NOTICE if arabic in _value("مدةالإشعار", limits)), "")
    papers = _value("الإقامةوتصريحالعمل", limits)
    if "ساري" in papers:
        prefs["visa"] = "Iqama and work permit valid" + ("; can transfer" if "الانتقالمتاح" in papers else "")

    other = []
    move_up = _value("طبيعةالانتقال", targets)
    if "مشابهأوأعلى" in move_up:
        other.append("Wants a similar or more senior role" + (", using AI in their field." if "AI" in move_up else "."))
    if wants := _pick(_value("المسؤوليةالمطلوبة", targets), WANTS):
        other.append(f"Responsibility sought: {_join(wants, 'or')}.")
    companies = _value("الشركات", limits)
    if "الكبيرةوالمتوسطة" in companies:
        other.append("Prefers large and mid-size companies" +
                     ("; start-ups only after checking funding and stability." if "الناشئة" in companies else "."))
    if employers := _pick(_value("القطاعالتنظيميللجهة", limits), EMPLOYERS):
        other.append(f"Open to {_join(employers)} employers.")
    travel = _value("السفر", limits)
    if "داخلالمملكة" in travel:
        other.append("Travel: within Saudi Arabia" + ("; prefers not abroad." if "لايفضلخارج" in travel else "."))
    if musts := _pick(_value("الشروطغيرالقابلةللتفاوض", t), MUSTS):
        other.append(f"Must have: {_join(musts)}.")
    if rejects := _pick(_value("أسبابالرفض", targets), REJECTS):
        other.append(f"Turns down: {_join(rejects, 'or')}.")
    prefs["other"] = "\n".join(other)

    found = [k for k in ("name", "nationality") if fields[k]]
    found += [k for k in ("titles", "keywords") if fields["search"][k]]
    found += ["preferences"] if any(prefs.values()) else []
    found += ["languages"] if languages else []
    return {"fields": fields, "found": found}
