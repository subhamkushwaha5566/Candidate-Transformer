import pytest
from app.services.normalizer import Normalizer

@pytest.fixture
def normalizer():
    """
    Fixture providing an initialized Normalizer instance.
    """
    return Normalizer()

def test_valid_phone_normalization(normalizer):
    """
    Test Case: Valid phone normalization.
    Verifies E.164 conversion, including Indian local formats.
    """
    # International prefixed number
    assert normalizer.normalize_phone("+91 99999 99999") == "+919999999999"
    # Local Indian format parsed with Indian region default
    assert normalizer.normalize_phone("9999999999") == "+919999999999"
    # US number format
    assert normalizer.normalize_phone("+1 555-019-9922") == "+15550199922"
    assert normalizer.normalize_phone("5550199922") == "+15550199922"

def test_invalid_phone(normalizer):
    """
    Test Case: Invalid phone values.
    Verifies that garbage strings or overly short numbers return None.
    """
    assert normalizer.normalize_phone("123") is None
    assert normalizer.normalize_phone("not-a-phone-number") is None
    assert normalizer.normalize_phone("") is None

def test_country_normalization(normalizer):
    """
    Test Case: Country normalization to ISO alpha-2.
    Verifies names, alpha-2, and alpha-3 codes.
    """
    assert normalizer.normalize_country("United States") == "US"
    assert normalizer.normalize_country("India") == "IN"
    assert normalizer.normalize_country("IN") == "IN"
    assert normalizer.normalize_country("USA") == "US"
    assert normalizer.normalize_country("InvalidCountryName") is None
    assert normalizer.normalize_country("") is None

def test_skill_normalization(normalizer):
    """
    Test Case: Skill canonical mappings and formatting.
    """
    # Predefined requirements
    assert normalizer.normalize_skill("reactjs") == "React"
    assert normalizer.normalize_skill("react.js") == "React"
    assert normalizer.normalize_skill("node") == "Node.js"
    assert normalizer.normalize_skill("nodejs") == "Node.js"
    assert normalizer.normalize_skill("mongo") == "MongoDB"

    # Additional standard skills
    assert normalizer.normalize_skill("python") == "Python"
    assert normalizer.normalize_skill("aws") == "AWS"
    assert normalizer.normalize_skill("custom-skill") == "custom-skill"
    assert normalizer.normalize_skill("") is None

def test_date_normalization(normalizer):
    """
    Test Case: Date string standardization to YYYY-MM.
    """
    assert normalizer.normalize_date("Jan 2024") == "2024-01"
    assert normalizer.normalize_date("March 2025") == "2025-03"
    assert normalizer.normalize_date("2024-01") == "2024-01"
    assert normalizer.normalize_date("05/2023") == "2023-05"
    assert normalizer.normalize_date("2024-05-15") == "2024-05"

def test_invalid_date(normalizer):
    """
    Test Case: Invalid date handling.
    """
    assert normalizer.normalize_date("not-a-date") is None
    assert normalizer.normalize_date("202") is None
    assert normalizer.normalize_date("") is None
