import pytest
from unittest.mock import MagicMock, patch
from app.parsers.resume_parser import ResumeParser

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

@pytest.fixture
def resume_parser():
    return ResumeParser()

@pytest.fixture
def valid_resume_text():
    return (
        "Alice Vance\n"
        "Python and React Software Engineer\n"
        "Email: alice@vance.com\n"
        "Phone: +1 555-019-9922\n"
        "LinkedIn: linkedin.com/in/alice-vance\n"
        "GitHub: github.com/alicev\n"
        "Technologies: Python, React, MongoDB, SQL, FastAPI, AWS"
    )

@pytest.fixture
def no_skills_resume_text():
    return (
        "Bob Builder\n"
        "General Construction Manager\n"
        "Email: bob@builder.com\n"
        "Phone: 987-654-3210\n"
        "Experience in managing building sites, negotiating contracts, and leading crews."
    )

@patch("pdfplumber.open")
def test_valid_resume_parsing(mock_open, resume_parser, valid_resume_text):
    """
    Test Case 1: Valid resume PDF parsing.
    Checks parsing of name, emails, phones, skills, and links from text.
    """
    # Setup mock to return a valid PDF structure
    mock_open.return_value = MockPDF([valid_resume_text])

    result = resume_parser.parse("dummy_path.pdf")

    assert result["full_name"] == "Alice Vance"
    assert result["emails"] == ["alice@vance.com"]
    assert result["phones"] == ["+1 555-019-9922"]
    
    # Skills check (predefined mapping values)
    skills_names = [s["name"] for s in result["skills"]]
    assert "Python" in skills_names
    assert "React" in skills_names
    assert "MongoDB" in skills_names
    assert "SQL" in skills_names
    assert "FastAPI" in skills_names
    assert "AWS" in skills_names
    assert "Docker" not in skills_names

    # Links check
    assert result["links"]["linkedin"] == "https://linkedin.com/in/alice-vance"
    assert result["links"]["github"] == "https://github.com/alicev"

@patch("pdfplumber.open")
def test_corrupted_pdf(mock_open, resume_parser):
    """
    Test Case 2: Corrupted PDF file.
    Verifies that parser handles exception from pdfplumber gracefully and returns empty fields.
    """
    # Setup mock to throw an exception during open
    mock_open.side_effect = Exception("Invalid PDF Header structure.")

    result = resume_parser.parse("corrupted.pdf")

    assert result["full_name"] is None
    assert result["emails"] == []
    assert result["phones"] == []
    assert result["skills"] == []
    assert result["links"]["linkedin"] is None

def test_missing_file(resume_parser):
    """
    Test Case 3: Missing file.
    Verifies that a non-existent file path returns standard empty fields.
    """
    result = resume_parser.parse("non_existent_file.pdf")
    
    assert result["full_name"] is None
    assert result["emails"] == []
    assert result["phones"] == []
    assert result["skills"] == []

@patch("pdfplumber.open")
def test_resume_with_no_skills(mock_open, resume_parser, no_skills_resume_text):
    """
    Test Case 4: Resume with no skills.
    Verifies name and contacts extraction still work, but skills list remains empty.
    """
    mock_open.return_value = MockPDF([no_skills_resume_text])

    result = resume_parser.parse("no_skills.pdf")

    assert result["full_name"] == "Bob Builder"
    assert result["emails"] == ["bob@builder.com"]
    assert result["phones"] == ["987-654-3210"]
    assert result["skills"] == []
