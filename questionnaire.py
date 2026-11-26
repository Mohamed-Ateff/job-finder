"""The questionnaire: a PDF form the person fills in, instead of sending a CV.

The app makes the form - blank for someone new, or already filled in from their profile - and
the person fills it in with any PDF reader on a computer or phone, saves it and sends it back.
Reading it back is exact (each answer has its own field), so nothing is guessed as it is with a
CV. It also asks what a CV never says and the search can use: other names for the same job, the
words that show a posting is in their field, titles and companies to skip, nationality (some
jobs are open only to certain nationalities), and how they want to work.

Free and on this computer: reportlab draws the form, pypdf fills it in and reads it back.
Labels are in English and Arabic; the fonts are IBM Plex Sans Arabic (Latin included), the
app's own typeface.
"""

from __future__ import annotations

import re
import time
from io import BytesIO
from pathlib import Path

import profiles
from cv_import import ImportError_

FORM_ID = "job-search-questionnaire/1"           # a hidden field: how a returned form is recognised
TITLE = ("Job Search Questionnaire", "استبيان البحث عن وظيفة")
FONTS_DIR = Path(__file__).resolve().parent / "webapp" / "static" / "fonts"

LEVEL_LABELS = {"entry": ("Entry level", "مبتدئ"), "associate": ("Associate", "مساعد"),
                "mid-senior": ("Mid–Senior", "متوسط إلى أول"), "director": ("Director", "مدير"),
                "executive": ("Executive", "تنفيذي")}
MODE_LABELS = {"on-site": ("On-site", "حضوري"), "hybrid": ("Hybrid", "هجين"), "remote": ("Remote", "عن بعد")}
TYPE_LABELS = {"full-time": ("Full-time", "دوام كامل"), "part-time": ("Part-time", "دوام جزئي"),
               "contract": ("Contract", "عقد مؤقت")}
CV_EXTRAS = (("certifications", "Certifications", "الشهادات المهنية", None),
             ("languages", "Languages", "اللغات", ("e.g. Arabic (native)", "مثلاً: العربية (اللغة الأم)")),
             ("training", "Training and courses", "الدورات التدريبية", None),
             ("awards", "Awards", "الجوائز", None))
MAX_ROLES, MAX_SCHOOLS = 20, 10

# --------------------------------------------------------------------- look --
INK, INK2, INK3 = "#1b1a17", "#5f5d57", "#9a978f"
RULE, BOX_LINE, BOX_FILL = "#e3e1db", "#d3d0c8", "#f8f7f4"
PAGE_W, PAGE_H = 595.2756, 841.8898                # A4
LEFT, TOP, BOTTOM = 50.0, 56.0, 58.0
WIDTH = PAGE_W - 2 * LEFT
COL_GAP, ROW_GAP = 14.0, 11.0
LINE_H = 12.6                                      # one line of a multi-line answer
FONT = {"regular": "PlexArabic", "medium": "PlexArabic-Medium", "semibold": "PlexArabic-SemiBold"}


def _fonts() -> None:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    if FONT["regular"] in pdfmetrics.getRegisteredFontNames():
        return
    for key, file in (("regular", "Regular"), ("medium", "Medium"), ("semibold", "SemiBold")):
        pdfmetrics.registerFont(TTFont(FONT[key], str(FONTS_DIR / f"IBMPlexSansArabic-{file}.ttf")))


def _width(text: str, font: str, size: float) -> float:
    from reportlab.pdfbase.pdfmetrics import stringWidth

    return stringWidth(text, FONT[font], size)


_LTR_WORD = re.compile(r"^[\x21-\x7e–’]*[A-Za-z0-9][\x21-\x7e–’]*$")
_MIRROR = str.maketrans("()[]«»", ")(][»«")


def _visual(text: str) -> str:
    """Arabic in reading order -> the order a PDF draws it, left to right: letters joined
    (presentation forms), Arabic runs reversed, English words and numbers kept as they are."""
    import arabic_reshaper

    runs: list[tuple[bool, list[str]]] = []
    for word in text.split():
        ltr = bool(_LTR_WORD.match(word))
        if runs and runs[-1][0] == ltr:
            runs[-1][1].append(word)
        else:
            runs.append((ltr, [word]))
    out = []
    for ltr, words in reversed(runs):
        run = " ".join(words)
        out.append(run if ltr else arabic_reshaper.reshape(run).translate(_MIRROR)[::-1])
    return " ".join(out)


