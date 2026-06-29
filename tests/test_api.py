import json
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# Helper mock classes for pdfplumber
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

def test_get_health_route():
    """
    Test Case 1: GET health route.
    Verifies root endpoint (/) returns the dashboard UI and /health returns healthy JSON.
    """
    response_root = client.get("/")
    assert response_root.status_code == 200
    assert "text/html" in response_root.headers.get("content-type", "")

    response_health = client.get("/health")
    assert response_health.status_code == 200
    assert response_health.json() == {"status": "healthy"}

@patch("pdfplumber.open")
def test_successful_transform(mock_open):
    """
    Test Case 2: Successful transform.
    Sends both recruiter CSV and resume PDF along with a projection config.
    """
    # 1. Mock PDF reader response
    pdf_text = "Alice Vance\nPython Developer\nEmail: alice@example.com\nPhone: +1 555-019-9922\nSkills: Python, AWS, React"
    mock_open.return_value = MockPDF([pdf_text])

    # 2. Setup multipart files and config form parameters
    csv_content = b"name,email,phone,current_company,title\nAlice Vance,alice@example.com,9999999999,Google,Engineer"
    files = {
        "csv_file": ("candidates.csv", csv_content, "text/csv"),
        "resume_file": ("resume.pdf", b"pdf_binary_content", "application/pdf")
    }
    
    # Select only full_name, emails, and primary phone (renamed)
    config_payload = {
        "fields": [
            {"path": "full_name"},
            {"path": "emails"},
            {"path": "primary_phone", "from": "phones[0]"}
        ],
        "include_confidence": True,
        "include_provenance": False,
        "on_missing": "null"
    }
    
    data = {"config": json.dumps(config_payload)}

    response = client.post("/api/v1/transform", files=files, data=data)
    
    assert response.status_code == 200
    json_data = response.json()
    
    # Assert correct field projection and mapping
    assert json_data["full_name"] == "Alice Vance"
    assert "alice@example.com" in json_data["emails"]
    # E.164 normalization checks (Indian local format maps to +91 phone)
    assert json_data["primary_phone"] in ["+919999999999", "+15550199922"]
    assert "overall_confidence" in json_data
    # Provenance is explicitly disabled in output config
    assert "provenance" not in json_data

def test_invalid_upload():
    """
    Test Case 3: Invalid upload.
    Checks that sending a request with no files returns a 400 error.
    """
    response = client.post("/api/v1/transform")
    assert response.status_code == 400
    assert "At least one candidate source file (CSV or PDF) is required." in response.json()["detail"]

def test_malformed_config():
    """
    Test Case 4: Malformed config.
    Checks that invalid JSON or invalid Pydantic schema formats throw 400 errors.
    """
    csv_content = b"name,email,phone,current_company,title\nAlice Vance,alice@example.com,9999999999,Google,Engineer"
    files = {
        "csv_file": ("candidates.csv", csv_content, "text/csv")
    }

    # Case A: Invalid JSON string
    data_bad_json = {"config": "{malformed-json}"}
    response_bad_json = client.post("/api/v1/transform", files=files, data=data_bad_json)
    assert response_bad_json.status_code == 400
    assert "Invalid config JSON syntax" in response_bad_json.json()["detail"]

    # Case B: Invalid Pydantic schema option (e.g. wrong on_missing value enum)
    data_bad_schema = {"config": json.dumps({"on_missing": "invalid_mode_option"})}
    response_bad_schema = client.post("/api/v1/transform", files=files, data=data_bad_schema)
    assert response_bad_schema.status_code == 400
    assert "Invalid runtime configuration schema" in response_bad_schema.json()["detail"]
