import re
from typing import List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

class Location(BaseModel):
    """
    Represents candidate's physical location.
    """
    city: Optional[str] = Field(default=None, description="City name")
    region: Optional[str] = Field(default=None, description="State, province, or region")
    country: Optional[str] = Field(default=None, description="Normalized ISO 3166-1 alpha-2 country code")

    @field_validator("country")
    @classmethod
    def validate_country_code(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v_clean = v.strip().upper()
            if len(v_clean) != 2:
                raise ValueError("Country code must be ISO alpha-2 (2 characters)")
            return v_clean
        return v

class Links(BaseModel):
    """
    Candidate links (LinkedIn, GitHub, Portfolio, etc.).
    """
    linkedin: Optional[str] = Field(default=None, description="LinkedIn profile URL")
    github: Optional[str] = Field(default=None, description="GitHub profile URL")
    portfolio: Optional[str] = Field(default=None, description="Portfolio website URL")
    other: List[str] = Field(default_factory=list, description="Other relevant URLs")

class Skill(BaseModel):
    """
    Candidate technical or soft skill.
    """
    name: str = Field(..., description="Name of the skill")
    experience_years: Optional[float] = Field(default=None, description="Years of experience with the skill")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Skill name cannot be empty")
        return v.strip()

    @field_validator("experience_years")
    @classmethod
    def validate_exp_years(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError("Skill experience years cannot be negative")
        return v

class Experience(BaseModel):
    """
    Professional experience history.
    """
    company: str = Field(..., description="Name of the employing company")
    role: str = Field(..., description="Job role or title")
    start_date: Optional[str] = Field(default=None, description="Start date of employment (YYYY-MM or YYYY)")
    end_date: Optional[str] = Field(default=None, description="End date of employment (YYYY-MM or YYYY) or 'Present'")
    description: Optional[str] = Field(default=None, description="Job duties and accomplishments")

    @field_validator("company", "role")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Company and role cannot be empty")
        return v.strip()

class Education(BaseModel):
    """
    Educational history.
    """
    institution: str = Field(..., description="Name of school, university, or institution")
    degree: Optional[str] = Field(default=None, description="Degree or certificate obtained")
    field_of_study: Optional[str] = Field(default=None, description="Major or area of specialization")
    start_date: Optional[str] = Field(default=None, description="Enrollment start date")
    end_date: Optional[str] = Field(default=None, description="Graduation date")

    @field_validator("institution")
    @classmethod
    def validate_institution(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Institution name cannot be empty")
        return v.strip()

class Provenance(BaseModel):
    """
    Tracking metadata for individual fields to log origin and extraction details.
    """
    field: str = Field(..., description="The candidate field this provenance is tracking (e.g. 'full_name')")
    source: str = Field(..., description="The raw data source name")
    confidence: float = Field(..., description="Source-level/extraction confidence score (0.0 to 1.0)")
    extracted_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="ISO format timestamp")
    raw_value: Optional[Any] = Field(default=None, description="The raw un-normalized value parsed from the source")

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("Confidence must be between 0.0 and 1.0")
        return v

class Candidate(BaseModel):
    """
    Canonical profile representation of a merged and normalized Candidate.
    """
    candidate_id: str = Field(..., description="Unique identifier for the candidate")
    full_name: str = Field(..., description="Full name of the candidate")
    emails: List[str] = Field(default_factory=list, description="List of normalized email addresses")
    phones: List[str] = Field(default_factory=list, description="List of normalized E.164 phone numbers")
    location: Optional[Location] = Field(default=None, description="Candidate physical location details")
    links: Links = Field(default_factory=Links, description="LinkedIn, GitHub, and other links")
    headline: Optional[str] = Field(default=None, description="Professional headline or summary")
    years_experience: Optional[float] = Field(default=None, description="Calculated years of experience")
    skills: List[Skill] = Field(default_factory=list, description="Canonicalized skills list")
    experience: List[Experience] = Field(default_factory=list, description="Professional history items")
    education: List[Education] = Field(default_factory=list, description="Educational history items")
    provenance: List[Provenance] = Field(default_factory=list, description="Field level extraction history list")
    overall_confidence: float = Field(default=0.0, description="Overall profile calculated confidence (0.0 to 1.0)")

    @field_validator("candidate_id", "full_name")
    @classmethod
    def validate_required_strings(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Candidate ID and Full Name cannot be empty")
        return v.strip()

    @field_validator("emails")
    @classmethod
    def validate_emails(cls, v: List[str]) -> List[str]:
        valid_emails = []
        for email in v:
            clean = email.strip()
            if not EMAIL_REGEX.match(clean):
                raise ValueError(f"Invalid email format: {email}")
            valid_emails.append(clean)
        return valid_emails

    @field_validator("years_experience")
    @classmethod
    def validate_years_exp(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError("Years of experience cannot be negative")
        return v

    @field_validator("overall_confidence")
    @classmethod
    def validate_overall_confidence(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("Overall confidence must be between 0.0 and 1.0")
        return v

# Maintain alias for backward compatibility/stubs
CandidateProfile = Candidate