def _wrap(text: str, font: str, size: float, width: float, arabic: bool = False) -> list[str]:
    lines: list[str] = []
    for word in text.split():
        trial = f"{lines[-1]} {word}" if lines else word
        if lines and _width(_visual(trial) if arabic else trial, font, size) > width:
            lines.append(word)
        elif lines:
            lines[-1] = trial
        else:
            lines.append(word)
    return lines


class _Bilingual:
    """English on the left, Arabic on the right: one line when both fit, else English then Arabic."""

    def __init__(self, en: str, ar: str, width: float, font: str, size: float, gap: float = 14.0):
        self.size, self.font, self.lead = size, font, size * 1.42
        if _width(en, font, size) + _width(_visual(ar), font, size + 0.6) + gap <= width:
            self.lines = [(en, ar)]
        else:
            self.lines = [(line, "") for line in _wrap(en, font, size, width)]
            self.lines += [("", line) for line in _wrap(ar, font, size + 0.6, width, arabic=True)]

    @property
    def height(self) -> float:
        return len(self.lines) * self.lead

    def draw(self, c, x: float, y: float, width: float, en_color: str, ar_color: str) -> float:
        """Draws from y (top) down; returns the y under the last line."""
        for en, ar in self.lines:
            y -= self.lead
            base = y + self.lead * 0.27
            if en:
                c.setFillColor(en_color)
                c.setFont(FONT[self.font], self.size)
                c.drawString(x, base, en)
            if ar:
                c.setFillColor(ar_color)
                c.setFont(FONT[self.font], self.size + 0.6)
                c.drawRightString(x + width, base, _visual(ar))
        return y


def _box(c, x: float, y: float, w: float, h: float) -> None:
    c.setLineWidth(0.6)
    c.setStrokeColor(BOX_LINE)
    c.setFillColor(BOX_FILL)
    c.roundRect(x, y, w, h, 3, stroke=1, fill=1)


# -------------------------------------------------------------------- cells --
class _Cell:
    """One answer in a row: its label (and hint) on top, the field under it."""

    def __init__(self, en: str = "", ar: str = "", hint: tuple[str, str] | None = None):
        self.en, self.ar, self.hint = en, ar, hint

    def head(self, width: float) -> list[_Bilingual]:
        parts = [_Bilingual(self.en, self.ar, width, "medium", 8.4)] if self.en else []
        if self.hint:
            parts.append(_Bilingual(*self.hint, width, "regular", 7.4))
        return parts

    def head_height(self, width: float) -> float:
        parts = self.head(width)
        return sum(p.height for p in parts) + (5 if parts else 0)

    def draw_head(self, c, x: float, y: float, width: float) -> None:
        for n, part in enumerate(self.head(width)):
            y = part.draw(c, x, y, width, INK if n == 0 else INK3, INK2 if n == 0 else INK3)


class _Text(_Cell):
    def __init__(self, name: str, en: str = "", ar: str = "", hint=None, rows: int = 1):
        super().__init__(en, ar, hint)
        self.name, self.rows = name, rows

    def body_height(self) -> float:
        return 22.0 if self.rows == 1 else self.rows * LINE_H + 10

    def draw_body(self, c, x: float, y: float, width: float) -> None:
        h = self.body_height()
        _box(c, x, y - h, width, h)
        c.acroForm.textfield(
            name=self.name, tooltip=self.en or self.name, x=x + 3, y=y - h + 1.5, width=width - 6, height=h - 3,
            value="", borderWidth=0, borderColor=None, fillColor=None, textColor=INK, fontName="Helvetica",
            fontSize=10 if self.rows == 1 else 9.5, fieldFlags="multiline" if self.rows > 1 else "", maxlen=0)


class _Choice(_Cell):
    def __init__(self, name: str, en: str, ar: str, options: list[str], value: str, hint=None):
        super().__init__(en, ar, hint)
        self.name, self.options, self.value = name, options, value

    def body_height(self) -> float:
        return 22.0

    def draw_body(self, c, x: float, y: float, width: float) -> None:
        _box(c, x, y - 22, width, 22)
        c.acroForm.choice(
            name=self.name, tooltip=self.en, x=x + 3, y=y - 20.5, width=width - 6, height=19, value=self.value,
            options=self.options, borderWidth=0, borderColor=None, fillColor=None, textColor=INK,
            fontName="Helvetica", fontSize=10)


