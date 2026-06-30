import pytest
from unittest.mock import patch
from app.parsers.resume_parser import ResumeParser
from app.services.normalizer import Normalizer
from app.services.merger import CandidateMerger
from app.services.confidence import ConfidenceEngine
from app.services.projector import ProjectionEngine
from app.services.transformer import CandidateTransformer
from app.schemas.candidate import Candidate, Experience, Education

@pytest.fixture
def resume_parser():
    return ResumeParser()

@pytest.fixture
def normalizer():
    return Normalizer()

@pytest.fixture
def merger():
    return CandidateMerger()

@pytest.fixture
def confidence_engine():
    return ConfidenceEngine()

@pytest.fixture
def projector():
    return ProjectionEngine()

# Mock classes to simulate pdfplumber structures
class MockPage:
    def __init__(self, text):
        self.text_content = text

    def extract_text(self):
        return self.text_content

class MockPDF:
    def __init__(self, pages_text: list):
        self.pages = [MockPage(t) for t in pages_text]

    def close(self):
        pass

@patch("pdfplumber.open")
def test_section_aware_resume_parsing(mock_open, resume_parser):
    """
    Verifies that the resume parser successfully sections the resume text
    and extracts experience, education, projects, skills and achievements.
    """
    resume_text = (
        "Subham Kushwaha\n"
        "Email: subham@example.com\n"
        "Phone: +91 9876543210\n"
        "\n"
        "Education\n"
        "Noida Institute of Engineering and Technology\n"
        "Bachelor of Technology in Information Technology | CGPA-9.28 Sep 2023 – Present\n"
        "\n"
        "Experience\n"
        "Prodigy InfoTech Remote, Aug 2025 – Sep 2025\n"
        "Web Development Intern\n"
        "\n"
        "Projects\n"
        "WritEzy | Node, Express, MongoDB, React | Github Jul 2025\n"
        "\n"
        "Technical Skills\n"
        "Languages: Java, Python, JavaScript, HTML, CSS\n"
        "Framework: Node.js, Express.js, React, Bootstrap\n"
    )
    mock_open.return_value = MockPDF([resume_text])
    
    result = resume_parser.parse("dummy_resume.pdf")
    
    # 1. Verification of metadata and contact info
    assert result["full_name"] == "Subham Kushwaha"
    assert "subham@example.com" in result["emails"]
    assert "+91 9876543210" in result["phones"]
    assert result["location"] == {
        "city": "Greater Noida",
        "region": "Uttar Pradesh",
        "country": "India"
    }

    # 2. Verification of Education extraction
    assert len(result["education"]) == 1
    edu = result["education"][0]
    assert edu["institution"] == "Noida Institute of Engineering and Technology"
    assert edu["degree"] == "Bachelor of Technology"
    assert edu["field"] == "Information Technology"
    assert edu["end_year"] is None  # Since date is "Present"

    # 3. Verification of Experience extraction
    assert len(result["experience"]) == 1
    exp = result["experience"][0]
    assert exp["company"] == "Prodigy InfoTech"
    assert exp["title"] == "Web Development Intern"
    assert exp["start"] == "Aug 2025"
    assert exp["end"] == "Sep 2025"

    # 4. Verification of Skills extraction (Advanced merging & deduplication)
    skills = result["skills"]
    assert "Java" in skills
    assert "Python" in skills
    assert "JavaScript" in skills
    assert "HTML" in skills
    assert "CSS" in skills
    assert "Node.js" in skills
    assert "Express.js" in skills
    assert "React" in skills
    assert "Bootstrap" in skills
    assert "MongoDB" in skills  # extracted from WritEzy projects line!

def test_date_normalization_ongoing(normalizer):
    """
    Tests that 'ongoing' sentinel works in normalize_date and normalize_year.
    """
    assert normalizer.normalize_date("ongoing") == "Present"
    assert normalizer.normalize_date("Ongoing") == "Present"
    assert normalizer.normalize_year("Ongoing") is None
    assert normalizer.normalize_year("ongoing") is None
    
    # Check numeric year parsing
    assert normalizer.normalize_year("2024") == 2024
    assert normalizer.normalize_year("Jan 2025") == 2025
    assert normalizer.normalize_year("Present") is None

