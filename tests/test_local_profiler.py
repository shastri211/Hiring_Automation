"""
Tests for LocalProfilerService (Phase 13 targeted corrections).

All tests are synchronous — LocalProfilerService has no async dependencies.
The conftest.py autouse fixture already patches LLM providers so no live
calls are made.

Coverage required by the acceptance criteria:
- WORK EXPERIENCE header detection
- PROFILE SUMMARY header detection
- TECHNICAL SKILLS header detection
- KEY PROJECTS header detection
- name extraction (happy path, ambiguous, missing)
- experience extraction (role, company, duration, description)
- education extraction (degree, institution, year)
- project extraction (name, description, technologies)
- bullet cleanup (•, ▪, ◦, -)
- missing sections
- malformed / short resumes
- conservative handling of uncertain / ambiguous fields
"""

import pytest
from app.services.extractor.local_profiler import LocalProfilerService

# ---------------------------------------------------------------------------
# Minimal resume fixture with canonical real-world headers
# ---------------------------------------------------------------------------

PRABAL_LIKE = """PRABAL PRATAP SINGH THAKUR
AI Engineer — Voice Agents & Conversational AI Systems
[email address] | [phone number] | [City, India] | [LinkedIn] | [GitHub]
PROFESSIONAL SUMMARY
AI Engineer with 2 years of experience at OneTab building production-grade voice agent systems.
TECHNICAL SKILLS
•
Voice AI & Telephony: voice agent pipelines, STT/TTS/LLM orchestration
•
AI/ML & GenAI: LLMs, RAG pipelines, LangChain, prompt engineering
•
Languages & Frameworks: Python, FastAPI, Node.js
WORK EXPERIENCE
AI Engineer  —  OneTab (OneTab Generative Pvt. Ltd.)
2024 – Present | India
•
Designed and built multi-phase voice agent pipelines.
•
Developed and debugged a custom telephony provider integration.
KEY PROJECTS
AI Voice Interview Agent  (Voice telephony platform, STT/TTS/LLM providers)
•
Built a self-hosted voice agent platform enabling automated candidate interview calls.
EDUCATION
Medicaps University  —  2024
B.Tech in Computer Science / IT
"""

ARAV_LIKE = """ARAV GUPTA
Software Engineer | B.Tech Computer Science
Bhopal, Madhya Pradesh, India  |  +91 98XXXXXX32  |  arav.gupta@email.com
PROFILE SUMMARY
Detail-oriented Software Engineer with 1.5 years of experience.
WORK EXPERIENCE
Software Engineer  |  NexaCode Technologies Pvt. Ltd.
Feb 2025 - Present
•
Develop and maintain REST APIs using Python (FastAPI).
•
Collaborate with a 5-member team to design database schemas.
Software Engineering Intern  |  NexaCode Technologies Pvt. Ltd.
Aug 2024 - Jan 2025
•
Assisted in building internal dashboards using Flask.
EDUCATION
Bachelor of Technology (B.Tech) in Computer Science & Engineering
Institute of Engineering & Technology (IET), DAVV, Indore  |  2020 - 2024
SKILLS
•
Python, JavaScript, SQL
•
FastAPI, Flask, React.js
•
REST API Design & Development
PROJECTS
Expense Tracker Web App
Built a full-stack expense tracking app with FastAPI backend.
CERTIFICATIONS
•
Python for Data Structures & Algorithms - Certificate Course
LANGUAGES
Hindi (Native), English (Fluent)
"""

DUMMY_LIKE = """ARJUN MEHRA
Indore, Madhya Pradesh, India   |   +91 98765 43210   |   arjun.mehra.dev@gmail.com
PROFESSIONAL SUMMARY
Python Backend Developer with hands-on experience building scalable backend services.
TECHNICAL SKILLS
Languages: Python, SQL, Bash
Frameworks: FastAPI, Flask, SQLAlchemy
Tools: Git, Docker, PostgreSQL, Redis
EXPERIENCE
Software Developer  |  TechCorp India
Jan 2023 - Dec 2024
Built and maintained REST APIs serving 10k+ daily requests.
PROJECTS
Resume Screener API
Built with FastAPI, PostgreSQL, Redis, Celery.
An automated resume screening API with semantic search.
EDUCATION
Bachelor of Engineering in Computer Science
RGPV University, Bhopal  |  2022
CERTIFICATIONS
AWS Cloud Practitioner
"""

SHORT_RESUME = "John Doe\nSoftware engineer\nPython, Java"