class _Checks(_Cell):
    """Tick boxes in even columns: the English beside each box, the Arabic under it."""

    SIZE, PAD = 10.0, 6.0

    def __init__(self, en: str, ar: str, items: list[tuple[str, str, str, bool]], hint=None):
        super().__init__(en, ar, hint)
        self.items = items                         # (field name, English, Arabic, ticked)

    def body_height(self, width: float = WIDTH) -> float:
        return 25.0

    def draw_body(self, c, x: float, y: float, width: float) -> None:
        col = width / len(self.items)
        for n, (name, en, ar, ticked) in enumerate(self.items):
            cx, by = x + n * col, y - self.SIZE - 1.5
            c.setLineWidth(0.7)
            c.setStrokeColor(BOX_LINE)
            c.setFillColor("#ffffff")
            c.roundRect(cx, by, self.SIZE, self.SIZE, 2, stroke=1, fill=1)
            c.acroForm.checkbox(name=name, tooltip=en, x=cx, y=by, size=self.SIZE, checked=ticked,
                                buttonStyle="check", borderWidth=0, borderColor=None, fillColor=None,
                                textColor=INK, fieldFlags="")
            tx = cx + self.SIZE + self.PAD
            c.setFillColor(INK)
            c.setFont(FONT["regular"], 9)
            c.drawString(tx, by + 1.7, en)
            c.setFillColor(INK2)
            c.setFont(FONT["regular"], 8.8)
            c.drawString(tx, by - 10.5, _visual(ar))


# ------------------------------------------------------------------- blocks --
class _Block:
    space_before = 0.0
    keep_with_next = False

    def height(self) -> float:
        raise NotImplementedError

    def draw(self, c, y: float) -> None:
        raise NotImplementedError


class _Row(_Block):
    """Answers side by side; their fields line up even when one label wraps and another doesn't."""

    def __init__(self, cells: list[tuple[_Cell, float]], space_before: float = ROW_GAP):
        self.cells, self.space_before = cells, space_before

    def _widths(self) -> list[float]:
        free = WIDTH - COL_GAP * (len(self.cells) - 1)
        return [free * share for _, share in self.cells]

    def _head(self) -> float:
        return max(cell.head_height(w) for (cell, _), w in zip(self.cells, self._widths()))

    def _body(self, cell: _Cell, width: float) -> float:
        return cell.body_height(width) if isinstance(cell, _Checks) else cell.body_height()

    def height(self) -> float:
        return self._head() + max(self._body(cell, w) for (cell, _), w in zip(self.cells, self._widths()))

    def draw(self, c, y: float) -> None:
        head = self._head()
        x = LEFT
        for (cell, _), w in zip(self.cells, self._widths()):
            cell.draw_head(c, x, y, w)
            cell.draw_body(c, x, y - head, w)
            x += w + COL_GAP


class _Section(_Block):
    keep_with_next = True

    def __init__(self, number: int, en: str, ar: str, note: tuple[str, str] | None = None):
        self.number, self.en, self.ar, self.note = number, en, ar, note
        self.space_before = 30.0

    def height(self) -> float:
        return 28.0 + (_Bilingual(*self.note, WIDTH, "regular", 7.8).height + 4 if self.note else 0)

    def draw(self, c, y: float) -> None:
        base = y - 15
        c.setFillColor(INK3)
        c.setFont(FONT["medium"], 8.5)
        c.drawString(LEFT, base + 1, f"{self.number:02d}")
        c.setFillColor(INK)
        c.setFont(FONT["semibold"], 13.5)
        c.drawString(LEFT + 21, base, self.en)
        c.setFont(FONT["semibold"], 13.5)
        c.drawRightString(LEFT + WIDTH, base, _visual(self.ar))
        c.setStrokeColor(RULE)
        c.setLineWidth(0.6)
        c.line(LEFT, base - 9, LEFT + WIDTH, base - 9)
        if self.note:
            _Bilingual(*self.note, WIDTH, "regular", 7.8).draw(c, LEFT, base - 12, WIDTH, INK3, INK3)


class _Subhead(_Block):
    keep_with_next = True

    def __init__(self, en: str, ar: str):
        self.en, self.ar, self.space_before = en, ar, 20.0

    def height(self) -> float:
        return 14.0

    def draw(self, c, y: float) -> None:
        c.setFillColor(INK2)
        c.setFont(FONT["semibold"], 9.2)
        c.drawString(LEFT, y - 10, self.en)
        c.setFont(FONT["semibold"], 9.8)
        c.drawRightString(LEFT + WIDTH, y - 10, _visual(self.ar))


