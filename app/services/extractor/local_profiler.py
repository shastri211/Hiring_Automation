import re
from typing import Dict, Any, List, Optional, Tuple

from app.core.config import settings


# ---------------------------------------------------------------------------
# Section-header normalization helpers
# ---------------------------------------------------------------------------

def _normalize_header(raw: str) -> str:
    """Lower-case, strip whitespace and trailing punctuation (colons, dots)."""
    return raw.strip().lower().rstrip(":.")


# Canonical section key → set of normalised variants that map to it.
# All values are already lower-cased and punctuation-stripped.
_SECTION_MAP: Dict[str, List[str]] = {
    "experience": [
        "experience",
        "work experience",
        "professional experience",
        "employment",
        "employment history",
        "work history",
        "career history",
        "career summary",
        "professional background",
        "relevant experience",
        "internship experience",
        "internships",
    ],
    "education": [
        "education",
        "educational background",
        "academic background",
        "academic qualifications",
        "qualifications",
        "academic history",
        "academic credentials",
    ],
    "skills": [
        "skills",
        "technical skills",
        "core skills",
        "core competencies",
        "competencies",
        "technologies",
        "technical expertise",
        "technology stack",
        "tools and technologies",
        "tools & technologies",
        "skills & technologies",
        "skills and technologies",
        "programming skills",
        "languages and technologies",
        "languages & technologies",
        "key skills",
        "professional skills",
        "it skills",
        "areas of expertise",
        "expertise",
    ],
    "projects": [
        "projects",
        "key projects",
        "selected projects",
        "notable projects",
        "personal projects",
        "side projects",
        "academic projects",
        "portfolio",
        "project highlights",
        "relevant projects",
    ],
    "summary": [
        "summary",
        "professional summary",
        "profile summary",
        "career objective",
        "objective",
        "career summary",
        "about me",
        "overview",
        "profile",
        "professional profile",
        "executive summary",
    ],
    "certifications": [
        "certifications",
        "certificates",
        "certification",
        "professional certifications",
        "licenses",
        "licenses & certifications",
    ],
    "languages": [
        "languages",
        "language proficiency",
        "language skills",
    ],
    "achievements": [
        "achievements",
        "awards",
        "honors",
        "honours",
        "accomplishments",
        "recognition",
    ],
}

# Build a flat lookup: normalised variant → canonical section key
_HEADER_LOOKUP: Dict[str, str] = {}
for _canonical, _variants in _SECTION_MAP.items():
    for _v in _variants:
        _HEADER_LOOKUP[_v] = _canonical

# Maximum line length to still be considered a possible section header.
_MAX_HEADER_LEN = 60

# ---------------------------------------------------------------------------
# Bullet / noise patterns
# ---------------------------------------------------------------------------

# Bullet symbols that should not appear as skills / standalone content.
_BULLET_RE = re.compile(r"^[\u2022\u25e6\u25aa\u25cf\u2023\u2043\u2219\u25b8\u2027\-\*•▪◦‣⁃]+\s*$")

# Contact / metadata patterns (used to reject these lines as candidate names).
_CONTACT_RE = re.compile(
    r"@|linkedin\.com|github\.com|http|www\.|\.com|\.in|\.org"
    r"|\+\d|\d{8,}|/in/|\|",
    re.IGNORECASE,
)

# Phone patterns
_PHONE_RE = re.compile(r"\+?\d[\d\s\-().]{7,}\d")
# Email
_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}")