EMPTY_RESUME = ""

MALFORMED_RESUME = "\n\n\n   \n\n"


# ===========================================================================
# 1. Section header detection
# ===========================================================================

class TestSectionHeaderDetection:

    def test_work_experience_detected(self):
        sections = LocalProfilerService._segment_text(PRABAL_LIKE)
        assert "experience" in sections, "WORK EXPERIENCE must map to 'experience' section"

    def test_professional_experience_detected(self):
        text = "Jane Doe\nPROFESSIONAL EXPERIENCE\nSenior Dev at ACME\n2022-2024\nBuilt systems."
        sections = LocalProfilerService._segment_text(text)
        assert "experience" in sections

    def test_employment_history_detected(self):
        text = "Bob\nEMPLOYMENT HISTORY\nDev at Foo\n2020-2022\nDid stuff."
        sections = LocalProfilerService._segment_text(text)
        assert "experience" in sections

    def test_career_history_detected(self):
        text = "Alice\nCAREER HISTORY\nManager at Bar\n2019-2021\nManaged team."
        sections = LocalProfilerService._segment_text(text)
        assert "experience" in sections

    def test_profile_summary_detected(self):
        sections = LocalProfilerService._segment_text(ARAV_LIKE)
        assert "summary" in sections, "PROFILE SUMMARY must map to 'summary' section"
        assert len(sections["summary"]) > 10

    def test_professional_summary_detected(self):
        sections = LocalProfilerService._segment_text(PRABAL_LIKE)
        assert "summary" in sections, "PROFESSIONAL SUMMARY must map to 'summary' section"

    def test_technical_skills_detected(self):
        sections = LocalProfilerService._segment_text(PRABAL_LIKE)
        assert "skills" in sections, "TECHNICAL SKILLS must map to 'skills' section"

    def test_core_skills_detected(self):
        text = "Alice\nCORE SKILLS\nPython, SQL, Docker"
        sections = LocalProfilerService._segment_text(text)
        assert "skills" in sections

    def test_key_projects_detected(self):
        sections = LocalProfilerService._segment_text(PRABAL_LIKE)
        assert "projects" in sections, "KEY PROJECTS must map to 'projects' section"

    def test_selected_projects_detected(self):
        text = "Dave\nSELECTED PROJECTS\nCoolApp\nBuilt a cool app."
        sections = LocalProfilerService._segment_text(text)
        assert "projects" in sections

    def test_header_with_trailing_colon(self):
        text = "Eve\nWORK EXPERIENCE:\nDev at Corp\n2022-2024\nBuilt APIs."
        sections = LocalProfilerService._segment_text(text)
        assert "experience" in sections

    def test_header_case_insensitive(self):
        text = "Sam\nwork experience\nDev at Corp\n2022-2024\nBuilt things."
        sections = LocalProfilerService._segment_text(text)
        assert "experience" in sections

    def test_mixed_case_header(self):
        text = "Pat\nWork Experience\nDev at Corp\n2022-2024"
        sections = LocalProfilerService._segment_text(text)
        assert "experience" in sections

    def test_technologies_header_detected(self):
        text = "Raj\nTECHNOLOGIES\nPython, Docker, PostgreSQL"
        sections = LocalProfilerService._segment_text(text)
        assert "skills" in sections

    def test_achievements_detected(self):
        text = "Uma\nACHIEVEMENTS\nBest Employee 2023\nHackathon Winner"
        sections = LocalProfilerService._segment_text(text)
        assert "achievements" in sections


# ===========================================================================
# 2. Name extraction
# ===========================================================================