class _Prose(_Block):
    """A paragraph in both languages, side by side: English on the left, Arabic on the right."""

    def __init__(self, en: str, ar: str, size: float = 9.2, color: str = INK2, space_before: float = 0.0,
                 font: str = "regular"):
        self.en, self.ar, self.size, self.color, self.font = en, ar, size, color, font
        self.space_before = space_before
        self.col = (WIDTH - 30) / 2

    def _lines(self):
        return (_wrap(self.en, self.font, self.size, self.col),
                _wrap(self.ar, self.font, self.size + 0.6, self.col, arabic=True))

    def height(self) -> float:
        en, ar = self._lines()
        return max(len(en) * self.size * 1.5, len(ar) * (self.size + 0.6) * 1.62)

    def draw(self, c, y: float) -> None:
        en, ar = self._lines()
        c.setFillColor(self.color)
        c.setFont(FONT[self.font], self.size)
        for n, line in enumerate(en):
            c.drawString(LEFT, y - self.size - n * self.size * 1.5, line)
        c.setFont(FONT[self.font], self.size + 0.6)
        for n, line in enumerate(ar):
            c.drawRightString(LEFT + WIDTH, y - self.size - n * (self.size + 0.6) * 1.62, _visual(line))


class _Title(_Block):
    def height(self) -> float:
        return 40.0

    def draw(self, c, y: float) -> None:
        c.setFillColor(INK)
        c.setFont(FONT["semibold"], 21)
        c.drawString(LEFT, y - 22, TITLE[0])
        c.setFont(FONT["semibold"], 19)
        c.drawRightString(LEFT + WIDTH, y - 22, _visual(TITLE[1]))
        c.setStrokeColor(INK)
        c.setLineWidth(0.9)
        c.line(LEFT, y - 37, LEFT + WIDTH, y - 37)
        # How a returned form is recognised: a hidden field the reader never sees.
        c.acroForm.textfield(name="q_form", value=FORM_ID, x=0, y=0, width=1, height=1, borderWidth=0,
                             borderColor=None, fillColor=None, annotationFlags="hidden",
                             fieldFlags="readOnly", maxlen=0)


class _Rule(_Block):
    def __init__(self, space_before: float = 30.0):
        self.space_before = space_before

    def height(self) -> float:
        return 12.0

    def draw(self, c, y: float) -> None:
        c.setStrokeColor(RULE)
        c.setLineWidth(0.6)
        c.line(LEFT, y - 1, LEFT + WIDTH, y - 1)


# ---------------------------------------------------------------- the form --
def _lines(values) -> str:
    return "\n".join(values or [])


def _complete(profile: dict) -> dict:
    """Any profile with every part present (an older one may lack the newer parts)."""
    p = profiles.blank()
    p.update({k: v for k, v in profile.items() if k not in profiles.GROUPS})
    for group in profiles.GROUPS:
        p[group].update(profile.get(group) or {})
    return p


def answers(profile: dict) -> dict:
    """The profile as the form's answers (field name -> text), to fill the form in with."""
    profile = _complete(profile)
    s, cv, pr = profile["search"], profile["cv"], profile["preferences"]
    out = {"q_name": profile.get("name", ""), "q_headline": profile.get("headline", ""),
           "q_email": profile.get("email", ""), "q_phone": profile.get("phone", ""),
           "q_city": profile.get("city", ""), "q_nationality": profile.get("nationality", ""),
           "q_linkedin": profile.get("linkedin", ""),
           "q_titles": _lines(s["titles"]), "q_years": pr["years"], "q_keywords": _lines(s["keywords"]),
           "q_exclude": _lines(s["exclude"]), "q_exclude_companies": _lines(s["exclude_companies"]),
           "q_relocate": pr["relocate"], "q_notice": pr["notice"], "q_salary": pr["salary"], "q_visa": pr["visa"],
           "q_other": pr["other"], "q_summary": "\n\n".join(cv["summary"]),
           "q_achievements": _lines(cv["achievements"]), "q_skills": _lines(cv["skills"])}
    for key, *_ in CV_EXTRAS:
        out[f"q_{key}"] = _lines(cv[key])
    for i, e in enumerate(cv["experience"], 1):
        out.update({f"q_exp{i}_title": e["role_title"], f"q_exp{i}_company": e["company"],
                    f"q_exp{i}_period": e["period"], f"q_exp{i}_about": e["role_description"],
                    f"q_exp{i}_points": _lines(e["bullets"])})
    for i, e in enumerate(cv["education"], 1):
        out.update({f"q_edu{i}_degree": e["credential"], f"q_edu{i}_school": e["institution"],
                    f"q_edu{i}_year": e["detail"]})
    return {k: v for k, v in out.items() if v}


