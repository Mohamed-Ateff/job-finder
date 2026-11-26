"""Free mode: score jobs and prepare CVs with no AI service - no account, no key, no cost.

Used when AI_MODE is "basic" (the default). It does plain, explainable matching:

- Fit comes from how many of the candidate's search keywords and CV-track terms
  appear in the job's title and description, and whether the title is at the
  candidate's level. Jobs restricted to a nationality the candidate doesn't hold
  score 0, as in the AI prompt (a Saudi candidate keeps "Saudi nationals only" jobs).
- "About the Role" is an excerpt of the real posting; "Why It Fits" lists what matched.
- The CV is the candidate's standard CV (approved facts only - the same content Demo
  Mode uses), headed with the job title, with the most relevant achievements and
  skills moved to the top. It is not rewritten per job; ChatGPT mode does that.
"""

from __future__ import annotations

import re

GENERIC = {"leader", "leadership", "management", "manager", "lead", "head", "senior", "director",
           "the", "of", "for", "and", "in", "to", "a"}
# One-word terms too broad to mean anything on their own (every industry has "projects").
BROAD = {"product", "products", "project", "projects", "program", "programme", "programs", "requirements",
         "delivery", "digital", "data", "strategy", "strategic", "business", "operations", "commercial",
         "growth", "marketing", "sales", "technology", "services", "solutions", "advisory"}
# Phrases any manager's posting uses: they don't show the job is in the candidate's field.
GENERIC_PHRASES = {"project management", "program management", "programme management", "stakeholder management",
                   "vendor management", "quality assurance", "delivery management", "ms project",
                   "people management", "team management", "budget management"}
NATIONALITY_RE = re.compile(
    r"\b(?:saudi|emirati|uae|qatari|kuwaiti|omani|bahraini|gcc)\s+nationals?\s+only\b"
    r"|\bonly\s+(?:saudi|emirati|uae|qatari|kuwaiti|gcc)\s+(?:nationals?|citizens?)\b"
    r"|\bmust\s+be\s+(?:a\s+)?(?:saudi|emirati|uae|qatari|kuwaiti)\s+(?:national|citizen)\b"
    r"|\b(?:saudi|emirati)\s+nationality\s+(?:is\s+)?(?:required|mandatory|a\s+must)\b"
    r"|\bfor\s+saudis?\s+only\b|\bsaudization\b",
    re.I,
)
# In a job title, naming a nationality always means the job is reserved for it: "Project Manager (Saudi National)".
TITLE_NATIONALITY_RE = re.compile(
    r"\b(?:saudi|emirati|qatari|kuwaiti|omani|bahraini|gcc)\s+nationals?\b|\bsaudis?\s+only\b|\bnationals?\s+only\b"
    r"|\(\s*saudis?\s*\)|للسعوديين|سعودي(?:ة)?\s+الجنسية", re.I)
NATIONALITY_REASON = "Skipped: the posting is open only to a specific nationality."
# Which nationals a restriction names, and which the person is (from what they wrote: "Saudi", "سعودية").
# Any GCC national passes "GCC nationals only"; "nationals only" alone means the searched country's.
NATIONALS = {
    "saudi": ("saudi", "ksa", "سعود"), "emirati": ("emirati", "uae", "إمارات", "اماراتي"),
    "qatari": ("qatari", "قطر"), "kuwaiti": ("kuwaiti", "كويت"), "omani": ("omani", "عمان", "عماني"),
    "bahraini": ("bahraini", "بحرين"), "egyptian": ("egyptian", "مصر"),
}
GCC = {"saudi", "emirati", "qatari", "kuwaiti", "omani", "bahraini"}
COUNTRY_NATIONALS = {"saudi arabia": "saudi", "united arab emirates": "emirati", "qatar": "qatari",
                     "kuwait": "kuwaiti", "oman": "omani", "bahrain": "bahraini", "egypt": "egyptian"}


def nationals_of(nationality: str) -> set[str]:
    """'Saudi' / 'Saudi Arabian' / 'سعودي' -> {'saudi', 'gcc'}; anything else -> what it names."""
    low = (nationality or "").lower()
    # English words from their start ("Romanian" isn't Omani); Arabic anywhere ("السعودية").
    found = {group for group, words in NATIONALS.items()
             if any(re.search(r"\b" + w, low) if w.isascii() else w in low for w in words)}
    return found | ({"gcc"} if found & GCC else set())