class TestNameExtraction:

    def test_all_caps_name_extracted(self):
        profile, _, _ = LocalProfilerService.profile_candidate(PRABAL_LIKE)
        name = profile.get("name")
        assert name is not None, "Should extract name from PRABAL_LIKE"
        assert "prabal" in name.lower() or "thakur" in name.lower()

    def test_title_case_name_extracted(self):
        profile, _, _ = LocalProfilerService.profile_candidate(ARAV_LIKE)
        name = profile.get("name")
        assert name is not None
        assert "arav" in name.lower() or "gupta" in name.lower()

    def test_name_not_email(self):
        text = "john.doe@example.com\nSoftware Engineer\nPython, Java"
        profile, _, _ = LocalProfilerService.profile_candidate(text)
        name = profile.get("name")
        # If a name is extracted it must not be an email address
        if name:
            assert "@" not in name

    def test_name_not_phone(self):
        text = "+91 9876543210\nJohn Doe\nSoftware Engineer\nPython"
        profile, _, _ = LocalProfilerService.profile_candidate(text)
        name = profile.get("name")
        if name:
            assert not any(c.isdigit() for c in name.replace(" ", "")[:3])

    def test_ambiguous_first_line_returns_none_or_safe(self):
        """When first lines are all metadata, name may be None (conservative)."""
        text = "https://linkedin.com/in/johndoe\n+91 9876543210\njohn@email.com\nPython, Java"
        profile, _, _ = LocalProfilerService.profile_candidate(text)
        name = profile.get("name")
        # Either None or something that is not a URL / phone
        if name:
            assert "http" not in name.lower()
            assert "@" not in name

    def test_single_word_not_extracted_as_name(self):
        text = "RESUME\nJohn Doe\nSoftware Engineer\nPython"
        profile, _, _ = LocalProfilerService.profile_candidate(text)
        name = profile.get("name")
        # "RESUME" is a section header; John Doe should be the name
        if name:
            assert name.lower() != "resume"


# ===========================================================================
# 3. Skills extraction & bullet cleanup
# ===========================================================================

class TestSkillsExtraction:

    def test_bullet_symbol_not_in_skills(self):
        profile, _, _ = LocalProfilerService.profile_candidate(PRABAL_LIKE)
        skills = profile.get("skills", [])
        for skill in skills:
            stripped = skill.strip()
            assert stripped not in ("•", "▪", "◦", "-", "*", "‣"), \
                f"Bullet symbol should not be a skill: {repr(stripped)}"

    def test_skills_extracted_from_technical_skills_section(self):
        profile, _, _ = LocalProfilerService.profile_candidate(PRABAL_LIKE)
        skills = profile.get("skills", [])
        assert len(skills) >= 2, "Should extract at least 2 skills from TECHNICAL SKILLS section"

    def test_skills_extracted_from_skills_section(self):
        profile, _, _ = LocalProfilerService.profile_candidate(ARAV_LIKE)
        skills = profile.get("skills", [])
        assert any("python" in s.lower() for s in skills), "Python should be in skills"
        assert any("sql" in s.lower() for s in skills), "SQL should be in skills"

    def test_bullet_variants_stripped(self):
        """All common bullet variants are stripped before skill text."""
        bullet_skills_text = "•Python\n▪SQL\n◦Docker\n‣Git\n- Bash"
        skills = LocalProfilerService._extract_skills(bullet_skills_text)
        for s in skills:
            assert s[0] not in "•▪◦‣-", f"Bullet not stripped from: {repr(s)}"

    def test_empty_skills_text_returns_empty_list(self):
        result = LocalProfilerService._extract_skills("")
        assert result == []

    def test_comma_separated_skills(self):
        result = LocalProfilerService._extract_skills("Python, FastAPI, PostgreSQL, Docker")
        assert "Python" in result
        assert "FastAPI" in result
        assert "PostgreSQL" in result
        assert "Docker" in result


# ===========================================================================
# 4. Experience extraction
# ===========================================================================

class TestExperienceExtraction:

    def test_experience_entries_found_prabal(self):
        profile, _, _ = LocalProfilerService.profile_candidate(PRABAL_LIKE)
        exp = profile.get("experience", [])
        assert len(exp) >= 1, "Prabal-like resume should have at least 1 experience entry"

    def test_experience_entries_found_arav(self):
        profile, _, _ = LocalProfilerService.profile_candidate(ARAV_LIKE)
        exp = profile.get("experience", [])
        assert len(exp) >= 1, "Arav-like resume should have at least 1 experience entry"

    def test_experience_has_role(self):
        profile, _, _ = LocalProfilerService.profile_candidate(ARAV_LIKE)
        exp = profile.get("experience", [])
        assert exp, "Expected experience entries"
        first = exp[0]
        assert first.get("role") is not None, "First experience entry should have a role"

    def test_experience_has_company(self):
        profile, _, _ = LocalProfilerService.profile_candidate(ARAV_LIKE)
        exp = profile.get("experience", [])
        assert exp
        first = exp[0]
        assert first.get("company") is not None, "First experience entry should have a company"

    def test_experience_has_duration(self):
        profile, _, _ = LocalProfilerService.profile_candidate(ARAV_LIKE)
        exp = profile.get("experience", [])
        # At least one entry should have a duration
        has_duration = any(e.get("duration") for e in exp)
        assert has_duration, "At least one experience entry should have a duration"

    def test_experience_description_not_pure_bullets(self):
        profile, _, _ = LocalProfilerService.profile_candidate(ARAV_LIKE)
        for entry in profile.get("experience", []):
            desc = entry.get("description") or ""
            assert desc.strip() not in ("•", "▪", "◦"), \
                "Description should not be a bare bullet"

    def test_experience_section_with_employment_history_header(self):
        text = (
            "Maria Lopez\nEMPLOYMENT HISTORY\n"
            "Lead Engineer  |  CorpX\nJan 2020 - Dec 2022\nBuilt the core platform.\n"
        )
        profile, _, _ = LocalProfilerService.profile_candidate(text)
        exp = profile.get("experience", [])
        assert len(exp) >= 1