def test_candidate_id_generation_deterministic(merger):
    """
    Tests that Candidate ID generation is deterministic and unique.
    """
    records_1 = [
        {"source": "csv", "full_name": "Alice Vance", "emails": ["alice@example.com"]}
    ]
    records_2 = [
        {"source": "resume", "full_name": "Alice Vance", "emails": ["alice@example.com"]}
    ]
    records_diff = [
        {"source": "csv", "full_name": "Bob Vance", "emails": ["bob@example.com"]}
    ]

    candidate_1 = merger.merge(records_1)
    candidate_2 = merger.merge(records_2)
    candidate_diff = merger.merge(records_diff)

    assert len(candidate_1.candidate_id) == 12
    assert candidate_1.candidate_id == candidate_2.candidate_id
    assert candidate_1.candidate_id != candidate_diff.candidate_id

def test_experience_years_calculation(merger):
    """
    Tests calculating years of experience from experience lists.
    """
    records = [
        {
            "source": "csv",
            "full_name": "Alice Vance",
            "experience": [
                {
                    "company": "Company A",
                    "title": "Engineer",
                    "start": "2023-01",
                    "end": "2023-12",
                    "summary": None
                },
                {
                    "company": "Company B",
                    "title": "Senior Engineer",
                    "start": "2024-01",
                    "end": "2024-12",
                    "summary": None
                }
            ]
        }
    ]
    candidate = merger.merge(records)
    # 12 months (Company A) + 12 months (Company B) = 24 months = 2.0 years
    assert candidate.years_experience == pytest.approx(2.0)

def test_headline_inference(merger):
    """
    Verifies that headline is inferred correctly from latest role or top skills.
    """
    # 1. Inference from latest role
    records_role = [
        {
            "source": "csv",
            "full_name": "Alice Vance",
            "experience": [
                {"company": "Google", "title": "Software Engineer", "start": "2020-01", "end": "2022-01"},
                {"company": "Meta", "title": "Tech Lead", "start": "2022-02", "end": "Present"}
            ]
        }
    ]
    candidate_role = merger.merge(records_role)
    assert candidate_role.headline == "Tech Lead"

    # 2. Inference from top skills when experience is missing
    records_skills = [
        {
            "source": "csv",
            "full_name": "Alice Vance",
            "skills": ["Python", "React", "AWS"]
        }
    ]
    candidate_skills = merger.merge(records_skills)
    assert "Python" in candidate_skills.headline
    assert "React" in candidate_skills.headline
    assert "Developer" in candidate_skills.headline

def test_projection_isolation_does_not_leak(projector):
    """
    Tests projection layer isolation.
    Verifies that the canonical candidate object remains fixed and unmutated.
    """
    candidate = Candidate(
        candidate_id="abc123xyz789",
        full_name="Alice Vance",
        emails=["alice@example.com"],
        phones=["+15550199922"],
        skills=[{"name": "Python", "experience_years": 3.0}],
        experience=[{"company": "Google", "title": "Engineer", "start": "2022-01", "end": "Present", "summary": "Code"}],
        education=[{"institution": "MIT", "degree": "BS", "field": "CS", "end_year": 2022}],
        overall_confidence=0.90
    )

    config = {
        "fields": [
            {"path": "primary_email", "from": "emails[0]"},
            {"path": "name", "from": "full_name"}
        ],
        "include_confidence": False,
        "include_provenance": False
    }

    projected = projector.project(candidate, config)

    # 1. Output dict has projected keys
    assert projected["primary_email"] == "alice@example.com"
    assert projected["name"] == "Alice Vance"
    assert "emails" not in projected
    assert "full_name" not in projected

    # 2. Canonical candidate remains unmutated and does not leak primary_email
    assert candidate.emails == ["alice@example.com"]
    assert candidate.full_name == "Alice Vance"
    assert not hasattr(candidate, "primary_email")
    assert "primary_email" not in candidate.model_dump()

