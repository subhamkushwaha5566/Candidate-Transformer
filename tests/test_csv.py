import pytest
from app.parsers.csv_parser import CSVParser

@pytest.fixture
def csv_parser():
    """
    Fixture providing an initialized CSVParser instance.
    """
    return CSVParser()

@pytest.fixture
def valid_csv_bytes():
    """
    Fixture providing valid recruiter CSV file data.
    """
    return (
        b"name,email,phone,current_company,title\n"
        b"John Doe,john@example.com,1234567890,Google,Senior Engineer\n"
        b"Jane Smith,,0987654321,,Designer"
    )

@pytest.fixture
def malformed_csv_bytes():
    """
    Fixture providing malformed/corrupted CSV file data.
    """
    return b"name,email,phone\nAlice,alice@example.com,123,456,extra\nBob"

@pytest.fixture
def empty_csv_bytes():
    """
    Fixture providing empty CSV data.
    """
    return b""

def test_valid_csv_parsing(csv_parser, valid_csv_bytes):
    """
    Test Case 1: Valid CSV parsing.
    Checks field mapping correctness and parsed structure length.
    """
    result = csv_parser.parse(valid_csv_bytes)
    assert len(result) == 2
    
    # Verify first candidate
    john = result[0]
    assert john["full_name"] == "John Doe"
    assert john["emails"] == ["john@example.com"]
    assert john["phones"] == ["1234567890"]
    assert john["headline"] == "Senior Engineer"
    assert len(john["experience"]) == 1
    assert john["experience"][0]["company"] == "Google"
    assert john["experience"][0]["role"] == "Senior Engineer"

    # Verify second candidate
    jane = result[1]
    assert jane["full_name"] == "Jane Smith"
    assert jane["emails"] == []
    assert jane["phones"] == ["0987654321"]
    assert jane["headline"] == "Designer"
    assert len(jane["experience"]) == 1
    assert jane["experience"][0]["company"] is None
    assert jane["experience"][0]["role"] == "Designer"

def test_missing_csv_file(csv_parser):
    """
    Test Case 2: Missing CSV file.
    Verifies that a non-existent path handles gracefully and returns empty list.
    """
    result = csv_parser.parse("this_file_does_not_exist_at_all.csv")
    assert result == []

def test_malformed_csv(csv_parser, malformed_csv_bytes):
    """
    Test Case 3: Malformed CSV.
    Verifies that malformed input streams do not crash the parser.
    """
    result = csv_parser.parse(malformed_csv_bytes)
    assert isinstance(result, list)

def test_empty_csv(csv_parser, empty_csv_bytes):
    """
    Test Case 4: Empty CSV.
    Verifies that zero-length payloads return empty candidate list.
    """
    result = csv_parser.parse(empty_csv_bytes)
    assert result == []