def _fid(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower())


def _blocks(profile: dict | None) -> list[_Block]:
    p = _complete(profile) if profile else profiles.blank()
    s, pr = p["search"], p["preferences"]
    levels = set(s["levels"]) if profile else set()
    B: list[_Block] = [
        _Title(),
        _Prose("Fill this in on your computer or phone, then save it and send it back. Every answer is "
               "used to find and rank jobs for you, so the more you add, the better the matches. "
               "Leave out anything that doesn’t apply.",
               "املأ هذا النموذج على جهازك أو هاتفك، ثم احفظه وأعده إلينا. نستخدم كل إجابة للبحث عن "
               "الوظائف وترتيبها لك، فكلما أضفت أكثر كانت النتائج أدق. اترك ما لا ينطبق عليك.",
               space_before=14),
    ]
    if profile:
        B.append(_Prose("Some answers are already filled in from your profile. Check them, and correct "
                        "anything that has changed.",
                        "بعض الإجابات مُلئت مسبقاً من ملفك. راجعها وصحّح ما تغيّر.",
                        size=8.8, color=INK, space_before=10, font="medium"))

    half = 0.5
    B += [
        _Section(1, "About you", "معلومات عنك"),
        _Row([(_Text("q_name", "Full name", "الاسم الكامل"), half),
              (_Text("q_headline", "Current or last job title", "المسمى الوظيفي الحالي أو الأخير"), half)], 12),
        _Row([(_Text("q_email", "Email", "البريد الإلكتروني"), half),
              (_Text("q_phone", "Mobile number", "رقم الجوال"), half)]),
        _Row([(_Text("q_city", "City you live in", "مدينة الإقامة"), half),
              (_Text("q_nationality", "Nationality", "الجنسية"), half)]),
        _Row([(_Text("q_linkedin", "LinkedIn profile link", "رابط حسابك في لينكدإن"), 1.0)]),

        _Section(2, "The jobs you want", "الوظائف التي تبحث عنها"),
        _Row([(_Text("q_titles", "Job titles to search for", "المسميات الوظيفية للبحث",
                     ("One per line. Add other names for the same job, e.g. Finance Manager, Financial Controller.",
                      "مسمّى في كل سطر، وأضف الأسماء الأخرى للوظيفة نفسها."), rows=5), 1.0)], 12),
        _Row([(_Checks("Seniority", "المستوى الوظيفي",
                       [(f"q_level_{_fid(lv)}", *LEVEL_LABELS[lv], lv in levels) for lv in profiles.LEVELS],
                       ("Tick every level you would accept.", "اختر كل مستوى تقبل به.")), 1.0)]),
        _Row([(_Choice("q_country", "Country to search in", "دولة البحث", profiles.COUNTRIES, s["country"]), half),
              (_Text("q_years", "Years of experience", "سنوات الخبرة"), half)]),
        _Row([(_Text("q_keywords", "Your field", "مجالك",
                     ("Industries, specialities and tools that show a job is in your field, one per line, "
                      "e.g. Banking, IFRS, SAP.", "القطاعات والتخصصات والأدوات التي تدل على أن الوظيفة في مجالك."),
                     rows=4), 1.0)]),
        _Row([(_Text("q_exclude", "Job titles to skip", "مسميات تُستبعد",
                     ("Words, one per line, e.g. Sales", "كلمة في كل سطر"), rows=3), half),
              (_Text("q_exclude_companies", "Companies to skip", "شركات تُستبعد",
                     ("e.g. your current employer", "مثل جهة عملك الحالية"), rows=3), half)]),

        _Section(3, "How you want to work", "طريقة العمل التي تفضلها"),
        _Row([(_Checks("Work arrangement", "نمط العمل",
                       [(f"q_mode_{_fid(m)}", *MODE_LABELS[m], m in pr["work_modes"]) for m in profiles.WORK_MODES]),
               half),
              (_Checks("Job type", "نوع الوظيفة",
                       [(f"q_type_{_fid(t)}", *TYPE_LABELS[t], t in pr["job_types"]) for t in profiles.JOB_TYPES]),
               half)], 12),
        _Row([(_Text("q_relocate", "Would you relocate?", "هل تقبل الانتقال؟",
                     ("Where to, or No", "إلى أين، أو لا")), half),
              (_Text("q_notice", "Notice period", "مدة الإشعار",
                     ("When could you start?", "متى يمكنك البدء؟")), half)]),
        _Row([(_Text("q_salary", "Expected monthly salary", "الراتب الشهري المتوقع",
                     ("Optional. Never shown on your CV.", "اختياري، ولا يظهر في السيرة الذاتية.")), half),
              (_Text("q_visa", "Residency or visa status", "الإقامة أو التأشيرة",
                     ("e.g. Transferable iqama", "مثلاً: إقامة قابلة للنقل")), half)]),
        _Row([(_Text("q_other", "Anything else we should know", "أي شيء آخر تود إخبارنا به",
                     ("Must-haves, deal-breakers, companies you would love to join.",
                      "شروطك الأساسية، وما لا تقبله، والشركات التي تتمنى العمل فيها."), rows=4), 1.0)]),

        _Section(4, "Your profile", "نبذة عنك"),
        _Row([(_Text("q_summary", "Professional summary", "الملخص المهني",
                     ("Two or three sentences on your experience and strengths.",
                      "جملتان أو ثلاث عن خبرتك ونقاط قوتك."), rows=5), 1.0)], 12),
        _Row([(_Text("q_achievements", "Key achievements", "أبرز الإنجازات",
                     ("One per line. Figures help, where you can share them.",
                      "إنجاز في كل سطر، والأرقام تفيد متى أمكن ذكرها."), rows=6), 1.0)]),
    ]

    roles = min(MAX_ROLES, max(4, len(p["cv"]["experience"]) + 1)) if profile else 4
    B.append(_Section(5, "Experience", "الخبرات العملية", ("Most recent first.", "الأحدث أولاً.")))
    for i in range(1, roles + 1):
        sub = _Subhead(f"Role {i}", f"الوظيفة {i}")
        if i == 1:
            sub.space_before = 10
        B += [
            sub,
            _Row([(_Text(f"q_exp{i}_title", "Job title", "المسمى الوظيفي"), half),
                  (_Text(f"q_exp{i}_company", "Company", "الشركة"), half)], 6),
            _Row([(_Text(f"q_exp{i}_period", "Dates", "الفترة", ("e.g. Jan 2020 – Present", "مثلاً: 2020 – الآن")), 1 / 3),
                  (_Text(f"q_exp{i}_about", "The role in one line", "الدور في سطر واحد", ("Optional", "اختياري")), 2 / 3)]),
            _Row([(_Text(f"q_exp{i}_points", "What you did and achieved", "ما قمت به وما حققته",
                         ("One point per line", "نقطة في كل سطر"), rows=4), 1.0)]),
        ]

    schools = min(MAX_SCHOOLS, max(3, len(p["cv"]["education"]) + 1)) if profile else 3
    B += [
        _Section(6, "Skills and education", "المهارات والتعليم"),
        _Row([(_Text("q_skills", "Skills", "المهارات",
                     ("One per line, the strongest first.", "مهارة في كل سطر، الأقوى أولاً."), rows=5), 1.0)], 12),
        _Subhead("Education", "التعليم"),
    ]
    for i in range(1, schools + 1):
        first = i == 1
        row = _Row([(_Text(f"q_edu{i}_degree", *(("Degree or qualification", "الشهادة أو المؤهل") if first else ("", ""))), 0.42),
                    (_Text(f"q_edu{i}_school", *(("University or school", "الجامعة أو المدرسة") if first else ("", ""))), 0.42),
                    (_Text(f"q_edu{i}_year", *(("Year", "السنة") if first else ("", ""))), 0.16)],
                   ROW_GAP if first else 6)
        row.keep_with_next = i < schools           # the table's rows stay on one page
        B.append(row)
    pairs = [CV_EXTRAS[0:2], CV_EXTRAS[2:4]]
    for pair in pairs:
        B.append(_Row([(_Text(f"q_{key}", en, ar, hint or ("One per line", "واحد في كل سطر"), rows=4), half)
                       for key, en, ar, hint in pair]))
    B += [
        _Rule(),
        _Prose("Thank you. Save the file and send it back as it is: printing it to PDF removes the answers.",
               "شكراً لك. احفظ الملف وأرسله كما هو، فطباعته بصيغة PDF تحذف الإجابات.",
               size=8.8, color=INK2),
    ]
    return B