def test_weighted_confidence_scoring(confidence_engine):
    """
    Tests the weighted confidence score calculation including conflict consistency.
    """
    candidate = Candidate(
        candidate_id="abc123xyz789",
        full_name="Alice Vance",
        emails=["alice@example.com"],
        phones=["+15550199922"],
        skills=[{"name": "Python"}],
        provenance=[
            {"field": "full_name", "source": "csv", "confidence": 0.95, "raw_value": "Alice Vance"},
            {"field": "emails", "source": "resume", "confidence": 0.85, "raw_value": "alice@example.com"}
        ],
        overall_confidence=0.0
    )

    # Setup raw records to compare conflict consistency
    raw_records_no_conflict = [
        {"full_name": "Alice Vance", "emails": ["alice@example.com"]},
        {"full_name": "Alice Vance", "emails": ["alice@example.com"]}
    ]

    raw_records_conflict = [
        {"full_name": "Alice Vance", "emails": ["alice@example.com"]},
        {"full_name": "Bob Vance", "emails": ["work@alice.com"]}
    ]

    # 1. Calculate confidence with NO conflict
    score_no_conflict = confidence_engine.calculate_overall_confidence(
        candidate=candidate,
        raw_records=raw_records_no_conflict
    )
    
    # 2. Calculate confidence WITH conflict
    score_conflict = confidence_engine.calculate_overall_confidence(
        candidate=candidate,
        raw_records=raw_records_conflict
    )

    # Conflict consistency should reduce score
    assert score_no_conflict > score_conflict

def test_realistic_confidence_score(confidence_engine):
    """
    Verifies that the overall confidence score for the current resume lands in the 0.82-0.88 range.
    """
    candidate = Candidate(
        candidate_id="abc123xyz789",
        full_name="Subham Kushwaha",
        emails=["subham@example.com"],
        phones=["+919876543210"],
        skills=[{"name": "Java"}, {"name": "Python"}, {"name": "JavaScript"}, {"name": "HTML"}, {"name": "CSS"}, {"name": "Node.js"}, {"name": "Express.js"}, {"name": "React"}, {"name": "Bootstrap"}, {"name": "MongoDB"}],
        experience=[
            {
                "company": "Prodigy InfoTech",
                "title": "Web Development Intern",
                "start": "2025-08",
                "end": "2025-09",
                "summary": "Worked on web projects."
            }
        ],
        education=[
            {
                "institution": "Noida Institute of Engineering and Technology",
                "degree": "Bachelor of Technology",
                "field": "Information Technology",
                "end_year": None
            }
        ],
        location={
            "city": "Greater Noida",
            "region": "Uttar Pradesh",
            "country": "IN"
        },
        links={
            "linkedin": "https://linkedin.com/in/subham",
            "github": "https://github.com/subham",
            "portfolio": None,
            "other": []
        },
        headline="Web Development Intern",
        years_experience=0.2,
        provenance=[
            {"field": "full_name", "source": "resume", "confidence": 0.85, "raw_value": "Subham Kushwaha"},
            {"field": "emails", "source": "resume", "confidence": 0.85, "raw_value": "subham@example.com"},
            {"field": "phones", "source": "resume", "confidence": 0.85, "raw_value": "+91 9876543210"},
            {"field": "location", "source": "resume", "confidence": 0.85, "raw_value": "Noida"}
        ]
    )

    raw_records = [
        {
            "full_name": "Subham Kushwaha",
            "emails": ["subham@example.com"],
            "phones": ["+91 9876543210"],
            "location": {"city": "Greater Noida", "region": "Uttar Pradesh", "country": "IN"}
        }
    ]

    score = confidence_engine.calculate_overall_confidence(
        candidate=candidate,
        raw_records=raw_records
    )

    # Expected base: Source=0.85, Completeness=1.0, Consistency=1.0 -> Base = 0.94
    # Penalties:
    # - PDF resume source uncertainty (-0.05)
    # - Years of experience < 1.0 (-0.02)
    # - Education field/degree end_year is None (no penalty for end_year None, but check details completeness)
    # - Experience summary is complete ("Worked on web projects.") -> no penalty
    # Total penalties = -0.07. Expected score = 0.87.
    assert 0.82 <= score <= 0.88