def restricted_to(title: str, description: str, country: str) -> list[set[str]]:
    """Each nationality restriction in a posting -> the nationals it is open to."""
    out = []
    for rx, text in ((NATIONALITY_RE, title), (TITLE_NATIONALITY_RE, title), (NATIONALITY_RE, description)):
        for m in rx.finditer(text):
            words = m.group(0)
            # "Saudi nationals only" is open to Saudis alone, not to every GCC national.
            named = (nationals_of(words) - {"gcc"}) | ({"gcc"} if "gcc" in words.lower() else set())
            if "saudization" in words.lower() or "للسعوديين" in words:
                named.add("saudi")
            out.append(named or {COUNTRY_NATIONALS.get(country.lower(), "saudi")})
    return out
LEVELS = (  # (pattern in the title, level) - first match wins
    (re.compile(r"\b(?:chief|c[efiotm]o|vice\s+president|vp|svp|evp|general\s+manager|head|managing\s+director)\b", re.I), "executive"),
    (re.compile(r"\b(?:director|associate\s+director)\b", re.I), "director"),
    (re.compile(r"\b(?:senior|sr\.?|lead|principal|manager|owner)\b", re.I), "mid-senior"),
)
JUNIOR_RE = re.compile(
    r"\b(?:analyst|specialist|coordinator|officer|assistant|administrator|intern|internship|junior|jr\.?|"
    r"trainee|graduate|representative|associate(?!\s+director))\b", re.I)
LEVEL_WORDS = {"executive": "an executive-level title", "director": "a director-level title",
               "mid-senior": "a senior-level title", "early": "an early-career title"}
LEVEL_ORDER = ["mid-senior", "director", "executive"]
EARLY = {"entry", "associate"}          # profiles that target first or early roles


def _term_re(term: str) -> re.Pattern:
    return re.compile(r"(?<![a-z0-9])" + re.escape(term.lower()) + r"(?![a-z0-9])", re.I)


def _phrases(name: str) -> list[str]:
    """Track name -> its distinctive phrases: 'Business Solutions & Strategic Advisory
    Leader' -> ['business solutions', 'strategic advisory']."""
    out = []
    for part in re.split(r"\s*(?:&|,|/|\band\b)\s*", name.lower()):
        words = [w for w in re.findall(r"[a-z][a-z\-]*", part) if w not in GENERIC]
        if words:
            out.append(" ".join(words))
    return out


def _stems(text: str) -> set[str]:
    return {w[:6] for w in re.findall(r"[a-z]{4,}", text.lower()) if w not in GENERIC}


# Words every posting uses: they say nothing about what this job needs.
FILLER = {"with", "will", "that", "this", "from", "have", "your", "their", "they", "them", "about", "able", "ability",
          "within", "across", "including", "such", "other", "more", "also", "work", "working", "team", "teams",
          "role", "roles", "company", "candidate", "candidates", "experience", "years", "year", "skills", "strong",
          "excellent", "good", "required", "requirement", "preferred", "responsibilities", "responsible",
          "qualifications", "ensure", "support", "provide", "using", "based", "join", "looking", "opportunity",
          "position", "level", "knowledge", "understanding", "must", "should", "would", "where", "which", "what",
          "when", "while", "into", "over", "through", "well", "high", "highly", "best", "great", "plus", "equal",
          "employer", "apply", "please", "salary", "benefits", "location", "saudi", "arabia", "riyadh", "jeddah",
          "dubai", "full", "time", "type", "employment", "industry", "function", "seniority", "job", "jobs",
          "managing", "manage", "lead", "leading"} | GENERIC
PLACES = r"riyadh|jeddah|dammam|khobar|dubai|abu\s+dhabi|doha|cairo|ksa|uae|gcc|mena|saudi\s+arabia|remote|hybrid|on-?site"