# Date range patterns (for experience entries)
_DATE_RANGE_RE = re.compile(
    r"""
    (?:
        (?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*
        \s*[,\.]?\s*
        (?:19|20)\d{2}
    )
    |(?:(?:19|20)\d{2}\s*[-–—to]+\s*(?:(?:19|20)\d{2}|present|current|now|date))
    |(?:\d{1,2}/\d{4}\s*[-–—to]+\s*(?:\d{1,2}/\d{4}|present|current))
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Lone year (used for education)
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


class LocalProfilerService:
    """
    Deterministically structures extracted resume text into:
    - a local_profile dict (matches CandidateProfile DB model fields)
    - a canonical_text for embedding (near-zero information loss)
    - a confidence dict (with is_insufficient flag)

    All extraction is heuristic and conservative: fields are left
    null/empty when evidence is absent or ambiguous.
    """

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    @classmethod
    def profile_candidate(
        cls, extracted_text: str
    ) -> Tuple[Dict[str, Any], str, Dict[str, Any]]:
        """
        Parse extracted resume text.

        Returns
        -------
        local_profile : dict
            Keys: name, summary, skills, experience, education, projects.
            All values are derived deterministically; nothing is fabricated.
        canonical_text : str
            Full resume content preserved and categorised for embedding.
        confidence : dict
            Numeric score + boolean flags + is_insufficient sentinel.
        """
        if not extracted_text or not extracted_text.strip():
            return {}, "", {"is_insufficient": True, "reason": "empty", "score": 0}

        sections = cls._segment_text(extracted_text)
        canonical_text = cls._build_canonical_text(extracted_text, sections)

        local_profile = {
            "name": cls._extract_name(extracted_text, sections),
            "summary": cls._extract_summary(sections),
            "skills": cls._extract_skills(sections.get("skills", "")),
            "experience": cls._extract_experience(sections.get("experience", "")),
            "education": cls._extract_education(sections.get("education", "")),
            "projects": cls._extract_projects(sections.get("projects", "")),
        }

        confidence = cls._calculate_confidence(extracted_text, sections, local_profile)
        return local_profile, canonical_text, confidence

    @classmethod
    def profile_job(cls, job_text: str) -> str:
        """Return canonical text for a job description (for embedding)."""
        sections = cls._segment_text(job_text)
        return cls._build_canonical_text(job_text, sections)

    # ------------------------------------------------------------------ #
    # Section segmentation                                                 #
    # ------------------------------------------------------------------ #

    @classmethod
    def _segment_text(cls, text: str) -> Dict[str, str]:
        """
        Split text into labelled sections using normalised header matching.

        - Tolerates UPPER/lower/Mixed case.
        - Tolerates trailing colons and whitespace.
        - Header line must be ≤ _MAX_HEADER_LEN characters.
        - When a header is recognised, content following it is bucketed
          under the canonical section name.
        - Unrecognised content before any header (and any unmatched lines)
          go into 'unclassified'.
        """
        sections: Dict[str, List[str]] = {"unclassified": []}
        current_section = "unclassified"

        for line in text.split("\n"):
            stripped = line.strip()
            if len(stripped) <= _MAX_HEADER_LEN:
                canonical = _HEADER_LOOKUP.get(_normalize_header(stripped))
                if canonical:
                    current_section = canonical
                    if current_section not in sections:
                        sections[current_section] = []
                    continue  # do not add the header line as content

            sections[current_section].append(line)

        # Collapse lists to strings, drop empty sections
        return {
            k: "\n".join(v).strip()
            for k, v in sections.items()
            if "\n".join(v).strip()
        }

    # ------------------------------------------------------------------ #
    # Canonical text                                                       #
    # ------------------------------------------------------------------ #

    @classmethod
    def _build_canonical_text(
        cls, original_text: str, sections: Dict[str, str]
    ) -> str:
        """
        Build the canonical embedding text.

        Design contract:
        'Do not discard useful source text. Parsed/labeled sections may be
        added, but canonical_text must preserve the complete relevant
        extracted resume information.'

        Strategy: emit each section with its label.  'unclassified'
        contains whatever could not be bucketed; it is always included so
        that misclassified experience / summary text is still embedded.
        """
        parts = []
        for sec_name, content in sections.items():
            if content.strip():
                label = f"[{sec_name.upper()}]"
                parts.append(f"{label}\n{content}")
        return "\n\n".join(parts)

    # ------------------------------------------------------------------ #
    # Name extraction                                                      #
    # ------------------------------------------------------------------ #

    # Patterns that disqualify a line from being a name.
    _NAME_REJECT_RE = re.compile(
        r"@|http|www\.|linkedin|github|\.com|\.in|\.org"
        r"|\+?\d[\d\s\-]{6,}"   # phone-like
        r"|\|"                   # contact separator
        r"|\d{4}",               # years
        re.IGNORECASE,
    )
    # A name line should contain only letters, spaces, hyphens, apostrophes, dots.
    _NAME_CHARS_RE = re.compile(r"^[A-Za-z][A-Za-z\s\-\.']{1,50}$")

    @classmethod
    def _extract_name(cls, text: str, sections: Dict[str, str]) -> Optional[str]:
        """
        Heuristically extract the candidate's name from the first few lines.

        Rules (conservative):
        1. Only inspect the first 10 non-empty lines of the document.
        2. Reject lines that look like contact info, URLs, or section headers.
        3. Prefer ALL-CAPS or Title-Case lines with 2-5 words.
        4. Return None rather than a wrong guess.
        """
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        candidates = []

        known_headers = set(_HEADER_LOOKUP.keys())

        for line in lines[:10]:
            if cls._NAME_REJECT_RE.search(line):
                continue
            if _normalize_header(line) in known_headers:
                continue
            if len(line) > 60:
                continue
            # Must look like words (letters, spaces, hyphens)
            if not cls._NAME_CHARS_RE.match(line):
                continue
            words = line.split()
            if len(words) < 2 or len(words) > 5:
                continue
            candidates.append(line)

        if not candidates:
            return None

        # Prefer the first candidate that is ALL-CAPS or Title-Case
        for cand in candidates:
            words = cand.split()
            if all(w.isupper() for w in words) or all(w.istitle() for w in words):
                return cand.title()

        # Fall back to first candidate, normalised to title case
        return candidates[0].title()

    # ------------------------------------------------------------------ #
    # Summary extraction                                                   #
    # ------------------------------------------------------------------ #

    @classmethod
    def _extract_summary(cls, sections: Dict[str, str]) -> Optional[str]:
        text = sections.get("summary", "").strip()
        return text if text else None

    # ------------------------------------------------------------------ #
    # Skills extraction                                                    #
    # ------------------------------------------------------------------ #

    _BULLET_CHARS_RE = re.compile(
        r"^[\u2022\u25e6\u25aa\u25cf\u2023\u2043\u2219\u25b8\u2027\-\*\*•▪◦‣⁃]+\s*"
    )

    @classmethod
    def _extract_skills(cls, skills_text: str) -> List[str]:
        """
        Split skills on commas and newlines; strip bullet symbols and
        surrounding whitespace; reject empty or pure-bullet tokens.
        """
        if not skills_text:
            return []

        raw_tokens = re.split(r"[,\n]", skills_text)
        skills: List[str] = []
        for tok in raw_tokens:
            # Strip leading bullet characters
            cleaned = cls._BULLET_CHARS_RE.sub("", tok).strip()
            # Skip empty, pure-bullet, or excessively long tokens
            if not cleaned:
                continue
            if _BULLET_RE.match(cleaned):
                continue
            if len(cleaned) > 80:
                continue
            skills.append(cleaned)
        return skills

    # ------------------------------------------------------------------ #
    # Experience extraction                                                #
    # ------------------------------------------------------------------ #

    @classmethod
    def _extract_experience(cls, exp_text: str) -> List[Dict[str, Any]]:
        """
        Parse experience section into a list of structured records.

        Each record: {role, company, duration, description}

        Strategy:
        - Split into logical blocks (separated by blank lines or date lines).
        - First line of each block → role/company.
        - Any line matching date pattern → duration.
        - Remaining lines → description.
        - Leave fields None when not confidently identifiable.
        """
        if not exp_text or len(exp_text.strip()) < 10:
            return []

        entries: List[Dict[str, Any]] = []
        current: Optional[Dict[str, Any]] = None
        desc_lines: List[str] = []
        is_first_content = True

        def _flush(entry, desc):
            if entry is None:
                return
            d = "\n".join(
                line.strip()
                for line in desc
                if line.strip() and not _BULLET_RE.match(line.strip())
            ).strip()
            entry["description"] = d if d else None
            entries.append(entry)

        lines = exp_text.split("\n")

        for raw_line in lines:
            line = raw_line.strip()

            if not line:
                # Blank line → potential entry boundary
                if current and desc_lines:
                    _flush(current, desc_lines)
                    current = None
                    desc_lines = []
                    is_first_content = True
                continue

            # Strip leading bullet chars for content analysis
            line_clean = cls._BULLET_CHARS_RE.sub("", line).strip()
            if not line_clean:
                continue

            date_match = _DATE_RANGE_RE.search(line_clean)

            if date_match:
                if current is None:
                    # Date before any role line → start a new entry
                    current = {"role": None, "company": None,
                               "duration": None, "description": None}
                    is_first_content = False
                current["duration"] = line_clean
                continue

            if is_first_content and current is None:
                # First substantive line of a block → role / company
                current = {
                    "role": None,
                    "company": None,
                    "duration": None,
                    "description": None,
                }
                role, company = cls._split_role_company(line_clean)
                current["role"] = role
                current["company"] = company
                is_first_content = False
                continue

            if current is not None:
                desc_lines.append(line_clean)

        _flush(current, desc_lines)

        # Remove entirely empty entries
        return [e for e in entries if any(v for v in e.values())]

    @staticmethod
    def _split_role_company(line: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Try to split 'Role  |  Company' or 'Role at Company' or
        'Role — Company' into (role, company).
        Returns (full_line, None) when no separator is confidently found.
        """
        # Common separators: pipe, em-dash, en-dash, 'at', comma
        for sep_re in [
            re.compile(r"\s*\|\s*"),
            re.compile(r"\s*[—–]\s*"),
            re.compile(r"\s+at\s+", re.IGNORECASE),
        ]:
            parts = sep_re.split(line, maxsplit=1)
            if len(parts) == 2 and parts[0].strip() and parts[1].strip():
                return parts[0].strip(), parts[1].strip()
        return line, None

    # ------------------------------------------------------------------ #
    # Education extraction                                                 #
    # ------------------------------------------------------------------ #

    @classmethod
    def _extract_education(cls, edu_text: str) -> List[Dict[str, Any]]:
        """
        Parse education section into a list of records.

        Each record: {degree, institution, year}
        Strategy: each non-empty line or small block is a potential entry.
        """
        if not edu_text or len(edu_text.strip()) < 5:
            return []

        entries: List[Dict[str, Any]] = []
        lines = [
            cls._BULLET_CHARS_RE.sub("", l).strip()
            for l in edu_text.split("\n")
            if l.strip()
        ]

        i = 0
        while i < len(lines):
            line = lines[i]
            if not line:
                i += 1
                continue

            year_m = _YEAR_RE.search(line)
            year = year_m.group(0) if year_m else None

            # Look ahead for institution on next line if current is degree-like
            degree = None
            institution = None

            # Heuristic: if line is longer and contains degree keywords → degree line
            degree_kw = re.compile(
                r"\b(b\.?tech|m\.?tech|b\.?sc|m\.?sc|b\.?com|m\.?com|b\.?a\b|m\.?a\b"
                r"|bachelor|master|phd|ph\.d|doctorate|diploma|certificate"
                r"|engineering|science|arts|commerce|technology)\b",
                re.IGNORECASE,
            )
            if degree_kw.search(line):
                degree = line
                # Try to get institution from next line
                if i + 1 < len(lines) and not degree_kw.search(lines[i + 1]):
                    nxt = lines[i + 1]
                    if nxt and not _YEAR_RE.match(nxt):
                        institution = nxt
                        year = year or (_YEAR_RE.search(nxt) and _YEAR_RE.search(nxt).group(0))
                        i += 1
            else:
                # Treat line as institution; look ahead for degree
                institution = line

            entry = {
                "degree": degree,
                "institution": institution,
                "year": year,
            }
            if any(v for v in entry.values()):
                entries.append(entry)
            i += 1

        return entries

    # ------------------------------------------------------------------ #
    # Project extraction                                                   #
    # ------------------------------------------------------------------ #

    @classmethod
    def _extract_projects(cls, proj_text: str) -> List[Dict[str, Any]]:
        """
        Parse projects section into a list of records.

        Each record: {name, description, technologies}

        Strategy:
        - A project name is a short (≤ 60 chars), capitalised line that
          does not look like a sentence (i.e., it does not end with a full
          stop or start with a lowercase word) and is not a date line.
        - Everything else until the next project name → description.
        - Lines matching '(tech, tech, ...)' or 'Technologies: ...' → techs.
        """
        if not proj_text or len(proj_text.strip()) < 5:
            return []

        tech_line_re = re.compile(
            r"(?:technologies?|tech stack|tools?|built with|stack)\s*[:\-]?\s*(.+)",
            re.IGNORECASE,
        )
        # Pattern for a parenthesised tech list at end of project name
        tech_paren_re = re.compile(r"\(([^)]{3,})\)\s*$")

        # A line looks like a sentence / description if it:
        # - ends with '.', '!', '?'  OR
        # - starts with a lowercase letter (continuation prose)  OR
        # - is longer than 60 chars
        _DESCRIPTION_RE = re.compile(
            r"[.!?]$"    # ends in sentence terminator
            r"|^[a-z]"   # starts with lowercase (verb phrase / continuation)
        )

        entries: List[Dict[str, Any]] = []
        current: Optional[Dict[str, Any]] = None
        desc_lines: List[str] = []

        def _flush_proj(entry, desc):
            if entry is None:
                return
            d = " ".join(
                l.strip()
                for l in desc
                if l.strip() and not _BULLET_RE.match(l.strip())
            ).strip()
            entry["description"] = d if d else None
            entries.append(entry)

        for raw_line in proj_text.split("\n"):
            line = raw_line.strip()
            if not line:
                continue

            line_clean = cls._BULLET_CHARS_RE.sub("", line).strip()
            if not line_clean:
                continue

            # Technology annotation
            tech_m = tech_line_re.match(line_clean)
            if tech_m and current is not None:
                techs = [t.strip() for t in re.split(r"[,/]", tech_m.group(1)) if t.strip()]
                current["technologies"] = techs
                continue

            # Decide: description line or new project name?
            # A line with a trailing parenthesised tech list is always a
            # project-name line, regardless of total length.
            has_tech_paren = bool(tech_paren_re.search(line_clean))
            is_description_line = (
                not has_tech_paren
                and (
                    len(line_clean) > 60
                    or bool(_DESCRIPTION_RE.search(line_clean))
                )
            ) or (
                _DATE_RANGE_RE.search(line_clean) is not None
                or _BULLET_RE.match(line_clean) is not None
                or line_clean.lower().startswith("http")
                or line_clean.lower().startswith("www")
            )

            if not is_description_line and len(line_clean) <= 120:
                # New project name
                _flush_proj(current, desc_lines)
                current = {"name": None, "description": None, "technologies": []}
                desc_lines = []

                # Extract parenthesised tech from project name line
                p_m = tech_paren_re.search(line_clean)
                if p_m:
                    techs = [t.strip() for t in re.split(r"[,/]", p_m.group(1)) if t.strip()]
                    current["technologies"] = techs
                    line_clean = tech_paren_re.sub("", line_clean).strip()

                current["name"] = line_clean
                continue

            # Otherwise treat as description / tech detail
            if current is not None:
                desc_lines.append(line_clean)

        _flush_proj(current, desc_lines)
        return [e for e in entries if e.get("name")]

    # ------------------------------------------------------------------ #
    # Confidence scoring                                                   #
    # ------------------------------------------------------------------ #

    @classmethod
    def _calculate_confidence(
        cls,
        original_text: str,
        sections: Dict[str, str],
        local_profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Score document understanding quality.

        Points are awarded for *extracted* structured content, not merely
        for text length or the presence of contact information.

        Max reachable = 95.  Threshold for is_insufficient is
        settings.LOCAL_PROFILE_CONFIDENCE_THRESHOLD (default 45).
        """
        text_length = len(original_text.strip())

        # --- text presence (up to 20 pts) ---
        score = 0
        if text_length > 200:
            score += 10
        if text_length > 1000:
            score += 10

        # --- structured field quality (up to 80 pts) ---
        exp_entries = local_profile.get("experience") or []
        has_experience = len(exp_entries) > 0
        if has_experience:
            score += 20

        skills_list = local_profile.get("skills") or []
        has_skills = len(skills_list) >= 2
        if has_skills:
            score += 15

        edu_entries = local_profile.get("education") or []
        has_education = len(edu_entries) > 0
        if has_education:
            score += 15

        # Dates: search across experience section AND unclassified
        # (handles cases where experience text is in unclassified due to
        #  header mismatch in the raw PDF)
        date_search_text = " ".join([
            sections.get("experience", ""),
            sections.get("unclassified", ""),
        ]).lower()
        has_dates = bool(_DATE_RANGE_RE.search(date_search_text))
        if has_dates:
            score += 10

        # Projects present
        proj_entries = local_profile.get("projects") or []
        if proj_entries:
            score += 5

        # Name found
        if local_profile.get("name"):
            score += 5

        is_insufficient = score < settings.LOCAL_PROFILE_CONFIDENCE_THRESHOLD

        return {
            "score": score,
            "text_length": text_length,
            "has_experience": has_experience,
            "has_skills": has_skills,
            "has_education": has_education,
            "has_dates": has_dates,
            "is_insufficient": is_insufficient,
        }