def test_multiple_education_parsing(resume_parser):
    """
    Verifies that high school (Class XII/X) education entries are parsed as separate
    blocks and do not bleed dates into the institution name.
    """
    resume_text = (
        "Education\n"
        "St. Mary's Public School (2020 - 2022)\n"
        "Class XII | CBSE | 2022\n"
        "Class X | CBSE | 2020\n"
    )
    # Mock PDF
    class MockPage:
        def extract_text(self):
            return resume_text
    class MockPDF:
        def __init__(self):
            self.pages = [MockPage()]
        def close(self):
            pass

    with patch("pdfplumber.open", return_value=MockPDF()):
        result = resume_parser.parse("dummy.pdf")

    edu_list = result["education"]
    assert len(edu_list) == 2

    # Verification of Class XII entry
    assert edu_list[0]["institution"] == "St. Mary's Public School"
    assert edu_list[0]["degree"] == "Class XII"
    assert edu_list[0]["field"] == "CBSE"
    assert edu_list[0]["end_year"] == 2022

    # Verification of Class X entry
    assert edu_list[1]["institution"] == "St. Mary's Public School"
    assert edu_list[1]["degree"] == "Class X"
    assert edu_list[1]["field"] == "CBSE"
    assert edu_list[1]["end_year"] == 2020


def test_skills_blacklist_filtering(resume_parser, normalizer):
    """
    Verifies that blacklisted section headers and lists are not extracted/normalized as skills.
    """
    # 1. Test in ResumeParser clean_and_validate_skill via parsing mock
    resume_text = (
        "Technical Skills\n"
        "- Technical Skills\n"
        "• Skills\n"
        "* Languages\n"
        "Framework:\n"
        "Software Tools: Python, Java\n"
    )
    class MockPage:
        def extract_text(self):
            return resume_text
    class MockPDF:
        def __init__(self):
            self.pages = [MockPage()]
        def close(self):
            pass

    with patch("pdfplumber.open", return_value=MockPDF()):
        result = resume_parser.parse("dummy.pdf")

    skills = result["skills"]
    # Only Python and Java should be extracted (since they are in KNOWN_SKILLS)
    # The blacklist headers themselves must never appear.
    assert "Python" in skills
    assert "Java" in skills
    for blacklisted in ["Technical Skills", "Skills", "Languages", "Framework", "Software Tools"]:
        assert blacklisted not in skills
        assert blacklisted.lower() not in [s.lower() for s in skills]

    # 2. Test in Normalizer normalize_skill
    assert normalizer.normalize_skill("Technical Skills") is None
    assert normalizer.normalize_skill("- Software Tools:") is None
    assert normalizer.normalize_skill("• Languages") is None
    assert normalizer.normalize_skill("Framework") is None
    assert normalizer.normalize_skill("Python") == "Python"


def test_education_parsing_three_entries_bug(resume_parser):
    """
    Verifies that the education parser does not merge 10th and 12th schools incorrectly,
    producing 3 separate entries and cleaning dates from institution names.
    """
    resume_text = (
        "Education\n"
        "Noida Institute of Engineering and Technology\n"
        "Bachelor of Technology in Information Technology\n"
        "A.Y.T Senior Secondary School 10th (2020)\n"
        "R B T Vidyalaya 12th (2022)\n"
    )
    class MockPage:
        def extract_text(self):
            return resume_text
    class MockPDF:
        def __init__(self):
            self.pages = [MockPage()]
        def close(self):
            pass

    with patch("pdfplumber.open", return_value=MockPDF()):
        result = resume_parser.parse("dummy.pdf")

    edu_list = result["education"]
    assert len(edu_list) == 3

    # Noida Institute of Engineering and Technology -> Bachelor of Technology / Information Technology
    assert edu_list[0]["institution"] == "Noida Institute of Engineering and Technology"
    assert "Bachelor of Technology" in edu_list[0]["degree"]
    assert edu_list[0]["field"] == "Information Technology"

    # A.Y.T Senior Secondary School -> 10th, end_year=2020
    assert edu_list[1]["institution"] == "A.Y.T Senior Secondary School"
    assert edu_list[1]["degree"] == "10th"
    assert edu_list[1]["end_year"] == 2020

    # R B T Vidyalaya -> 12th, end_year=2022
    assert edu_list[2]["institution"] == "R B T Vidyalaya"
    assert edu_list[2]["degree"] == "12th"
    assert edu_list[2]["end_year"] == 2022



