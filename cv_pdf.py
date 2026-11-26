"""The CV as a PDF: the same content and layout as the Word file (job_automation.render_cv_docx) -
name, headline, contact line, profile, skills, achievements, experience with dates on the right,
education, certifications, training, awards, languages. One A4 column, real text (ATS-readable).
Free and local: reportlab, with the app's own typeface (IBM Plex Sans Arabic, Latin included).
"""

from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

FONTS_DIR = Path(__file__).resolve().parent / "webapp" / "static" / "fonts"
INK, MUTED, ACCENT = "#1B1A17", "#5F5D57", "#1F3A5F"
REG, MED, BOLD = "PlexArabic", "PlexArabic-Medium", "PlexArabic-SemiBold"


def _fonts() -> None:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    if REG in pdfmetrics.getRegisteredFontNames():
        return
    for name, file in ((REG, "Regular"), (MED, "Medium"), (BOLD, "SemiBold")):
        pdfmetrics.registerFont(TTFont(name, str(FONTS_DIR / f"IBMPlexSansArabic-{file}.ttf")))
    pdfmetrics.registerFontFamily(REG, normal=REG, bold=BOLD, italic=REG, boldItalic=BOLD)


def render(cv, profile: dict | None = None, name: str = "") -> bytes:
    """cv: a TailoredCV (or anything with its fields); profile: the fixed facts (cv_fixed / cv_profile.json)."""
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (KeepTogether, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer,
                                    Table, TableStyle)
    from reportlab.platypus.flowables import HRFlowable

    _fonts()
    profile = profile or {}
    name = profile.get("name") or name
    width = A4[0] - 36 * mm

    def style(size=10, font=REG, color=INK, lead=1.38, after=2, before=0):
        return ParagraphStyle("s", fontName=font, fontSize=size, leading=size * lead, textColor=color,
                              spaceAfter=after, spaceBefore=before, alignment=TA_LEFT)

    body, small = style(9.8), style(9, color=MUTED)
    story: list = [Paragraph(escape(name), style(21, BOLD, lead=1.15, after=3))]
    if cv.headline:
        story.append(Paragraph(escape(cv.headline), style(11, BOLD, ACCENT, after=3)))
    contact = [profile.get(k) for k in ("location", "phone", "email", "linkedin", "website")]
    if any(contact):
        story.append(Paragraph(escape("  ·  ".join(c for c in contact if c)), style(9, color=MUTED, after=6)))

    def heading(text: str) -> list:
        return [Spacer(1, 7), Paragraph(escape(text.rstrip(":").upper()), style(9.5, BOLD, ACCENT, after=2)),
                HRFlowable(width="100%", thickness=0.7, color=ACCENT, spaceBefore=0, spaceAfter=5)]

    def bullets(items: list[str]):
        return ListFlowable([ListItem(Paragraph(escape(i), body), leftIndent=12, value="•") for i in items],
                            bulletType="bullet", start="•", leftIndent=12, bulletFontName=REG, bulletFontSize=8,
                            bulletColor=INK, spaceBefore=0)

    def with_dates(left: str, right: str, size: float = 10.5):
        t = Table([[Paragraph(escape(left), style(size, BOLD, after=0)),
                    Paragraph(f'<para alignment="right">{escape(right)}</para>', style(9, color=MUTED, after=0))]],
                  colWidths=[width * 0.75, width * 0.25])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
        return t

    if cv.about_paragraphs:
        story += heading(profile.get("profile_heading") or "Professional Profile")
        story += [Paragraph(escape(p), style(9.8, after=4)) for p in cv.about_paragraphs]
    if cv.core_competencies:
        skills = [s.strip() for s in re.split(r"\s*[|·•]\s*", cv.core_competencies) if s.strip()]
        groups = [s for s in skills if re.match(r"^[^:]{2,40}:\s", s)]
        story += heading("Core Skills")
        for g in groups:                 # "Frameworks & Libraries: React, Next.js" - one line each, as written
            label, rest = g.split(":", 1)
            story.append(Paragraph(f"<b>{escape(label.strip())}:</b> {escape(rest.strip())}", style(9.8, after=1.5)))
        others = [s for s in skills if s not in groups]
        if others:
            story.append(Paragraph(escape("  ·  ".join(others)), body))
    if cv.key_achievements:
        story += heading(cv.achievements_title or "Key Achievements") + [bullets(cv.key_achievements)]
    if cv.work_experience:
        story += heading("Professional Experience")
        for i, e in enumerate(cv.work_experience):
            head = [Spacer(1, 5 if i else 0), with_dates(e.role_title, e.period)]
            if e.company:
                head.append(Paragraph(escape(e.company), style(9.5, color=MUTED, after=2)))
            if e.role_description:
                head.append(Paragraph(escape(e.role_description), body))
            story.append(KeepTogether(head + ([bullets(e.bullets[:1])] if e.bullets else [])))
            if len(e.bullets) > 1:
                story.append(bullets(e.bullets[1:]))
    if profile.get("education"):
        story += heading("Education")
        for edu in profile["education"]:
            detail = edu.get("detail", "")
            short = detail if len(detail) <= 24 else ""
            block = [with_dates(edu.get("credential", ""), short, 10)]
            below = "  ·  ".join(x for x in (edu.get("institution", ""), "" if short else detail) if x)
            if below:
                block.append(Paragraph(escape(below), style(9.3, color=MUTED, after=3)))
            story.append(KeepTogether(block))
    for key, title in (("certifications", "Professional Certifications"), ("training", "Training"), ("awards", "Awards")):
        if profile.get(key):
            story += heading(title) + [bullets(list(profile[key]))]
    if profile.get("languages"):
        story += heading("Languages") + [Paragraph(escape("  ·  ".join(profile["languages"])), body)]

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=15 * mm,
                            bottomMargin=15 * mm, title=f"{name} - CV", author=name)
    doc.build(story)
    return buf.getvalue()