def _paginate(blocks: list[_Block]) -> list[list[tuple[_Block, float]]]:
    """Blocks -> pages of (block, top y). A heading never ends a page."""
    pages: list[list[tuple[_Block, float]]] = [[]]
    y = PAGE_H - TOP
    i = 0
    while i < len(blocks):
        # A heading goes with what follows it.
        group = [blocks[i]]
        while group[-1].keep_with_next and i + len(group) < len(blocks):
            group.append(blocks[i + len(group)])
        need = sum(b.height() + (b.space_before if n or pages[-1] else 0) for n, b in enumerate(group))
        if pages[-1] and y - need < BOTTOM:
            pages.append([])
            y = PAGE_H - TOP
        for b in group:
            if pages[-1]:
                y -= b.space_before
            pages[-1].append((b, y))
            y -= b.height()
        i += len(group)
    return pages


def build(profile: dict | None = None) -> bytes:
    """The questionnaire as a fillable PDF: blank, or filled in from the profile so far."""
    from reportlab.pdfgen import canvas

    _fonts()
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(PAGE_W, PAGE_H))
    c.setTitle(TITLE[0])
    c.setSubject(FORM_ID)
    c.setCreator("Job Automation")
    pages = _paginate(_blocks(profile))
    stamp = time.strftime("%d %b %Y").lstrip("0")
    for n, page in enumerate(pages, 1):
        for block, y in page:
            block.draw(c, y)
        c.setFillColor(INK3)
        c.setFont(FONT["regular"], 7.4)
        c.drawString(LEFT, BOTTOM - 26, f"{TITLE[0]}  ·  {stamp}")
        c.drawRightString(LEFT + WIDTH, BOTTOM - 26, f"{n} / {len(pages)}")
        c.showPage()
    c.save()
    return _fill(buf.getvalue(), answers(profile) if profile else {})