def _clean_title(title: str) -> str:
    """'Assistant Director - Market Activation - Riyadh (Req 1234)' -> 'Assistant Director - Market Activation':
    no city, work model, gender marker or requisition number, and at most two parts when it is long."""
    title = re.sub(r"\s*[\(\[][^)\]]*[\)\]]", "", title).strip()               # (m/f), (Riyadh), [12345]
    pieces = re.split(r"(\s+[-–—|]\s+|\s*,\s*)", title)
    parts, seps = [p.strip() for p in pieces[0::2]], ["" , *(", " if "," in s else " - " for s in pieces[1::2])]
    keep = [i for i, p in enumerate(parts) if p
            and not re.fullmatch(rf"(?:{PLACES})(?:\s*(?:region|,)?\s*(?:{PLACES}))*", p, re.I)
            and not re.fullmatch(r"(?:req|job|ref)?\s*#?\s*\d+", p, re.I)] or [i for i, p in enumerate(parts) if p]

    def join(idx):
        return "".join((seps[i] if n else "") + parts[i] for n, i in enumerate(idx))
    out = join(keep)
    return join(keep[:2]) if len(out) > 60 and len(keep) > 2 else out


def _weights(text: str) -> dict[str, int]:
    """How often each meaningful word stem appears in the posting."""
    counts: dict[str, int] = {}
    for w in re.findall(r"[a-z]{4,}", text.lower()):
        if w not in FILLER:
            counts[w[:7]] = counts.get(w[:7], 0) + 1      # 7 letters: "deliver(y)" match, "generat(ive)" != "general"
    return counts