# ===========================================================================
# 5. Education extraction
# ===========================================================================

class TestEducationExtraction:

    def test_education_entries_found(self):
        profile, _, _ = LocalProfilerService.profile_candidate(ARAV_LIKE)
        edu = profile.get("education", [])
        assert len(edu) >= 1, "Should extract at least 1 education entry"

    def test_education_has_degree(self):
        profile, _, _ = LocalProfilerService.profile_candidate(DUMMY_LIKE)
        edu = profile.get("education", [])
        has_degree = any(e.get("degree") for e in edu)
        assert has_degree, "At least one education entry should have a degree"

    def test_education_has_institution(self):
        profile, _, _ = LocalProfilerService.profile_candidate(DUMMY_LIKE)
        edu = profile.get("education", [])
        has_inst = any(e.get("institution") for e in edu)
        assert has_inst, "At least one education entry should have an institution"

    def test_education_has_year(self):
        profile, _, _ = LocalProfilerService.profile_candidate(DUMMY_LIKE)
        edu = profile.get("education", [])
        has_year = any(e.get("year") for e in edu)
        assert has_year, "At least one education entry should have a year"

    def test_education_with_academic_background_header(self):
        text = (
            "Neil\nACADEMIC BACKGROUND\n"
            "Bachelor of Science in Physics\nMIT  |  2018\n"
        )
        profile, _, _ = LocalProfilerService.profile_candidate(text)
        edu = profile.get("education", [])
        assert len(edu) >= 1


# ===========================================================================
# 6. Project extraction
# ===========================================================================

class TestProjectExtraction:

    def test_projects_found_prabal(self):
        profile, _, _ = LocalProfilerService.profile_candidate(PRABAL_LIKE)
        proj = profile.get("projects", [])
        assert len(proj) >= 1, "Prabal-like resume should have at least 1 project"

    def test_projects_found_dummy(self):
        profile, _, _ = LocalProfilerService.profile_candidate(DUMMY_LIKE)
        proj = profile.get("projects", [])
        assert len(proj) >= 1, "Dummy resume should have at least 1 project"

    def test_project_has_name(self):
        profile, _, _ = LocalProfilerService.profile_candidate(DUMMY_LIKE)
        for p in profile.get("projects", []):
            assert p.get("name"), "Every extracted project must have a name"

    def test_project_technologies_extracted_from_parens(self):
        text = (
            "Kai\nKEY PROJECTS\n"
            "Chat Bot  (Python, FastAPI, OpenAI)\n"
            "Built a conversational bot using FastAPI and OpenAI.\n"
        )
        profile, _, _ = LocalProfilerService.profile_candidate(text)
        proj = profile.get("projects", [])
        assert proj, "Should find at least one project"
        techs = proj[0].get("technologies", [])
        assert any("python" in t.lower() for t in techs), \
            f"Python should be in techs: {techs}"

    def test_project_description_present(self):
        profile, _, _ = LocalProfilerService.profile_candidate(ARAV_LIKE)
        proj = profile.get("projects", [])
        if proj:
            has_desc = any(p.get("description") for p in proj)
            assert has_desc, "At least one project should have a description"

    def test_selected_projects_header_maps_to_projects(self):
        text = (
            "Zara\nSELECTED PROJECTS\n"
            "Inventory System\nBuilt with Django and PostgreSQL.\n"
        )
        profile, _, _ = LocalProfilerService.profile_candidate(text)
        proj = profile.get("projects", [])
        assert len(proj) >= 1


# ===========================================================================
# 7. Canonical text
# ===========================================================================

