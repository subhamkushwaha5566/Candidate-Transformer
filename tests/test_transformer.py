import pytest
from unittest.mock import patch
from app.services.transformer import CandidateTransformer

@pytest.fixture
def transformer():
    """
    Fixture providing a CandidateTransformer instance.
    """
    return CandidateTransformer()

def test_process_empty_inputs(transformer):
    """
    Verifies that raising ValueError occurs when both source inputs are missing.
    """
    with pytest.raises(ValueError) as excinfo:
        transformer.process(csv_bytes=None, resume_bytes=None)
    assert "At least one candidate source file" in str(excinfo.value)

@patch("app.parsers.csv_parser.CSVParser.parse")
def test_process_only_csv(mock_csv_parse, transformer):
    """
    Verifies that transformer runs the pipeline successfully with only CSV data.
    """
    mock_csv_parse.return_value = [{
        "full_name": "Alice Vance",
        "emails": ["alice@example.com"],
        "phones": ["9999999999"],
        "headline": "Engineer",
        "experience": [
            {
                "company": "Google",
                "title": "Engineer",
                "start": None,
                "end": None,
                "summary": None
            }
        ]
    }]

    result = transformer.process(csv_bytes=b"dummy_csv", resume_bytes=None)
    
    assert result["full_name"] == "Alice Vance"
    assert result["emails"] == ["alice@example.com"]
    # Indian phone number is E.164 normalized
    assert result["phones"] == ["+919999999999"]
    # Weighted confidence formula (including completeness of location, education and penalties)
    assert result["overall_confidence"] == pytest.approx(0.655, abs=1e-4)
    assert len(result["provenance"]) > 0

@patch("app.parsers.resume_parser.ResumeParser.parse")
def test_process_only_resume(mock_resume_parse, transformer):
    """
    Verifies that transformer runs the pipeline successfully with only PDF resume data.
    """
    mock_resume_parse.return_value = {
        "full_name": "Alice Vance",
        "emails": ["work@alice.com"],
        "phones": ["+1 555-019-9922"],
        "skills": ["Python", "React", "FastAPI"],
        "experience": [
            {
                "company": "Google",
                "title": "Engineer",
                "start": "Jan 2020",
                "end": "Present",
                "summary": "Worked on core Search platform."
            }
        ],
        "education": [],
        "location": None,
        "links": {
            "linkedin": "https://linkedin.com/in/alice-vance",
            "github": "https://github.com/alicev",
            "portfolio": None,
            "other": []
        },
        "headline": "Lead Engineer",
        "years_experience": 4.0
    }
    
    result = transformer.process(csv_bytes=None, resume_bytes=b"dummy_pdf")
    
    assert result["full_name"] == "Alice Vance"
    assert result["emails"] == ["work@alice.com"]
    assert result["phones"] == ["+15550199922"]
    assert result["overall_confidence"] == pytest.approx(0.6588, abs=1e-4)
    assert len(result["skills"]) == 3
    
    # Assert Present sentinel date normalization
    assert len(result["experience"]) == 1
    assert result["experience"][0]["start"] == "2020-01"
    assert result["experience"][0]["end"] == "Present"

@patch("app.parsers.resume_parser.ResumeParser.parse")
@patch("app.parsers.csv_parser.CSVParser.parse")
def test_process_integrated_deep_merge(mock_csv_parse, mock_resume_parse, transformer):
    """
    Verifies that when both CSV and PDF inputs are provided, they are merged.
    Overlapping arrays are unioned and Experience items with matching keys are deeply merged.
    """
    mock_csv_parse.return_value = [{
        "full_name": "Alice Vance",
        "emails": ["alice@example.com"],
        "phones": ["9999999999"],
        "headline": "Engineer",
        "experience": [
            {
                "company": "Google",
                "title": "Engineer",
                "start": None,
                "end": None,
                "summary": None
            }
        ]
    }]

    mock_resume_parse.return_value = {
        "full_name": "Alice Vance",
        "emails": ["work@alice.com"],
        "phones": ["+1 555-019-9922"],
        "skills": ["Python", "React", "FastAPI"],
        "experience": [
            {
                "company": "Google",
                "title": "Engineer",
                "start": "Jan 2020",
                "end": "Present",
                "summary": "Worked on core Search platform."
            }
        ]
    }
    
    result = transformer.process(
        csv_bytes=b"dummy_csv", 
        resume_bytes=b"dummy_pdf",
        config_payload={"on_missing": "null"}
    )
    
    # Unified emails & E.164 phones
    assert len(result["emails"]) == 2
    assert "alice@example.com" in result["emails"]
    assert "work@alice.com" in result["emails"]
    
    assert len(result["phones"]) == 2
    assert "+919999999999" in result["phones"]
    assert "+15550199922" in result["phones"]

    # Deep Merged Experience (CSV and Resume merged)
    assert len(result["experience"]) == 1
    exp = result["experience"][0]
    assert exp["company"] == "Google"
    assert exp["title"] == "Engineer"
    assert exp["start"] == "2020-01"  # filled in from Resume
    assert exp["end"] == "Present"     # filled in from Resume
    assert exp["summary"] == "Worked on core Search platform."  # filled in from Resume

    # Overall confidence matches the weighted formula (0.5621)
    assert result["overall_confidence"] == pytest.approx(0.5621, abs=1e-4)