def _plain(text: str) -> bool:
    try:
        text.encode("cp1252")
        return True
    except UnicodeEncodeError:
        return False


def _fill(pdf: bytes, values: dict) -> bytes:
    """Writes the answers into the form's fields. Readers redraw the fields when the file is
    opened (NeedAppearances); an answer the form's font can't draw (Arabic) is left for them
    to draw rather than drawn wrongly here."""
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import NameObject, TextStringObject

    writer = PdfWriter(clone_from=PdfReader(BytesIO(pdf)))
    # The fields' font in the standard Windows encoding, so dashes and quotes come out right.
    fonts = writer._root_object["/AcroForm"]["/DR"]["/Font"]
    for key in fonts:
        fonts[key].get_object()[NameObject("/Encoding")] = NameObject("/WinAnsiEncoding")
    plain = {k: v for k, v in values.items() if _plain(v)}
    if plain:
        writer.update_page_form_field_values(None, plain, auto_regenerate=False)
    other = {k: v for k, v in values.items() if k not in plain}
    for page in writer.pages if other else []:
        for annot in page.get("/Annots") or []:
            widget = annot.get_object()
            name = widget.get("/T")
            if name in other:
                widget[NameObject("/V")] = TextStringObject(other[name])
                widget.pop("/AP", None)
    writer.set_need_appearances_writer(True)
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


# ------------------------------------------------------------------ reading --
def _text(value) -> str:
    if value is None:
        return ""
    text = str(value)
    return "" if text.startswith("/") else text.replace("\r\n", "\n").replace("\r", "\n").strip()


def _ticked(value) -> bool:
    return value is not None and str(value) not in ("", "/Off", "Off")


def _list(value, split_commas: bool = False) -> list[str]:
    out = []
    for line in _text(value).split("\n"):
        parts = re.split(r"\s*[,،;؛]\s*", line) if split_commas else [line]
        for part in parts:
            part = re.sub(r"^\s*(?:[•·▪●○■\-–*]|\d{1,2}[.)])\s*", "", part).strip()
            if part:
                out.append(part)
    return out