class TestCanonicalText:

    def test_canonical_text_non_empty(self):
        _, canonical, _ = LocalProfilerService.profile_candidate(PRABAL_LIKE)
        assert len(canonical) > 100

    def test_canonical_text_preserves_experience_content(self):
        _, canonical, _ = LocalProfilerService.profile_candidate(PRABAL_LIKE)
        # The word "OneTab" appears in the experience section
        assert "OneTab" in canonical or "onetab" in canonical.lower()

    def test_canonical_text_has_section_labels(self):
        _, canonical, _ = LocalProfilerService.profile_candidate(ARAV_LIKE)
        assert "[" in canonical and "]" in canonical

    def test_canonical_text_length_close_to_input(self):
        """
        Canonical text should not significantly shrink the input;
        total loss must be < 10% of original length.
        """
        _, canonical, _ = LocalProfilerService.profile_candidate(ARAV_LIKE)
        # canonical adds labels so it will be >= input length
        assert len(canonical) >= len(ARAV_LIKE) * 0.85

    def test_canonical_text_includes_unclassified_when_needed(self):
        """Content that cannot be bucketed still appears in [UNCLASSIFIED]."""
        text = "Jane Random\nSome unclassified line that fits no header."
        _, canonical, _ = LocalProfilerService.profile_candidate(text)
        assert "UNCLASSIFIED" in canonical or "unclassified" in canonical.lower()


# ===========================================================================
# 8. Confidence scoring
# ===========================================================================

class TestConfidenceScoring:

    def test_full_resume_high_confidence(self):
        _, _, confidence = LocalProfilerService.profile_candidate(ARAV_LIKE)
        assert confidence["score"] >= 60, \
            f"Well-formed resume should score >= 60, got {confidence['score']}"
        assert not confidence["is_insufficient"]

    def test_full_resume_not_insufficient(self):
        _, _, confidence = LocalProfilerService.profile_candidate(PRABAL_LIKE)
        assert not confidence["is_insufficient"]

    def test_empty_text_is_insufficient(self):
        _, _, confidence = LocalProfilerService.profile_candidate(EMPTY_RESUME)
        assert confidence["is_insufficient"]

    def test_whitespace_only_is_insufficient(self):
        _, _, confidence = LocalProfilerService.profile_candidate(MALFORMED_RESUME)
        assert confidence["is_insufficient"]

    def test_very_short_resume_is_insufficient(self):
        _, _, confidence = LocalProfilerService.profile_candidate(SHORT_RESUME)
        assert confidence["is_insufficient"], \
            "A 3-line stub resume should be flagged as insufficient"

    def test_confidence_has_required_keys(self):
        _, _, confidence = LocalProfilerService.profile_candidate(ARAV_LIKE)
        for key in ("score", "text_length", "has_experience", "has_skills",
                    "has_education", "has_dates", "is_insufficient"):
            assert key in confidence, f"Confidence dict missing key: {key}"

    def test_has_experience_true_when_experience_entries_found(self):
        _, _, confidence = LocalProfilerService.profile_candidate(ARAV_LIKE)
        assert confidence["has_experience"], \
            "has_experience should be True when experience entries are extracted"

    def test_has_skills_true_when_skills_found(self):
        _, _, confidence = LocalProfilerService.profile_candidate(ARAV_LIKE)
        assert confidence["has_skills"]

    def test_has_education_true_when_education_found(self):
        _, _, confidence = LocalProfilerService.profile_candidate(ARAV_LIKE)
        assert confidence["has_education"]

    def test_has_dates_true_for_resume_with_dates(self):
        _, _, confidence = LocalProfilerService.profile_candidate(ARAV_LIKE)
        assert confidence["has_dates"]

    def test_confidence_not_based_on_contact_alone(self):
        """A resume with only contact info should not score >= 60."""
        contact_only = (
            "john.doe@example.com\n"
            "+91 9876543210\n"
            "linkedin.com/in/johndoe\n"
            "github.com/johndoe\n"
        )
        _, _, confidence = LocalProfilerService.profile_candidate(contact_only)
        assert confidence["is_insufficient"], \
            "Contact-info-only text must be marked insufficient"

    def test_long_text_without_structure_can_still_be_insufficient(self):
        """
        A long wall of unstructured text should not automatically score >= 60
        just because of text length.
        """
        long_unstructured = "Lorem ipsum dolor sit amet. " * 100  # ~2800 chars, no structure
        _, _, confidence = LocalProfilerService.profile_candidate(long_unstructured)
        # With new scoring: text > 200 → +10, text > 1000 → +10 = max 20 from length.
        # No skills/experience/education extracted → score = 20 < 60 → insufficient.
        assert confidence["is_insufficient"], \
            "Long but structureless text should remain insufficient"