class BasicAI:
    """Stands in for ChatGPT: the pipeline calls evaluate_jobs() and tailor()."""

    def __init__(self, candidate, pipeline):
        self.c = candidate
        self.ja = pipeline
        self.keywords = [(k, _term_re(k)) for k in candidate.keywords]
        track_keywords = getattr(candidate, "track_keywords", None) or {}
        titles = {k.lower() for k in candidate.keywords}
        self.tracks: dict[int, list[tuple[str, re.Pattern]]] = {}
        self.domain: dict[int, list[tuple[str, re.Pattern]]] = {}
        for n, name in candidate.track_names.items():
            terms = _phrases(name) + [k.lower() for k in track_keywords.get(n, [])]
            name_stems = _stems(name)
            terms += [k.lower() for k in candidate.keywords if _stems(k) & name_stems]   # search keywords near this track
            unique = [t for t in dict.fromkeys(t for t in terms if t) if t not in BROAD]
            self.tracks[n] = [(t, _term_re(t)) for t in unique]
            # Evidence the job is in the candidate's field: the track's specific terms, not job titles
            # (they're already in the title check) and not phrases every manager's posting uses.
            self.domain[n] = [(t, rx) for t, rx in self.tracks[n] if t not in titles and t not in GENERIC_PHRASES]
        # Words from the candidate's job titles ("product", "fintech", ...): a weaker title signal.
        self.title_words = [(w, _term_re(w)) for w in dict.fromkeys(
            w for k in candidate.keywords for w in re.findall(r"[a-z][a-z\-]+", k.lower())
            if w not in GENERIC and w not in {"project", "program", "programme"})]
        # url -> how its score was made, in plain parts the app shows under "Why this score".
        self.breakdowns: dict[str, dict] = {}
        self.levels = set(candidate.experience_levels)
        self.early = bool(self.levels & EARLY)
        # Words like "specialist" in the person's own target titles aren't "junior" for them.
        self.own_words = {w.lower() for k in candidate.keywords for w in JUNIOR_RE.findall(k)}
        self.nationals = nationals_of(getattr(candidate, "nationality", ""))
        self.country = getattr(candidate, "location", "") or getattr(pipeline, "LOCATION", "") or "Saudi Arabia"

    def closed_to_them(self, title: str, description: str) -> bool:
        """The posting is reserved for nationals the person isn't (a Saudi passes "Saudi nationals only")."""
        if not (NATIONALITY_RE.search(description) or NATIONALITY_RE.search(title) or TITLE_NATIONALITY_RE.search(title)):
            return False
        rules = restricted_to(title, description, self.country)
        return not rules or any(not (open_to & self.nationals) for open_to in rules)

    # --------------------------------------------------------------- scoring --
    def evaluate_jobs(self, batch: list[dict]):
        ja = self.ja
        return ja.BatchEvaluations(evaluations=[self._evaluate(job) for job in batch])

    def _level_fit(self, title: str) -> tuple[float, str | None]:
        level = next((lv for pattern, lv in LEVELS if pattern.search(title)), None)
        junior = any(w.lower() not in self.own_words for w in JUNIOR_RE.findall(title)) and level not in ("executive", "director")
        if self.early:
            # Early-career profile: junior titles are the target, director and above a stretch.
            if level in ("executive", "director") and not self.levels & {"director", "executive"}:
                return 0.5, level
            if junior or level is None:
                return 1.0, "early" if junior else None
            return (1.0 if level in self.levels else 0.8), level
        if junior:
            return 0.0, "junior"          # "Analyst", "Specialist", "Senior Analyst": below this profile
        if level is None:
            return 0.4, None
        if level in self.levels:
            return 1.0, level
        top = max((LEVEL_ORDER.index(lv) for lv in self.levels if lv in LEVEL_ORDER), default=0)
        return (0.6 if LEVEL_ORDER.index(level) > top else 0.7), level

    def _evaluate(self, job: dict):
        ja = self.ja
        title, description = job.get("title") or "", job.get("description") or ""
        if self.closed_to_them(title, description):
            self.breakdowns[job["url"]] = {"nationality": True}
            return ja.JobEvaluation(
                job_url=job["url"], ats_score=0, interview_score=0, fit_score=0, selected_track=min(self.tracks),
                secondary_track=None, track_selection_confidence="high", selected_track_reason=NATIONALITY_REASON,
                tailoring_level="light", summary=None, reasoning=NATIONALITY_REASON,
            )

        kw_title = [k for k, rx in self.keywords if rx.search(title)]
        scored = []
        for n, terms in self.tracks.items():
            in_title = [t for t, rx in terms if rx.search(title)]
            in_desc = [t for t, rx in self.domain[n] if rx.search(description)]
            scored.append((3 * len(in_title) + len(in_desc), n, in_title, in_desc))
        scored.sort(key=lambda s: (-s[0], s[1]))
        best_score, track, t_title, t_desc = scored[0]
        second = scored[1] if len(scored) > 1 and scored[1][0] > 0 else None
        # Field evidence counts across all tracks: a fintech PM posting may cite two tracks' terms.
        domain_hits = list(dict.fromkeys(t for n in self.domain for t, rx in self.domain[n] if rx.search(description)))

        level_fit, level = self._level_fit(title)
        word_hits = [w for w, rx in self.title_words if rx.search(title)]
        title_match = 1.0 if (kw_title or t_title) else 0.6 if word_hits else 0.0
        title_hits = len({k.lower() for k in kw_title} | set(t_title))
        described = len(description) >= 150
        if not described:
            # No description (Bayt never sends one, LinkedIn sometimes withholds it): only the title can be
            # judged. A real title match is not penalised; a shared word or no match keeps it below Good.
            ats = 50 + 12 * min(title_hits, 3) if title_hits else 35
            interview = 35 + round(35 * title_match) + round(30 * level_fit)
        else:
            # A matching title in another field (a construction "Project Manager" for a product
            # manager) shows none of the field's terms in its description: it stays below Good.
            in_field = 0.5 if not domain_hits else 1.0
            ats = 30 + 10 * min(len(domain_hits), 5) + (8 if title_match == 1.0 else 0)
            interview = 25 + round(35 * title_match * in_field) + round(30 * level_fit) + 10
        if level == "junior":
            ats, interview = ats - 15, interview - 25          # keeps it out of Strong / Good
        ats, interview = max(0, min(100, ats)), max(0, min(100, interview))
        fit = ja.weighted_fit(ats, interview)

        if second and best_score < 2 * second[0]:
            confidence = "medium" if best_score > second[0] else "low"
        else:
            confidence = "high" if best_score >= 3 else "medium" if best_score else "low"
        why = []
        if kw_title:
            why.append("The title matches " + ", ".join(kw_title[:2]))
        if domain_hits:
            why.append("the posting mentions " + ", ".join(domain_hits[:4]))
        elif len(description) >= 150:
            why.append("the posting shows little of this profile's field")
        if level == "junior":
            why.append("but the title is junior for this profile")
        elif level:
            why.append(LEVEL_WORDS[level])
        reasoning = ("; ".join(why) + ".") if why else "Few of the profile's keywords appear in this posting."
        reasoning = reasoning[0].upper() + reasoning[1:]
        self.breakdowns[job["url"]] = {
            "title": {"state": "match" if title_match == 1.0 else "partial" if title_match else "none",
                      "terms": (kw_title or t_title or word_hits)[:3]},
            "level": {"state": ("junior" if level == "junior" else "match" if level_fit >= 1.0
                                else "unclear" if level is None else "near"), "level": level or ""},
            "field": {"state": ("no_description" if not described else "match" if len(domain_hits) >= 2
                                else "few" if domain_hits else "none"), "terms": domain_hits[:6]},
        }
        return ja.JobEvaluation(
            job_url=job["url"], ats_score=ats, interview_score=interview, fit_score=fit, selected_track=track,
            secondary_track=second[1] if second else None, track_selection_confidence=confidence,
            selected_track_reason=f"Closest track by keywords: {self.c.track_names[track]}.",
            tailoring_level="light" if fit >= 80 else "moderate",
            summary=self._excerpt(description) if fit > ja.MODERATE_MIN - 1 else None,
            reasoning=reasoning if fit > ja.MODERATE_MIN - 1 else None,
        )

    @staticmethod
    def _excerpt(description: str, limit: int = 420) -> str | None:
        text = re.sub(r"\s+", " ", description).strip()
        if not text:
            return None
        if len(text) <= limit:
            return text
        cut = text[:limit]
        end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
        return cut[: end + 1] if end > limit * 0.5 else cut.rsplit(" ", 1)[0] + "…"

    # ------------------------------------------------------------------ CVs --
    def tailor(self, job: dict, track: int):
        """The person's own CV for this job - their headline, their summary, their roles with every
        point in the order they wrote it. Nothing is added or reworded: a CV that reads as written by
        a template (a posting's title as the headline, a stock closing sentence, shuffled points) costs
        interviews. The one change per job is invisible: the skills this posting asks for come first."""
        ja = self.ja
        content = getattr(self.c, "cv_content", None)
        base = content() if content else ja.standard_cv(self.c.key)
        title = _clean_title(re.sub(r"\s+", " ", job.get("title") or "").strip()) or "Target Role"
        description = job.get("description") or ""
        posting = f"{title}\n{description}"
        weights = _weights(f"{title}\n{title}\n{title}\n{description}")      # the title counts three times
        broad = {w[:7] for w in BROAD}

        sep = next((s for s in (" | ", " · ", " • ", ", ") if s in base.get("competencies", "")), None)
        skills = list(base.get("skills") or [s.strip() for s in (base.get("competencies", "").split(sep) if sep
                                                                     else [base.get("competencies", "")]) if s.strip()])

        def stems(text: str) -> list[str]:
            return list(dict.fromkeys(w[:7] for w in re.findall(r"[a-z]{4,}", text.lower()) if w not in FILLER))

        # The person's skills this posting asks for, strongest first: named outright, or (for a phrase like
        # "Requirements & Acceptance") its words all there, or most of them with at least one specific word.
        def skill_score(skill: str) -> int:
            named = len(_term_re(skill).findall(posting))
            words = stems(skill)
            found = [w for w in words if weights.get(w)]
            whole = bool(words) and len(found) == len(words)
            most = len(found) * 2 >= len(words) and any(w not in broad for w in found)
            if not (named or whole or most):
                return 0
            return named * 3 + sum(weights[w] for w in found)
        asked = sorted((s for s in skills if skill_score(s)), key=skill_score, reverse=True)

        # Skills in groups ("Core: HTML5, CSS3") keep the person's order; single skills lead with the asked ones.
        grouped = any(re.match(r"^[^:]{2,40}:\s", s) for s in skills)
        competencies = list(skills) if grouped else asked + [s for s in skills if s not in asked]
        return ja.TailoredCV(
            headline=base.get("pillar") or (skills[0] if skills else title),
            about_paragraphs=[p for p in base.get("about", []) if p],
            achievements_title=base.get("achievements_title") or "Key Achievements:",
            key_achievements=list(base.get("achievements", [])),
            work_experience=[ja.WorkExperienceEntry(**dict(e)) for e in base.get("experience", [])],
            core_competencies=" | ".join(competencies[:12]),     # more reads as keyword stuffing
        )