def _paragraphs(value) -> list[str]:
    text = _text(value)
    paras = [re.sub(r"\s*\n\s*", " ", p).strip() for p in re.split(r"\n\s*\n", text)]
    if len(paras) == 1:
        paras = [p.strip() for p in text.split("\n")]
    paras = [p for p in paras if p]
    return paras[:3] + [" ".join(paras[3:])] if len(paras) > 4 else paras


def parse(values: dict) -> dict:
    """The form's answers (field name -> value) -> {'fields': partial profile, 'found': what was answered}."""
    v = values.get
    email = _text(v("q_email"))
    linkedin = _text(v("q_linkedin"))
    fields: dict = {
        "name": _text(v("q_name")), "headline": _text(v("q_headline")),
        # A mistyped address mustn't stop the rest from being read: it is left out.
        "email": email if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) else "",
        "phone": _text(v("q_phone")), "city": _text(v("q_city")), "nationality": _text(v("q_nationality")),
        "linkedin": "" if re.search(r"[<>\"'\s]|javascript:", linkedin, re.I) else linkedin,
    }
    country = _text(v("q_country"))
    fields["search"] = {
        "titles": _list(v("q_titles"), split_commas=True),
        "levels": [lv for lv in profiles.LEVELS if _ticked(v(f"q_level_{_fid(lv)}"))],
        "country": country if country in profiles.COUNTRIES else "",
        "keywords": _list(v("q_keywords"), split_commas=True),
        "exclude": _list(v("q_exclude"), split_commas=True),
        "exclude_companies": _list(v("q_exclude_companies")),
    }
    fields["preferences"] = {
        "years": _text(v("q_years")),
        "work_modes": [m for m in profiles.WORK_MODES if _ticked(v(f"q_mode_{_fid(m)}"))],
        "job_types": [t for t in profiles.JOB_TYPES if _ticked(v(f"q_type_{_fid(t)}"))],
        "relocate": _text(v("q_relocate")), "notice": _text(v("q_notice")), "salary": _text(v("q_salary")),
        "visa": _text(v("q_visa")), "other": _text(v("q_other")),
    }
    experience = []
    for i in range(1, MAX_ROLES + 1):
        role = {"role_title": _text(v(f"q_exp{i}_title")), "company": _text(v(f"q_exp{i}_company")),
                "period": _text(v(f"q_exp{i}_period")), "role_description": _text(v(f"q_exp{i}_about")),
                "bullets": _list(v(f"q_exp{i}_points"))}
        if role["role_title"] or role["company"]:
            experience.append(role)
    education = []
    for i in range(1, MAX_SCHOOLS + 1):
        school = {"credential": _text(v(f"q_edu{i}_degree")), "institution": _text(v(f"q_edu{i}_school")),
                  "detail": _text(v(f"q_edu{i}_year"))}
        if school["credential"] or school["institution"]:
            education.append(school)
    fields["cv"] = {
        "summary": _paragraphs(v("q_summary")),
        "achievements": _list(v("q_achievements")),
        "experience": experience,
        "skills": _list(v("q_skills"), split_commas=True),
        "education": education,
        **{key: _list(v(f"q_{key}")) for key, *_ in CV_EXTRAS},
    }
    found = [k for k in ("name", "headline", "email", "phone", "linkedin", "city", "nationality") if fields[k]]
    found += [k for k in ("titles", "keywords", "exclude", "exclude_companies") if fields["search"][k]]
    if any(fields["preferences"].values()):
        found.append("preferences")
    found += [k for k, value in fields["cv"].items() if value]
    return {"fields": fields, "found": found, "source": "questionnaire"}


def read(filename: str, data: bytes) -> dict | None:
    """A returned questionnaire -> parse()'s answer; None when the file is something else (a CV)."""
    if not filename.lower().endswith(".pdf"):
        return None
    from pypdf import PdfReader

    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            reader.decrypt("")
        fields = reader.get_fields() or {}
    except Exception:  # noqa: BLE001 - not a readable form: cv_import gives its usual answer
        return None
    values = {name: field.get("/V") for name, field in fields.items()}
    if _text(values.get("q_form")) == FORM_ID or "q_titles" in values:
        return parse(values)
    if not fields:
        try:
            first = reader.pages[0].extract_text() or "" if reader.pages else ""
        except Exception:  # noqa: BLE001
            first = ""
        if TITLE[0] in first:
            raise ImportError_("This questionnaire was printed to PDF, which removes the answers. "
                               "Open the one that was sent, fill it in, and use Save instead of Print.")
    return None