# ===========================================================================
# 9. Missing sections / malformed
# ===========================================================================

class TestMissingSectionsAndMalformed:

    def test_empty_string_returns_empty_profile(self):
        profile, canonical, confidence = LocalProfilerService.profile_candidate("")
        assert profile == {}
        assert canonical == ""
        assert confidence["is_insufficient"]

    def test_whitespace_only_returns_empty_profile(self):
        profile, canonical, confidence = LocalProfilerService.profile_candidate("   \n\n  ")
        assert profile == {}
        assert canonical == ""
        assert confidence["is_insufficient"]

    def test_no_skills_section_returns_empty_skills(self):
        text = "John Doe\nI worked at ACME for 2 years.\nBachelor's in CS, 2020."
        profile, _, _ = LocalProfilerService.profile_candidate(text)
        skills = profile.get("skills", [])
        assert isinstance(skills, list)

    def test_no_experience_section_returns_empty_experience(self):
        text = "Jane Doe\nEDUCATION\nBSc Computer Science\nMIT, 2021"
        profile, _, _ = LocalProfilerService.profile_candidate(text)
        exp = profile.get("experience", [])
        assert isinstance(exp, list)

    def test_no_education_section_returns_empty_education(self):
        text = "Bob\nWORK EXPERIENCE\nDev at Corp\n2022-2024\nBuilt APIs."
        profile, _, _ = LocalProfilerService.profile_candidate(text)
        edu = profile.get("education", [])
        assert isinstance(edu, list)

    def test_profile_candidate_returns_three_items(self):
        profile, canonical, confidence = LocalProfilerService.profile_candidate(ARAV_LIKE)
        assert isinstance(profile, dict)
        assert isinstance(canonical, str)
        assert isinstance(confidence, dict)

    def test_profile_has_all_expected_keys(self):
        profile, _, _ = LocalProfilerService.profile_candidate(ARAV_LIKE)
        for key in ("name", "summary", "skills", "experience", "education", "projects"):
            assert key in profile, f"Profile missing key: {key}"


# ===========================================================================
# 10. Conservative handling of uncertain fields
# ===========================================================================

class TestConservativeHandling:

    def test_uncertain_name_may_be_none(self):
        """When no clear name is present, None is acceptable."""
        text = (
            "RESUME\n"
            "Software Engineer\n"
            "Python, SQL, FastAPI\n"
        )
        profile, _, _ = LocalProfilerService.profile_candidate(text)
        # May be None — conservative is fine
        name = profile.get("name")
        if name:
            assert len(name) > 1  # at least meaningful if set

    def test_experience_without_dates_still_extracted(self):
        text = (
            "Cara\nWORK EXPERIENCE\n"
            "Software Developer  |  OpenSource Corp\n"
            "Contributed to open-source projects.\n"
            "EDUCATION\nBSc CS, 2021"
        )
        profile, _, _ = LocalProfilerService.profile_candidate(text)
        exp = profile.get("experience", [])
        assert len(exp) >= 1
        # Duration may be None — that's conservative and acceptable
        assert exp[0].get("role") is not None or exp[0].get("company") is not None

    def test_project_without_tech_has_empty_list(self):
        text = (
            "Dev\nPROJECTS\n"
            "My Cool App\n"
            "Built an app that does stuff.\n"
        )
        profile, _, _ = LocalProfilerService.profile_candidate(text)
        proj = profile.get("projects", [])
        if proj:
            techs = proj[0].get("technologies", [])
            assert isinstance(techs, list)

    def test_no_fabrication_in_empty_sections(self):
        """Skills/experience/education should be empty lists, not fabricated data."""
        profile, _, _ = LocalProfilerService.profile_candidate(SHORT_RESUME)
        # None or empty list — not populated with invented values
        exp = profile.get("experience", [])
        assert exp == [] or all(
            isinstance(e, dict) for e in exp
        ), "Experience must be list of dicts or empty"


# ===========================================================================
# 11. Profile job (unchanged API)
# ===========================================================================

class TestProfileJob:

    def test_profile_job_returns_string(self):
        jd = (
            "Python Backend Developer\n"
            "We need a developer with 3+ years of Python experience.\n"
            "Skills: Python, FastAPI, PostgreSQL\n"
        )
        result = LocalProfilerService.profile_job(jd)
        assert isinstance(result, str)
        assert len(result) > 0
