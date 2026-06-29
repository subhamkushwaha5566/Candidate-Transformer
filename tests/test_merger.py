import pytest
from app.services.merger import CandidateMerger

@pytest.fixture
def merger():
    """
    Fixture providing an instance of CandidateMerger.
    """
    return CandidateMerger()

def test_duplicate_email_merged(merger):
    """
    Test Case 1: Duplicate emails merged uniquely.
    Asserts that duplicate emails from different sources are unified.
    """
    record_csv = {
        "source": "csv",
        "full_name": "Alice Vance",
        "emails": ["alice@example.com", "contact@alice.com"]
    }
    record_resume = {
        "source": "resume",
        "full_name": "Alice Vance",
        "emails": ["alice@example.com", "work@alice.com"]
    }

    result = merger.merge([record_csv, record_resume])
    
    # Assert unique union of emails
    assert len(result.emails) == 3
    assert "alice@example.com" in result.emails
    assert "contact@alice.com" in result.emails
    assert "work@alice.com" in result.emails

def test_duplicate_phone_merged(merger):
    """
    Test Case 2: Duplicate phones merged uniquely.
    Asserts that duplicate phone numbers are unified.
    """
    record_csv = {
        "source": "csv",
        "full_name": "Bob Builder",
        "phones": ["+15550199922"]
    }
    record_resume = {
        "source": "resume",
        "full_name": "Bob Builder",
        "phones": ["+15550199922", "+15550199933"]
    }

    result = merger.merge([record_csv, record_resume])
    
    assert len(result.phones) == 2
    assert "+15550199922" in result.phones
    assert "+15550199933" in result.phones

def test_conflicting_headline_resolved(merger):
    """
    Test Case 3: Conflicting headline resolved.
    Asserts that scalar field conflicts select the value from the source with higher confidence.
    CSV confidence (0.95) > Resume confidence (0.85).
    """
    # CSV has higher confidence, should win
    record_csv = {
        "source": "csv",
        "full_name": "Charlie Chaplin",
        "headline": "Lead Actor"
    }
    record_resume = {
        "source": "resume",
        "full_name": "Charlie Chaplin",
        "headline": "Director and Writer"
    }

    result = merger.merge([record_csv, record_resume])
    assert result.headline == "Lead Actor"

    # If CSV has no headline, it should fall back to Resume
    record_csv_empty = {
        "source": "csv",
        "full_name": "Charlie Chaplin",
        "headline": ""
    }
    result_fallback = merger.merge([record_csv_empty, record_resume])
    assert result_fallback.headline == "Director and Writer"

def test_provenance_retained(merger):
    """
    Test Case 4: Provenance details retained.
    Asserts that all fields track their source, confidence score, and raw value correctly.
    """
    record_csv = {
        "source": "csv",
        "full_name": "Alice Vance",
        "headline": "Python Developer",
        "emails": ["alice@example.com"]
    }
    record_resume = {
        "source": "resume",
        "full_name": "Alice Vance",
        "headline": "React Engineer",
        "phones": ["+15550199922"]
    }

    result = merger.merge([record_csv, record_resume])
    
    # Assert provenance list is populated
    assert len(result.provenance) > 0

    # Locate field provenance for 'headline' (CSV wins)
    headline_prov = [p for p in result.provenance if p.field == "headline"]
    assert len(headline_prov) == 1
    assert headline_prov[0].source == "csv"
    assert headline_prov[0].confidence == 0.95
    assert headline_prov[0].raw_value == "Python Developer"

    # Locate field provenance for 'phones' (Resume contributes)
    phone_prov = [p for p in result.provenance if p.field == "phones"]
    assert len(phone_prov) == 1
    assert phone_prov[0].source == "resume"
    assert phone_prov[0].confidence == 0.85
    assert phone_prov[0].raw_value == "+15550199922"
