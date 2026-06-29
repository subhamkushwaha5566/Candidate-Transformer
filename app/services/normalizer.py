import re
from datetime import datetime
from typing import Optional, Dict, Any, List
import phonenumbers
import pycountry
from app.utils.logger import get_logger

logger = get_logger(__name__)

class Normalizer:
    """
    Handles normalization and canonicalization of candidate data fields
    including phone numbers, country codes, skills, date fields, and overall records.
    """
    def normalize_phone(self, phone: str) -> Optional[str]:
        """
        Normalizes a candidate's phone number to E.164 format.
        Handles international formats as well as Indian local numbers.
        Returns None if invalid.
        """
        if not phone or not isinstance(phone, str):
            return None

        phone_clean = phone.strip()
        if not phone_clean:
            return None

        # 1. If starting with +, parse with no default region
        if phone_clean.startswith("+"):
            try:
                parsed = phonenumbers.parse(phone_clean, None)
                if phonenumbers.is_possible_number(parsed):
                    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
            except Exception:
                pass
            return None

        # 2. Try parsing with region defaults based on starting digit prefix
        first_digit = phone_clean[0] if phone_clean else ""
        regions = ["IN", "US"] if first_digit in ["6", "7", "8", "9"] else ["US", "IN"]
        for region in regions:
            try:
                parsed = phonenumbers.parse(phone_clean, region)
                if phonenumbers.is_possible_number(parsed):
                    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
            except Exception:
                continue

        # 3. Last attempt general parsing
        try:
            parsed = phonenumbers.parse(phone_clean, None)
            if phonenumbers.is_possible_number(parsed):
                return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        except Exception:
            pass

        logger.warning(f"Could not normalize phone number: '{phone}'")
        return None

    def normalize_country(self, country: str) -> Optional[str]:
        """
        Normalizes a country name or code to ISO 3166-1 alpha-2 (2 characters).
        Returns None if invalid.
        """
        if not country or not isinstance(country, str):
            return None

        country_clean = country.strip()
        if not country_clean:
            return None

        try:
            match = pycountry.countries.lookup(country_clean)
            if match:
                return match.alpha_2
        except Exception:
            pass

        logger.warning(f"Could not normalize country name: '{country}'")
        return None

    def normalize_skill(self, skill: str) -> Optional[str]:
        """
        Maps skill string values to canonical forms.
        e.g., reactjs -> React, node -> Node.js, mongo -> MongoDB.
        """
        if not skill or not isinstance(skill, str):
            return None

        clean = skill.strip()
        if not clean:
            return None

        # Predefined canonical mapping
        canonical_map = {
            "reactjs": "React",
            "react.js": "React",
            "node": "Node.js",
            "nodejs": "Node.js",
            "mongo": "MongoDB"
        }

        match_key = clean.lower()
        if match_key in canonical_map:
            return canonical_map[match_key]

        # Additional common mapping rules for consistency
        common_skills = {
            "python": "Python",
            "aws": "AWS",
            "sql": "SQL",
            "docker": "Docker",
            "fastapi": "FastAPI",
            "mongodb": "MongoDB",
            "javascript": "JavaScript",
            "js": "JavaScript",
            "typescript": "TypeScript",
            "ts": "TypeScript"
        }
        if match_key in common_skills:
            return common_skills[match_key]

        return clean

    def normalize_date(self, date_string: str) -> Optional[str]:
        """
        Standardizes date strings (e.g. 'Jan 2024', 'March 2025', '2024-01')
        into YYYY-MM format. Also preserves 'Present' and 'Current' sentinels.
        Returns None if parsing fails.
        """
        if not date_string or not isinstance(date_string, str):
            return None

        clean = date_string.strip()
        if not clean:
            return None

        # Handle sentinels
        if clean.lower() in ["present", "current"]:
            return "Present"

        # If it is already exactly YYYY-MM
        if re.match(r"^\d{4}-\d{2}$", clean):
            return clean

        # Clean string from dots, dashes, commas, slashes
        clean_fmt = re.sub(r"[.,\-/]", " ", clean)
        clean_fmt = re.sub(r"\s+", " ", clean_fmt).strip()

        # Try parsing against multiple formats
        formats = [
            "%b %Y",     # Jan 2024
            "%B %Y",     # March 2025
            "%m %Y",     # 01 2024
            "%Y %m",     # 2024 01
            "%B %d %Y",  # March 15 2025
            "%b %d %Y"   # Mar 15 2025
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(clean_fmt, fmt)
                return dt.strftime("%Y-%m")
            except ValueError:
                continue

        # Try mapping standard ISO date structures (like 2024-01-01)
        try:
            if len(clean) >= 7 and re.match(r"^\d{4}-\d{2}", clean):
                return clean[:7]
        except Exception:
            pass

        logger.warning(f"Could not parse/normalize date string: '{date_string}'")
        return None

    def normalize_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Applies normalizations to an entire raw candidate dictionary record.
        """
        normalized = record.copy()

        # 1. Normalize Emails
        emails = record.get("emails", [])
        if isinstance(emails, list):
            normalized["emails"] = list(set([e.lower().strip() for e in emails if e]))

        # 2. Normalize Phones
        phones = record.get("phones", [])
        if isinstance(phones, list):
            normalized["phones"] = [
                self.normalize_phone(p) for p in phones 
                if self.normalize_phone(p) is not None
            ]

        # 3. Normalize Location
        loc = record.get("location")
        if isinstance(loc, dict):
            loc_copy = loc.copy()
            country = loc_copy.get("country")
            if country:
                loc_copy["country"] = self.normalize_country(country)
            normalized["location"] = loc_copy
        elif loc is None:
            normalized["location"] = {"city": None, "region": None, "country": None}

        # 4. Normalize Skills
        skills = record.get("skills", [])
        normalized_skills = []
        if isinstance(skills, list):
            for skill in skills:
                skill_name = None
                exp_years = None
                if isinstance(skill, dict):
                    skill_name = skill.get("name")
                    exp_years = skill.get("experience_years")
                elif isinstance(skill, str):
                    skill_name = skill
                
                if skill_name:
                    canonical_name = self.normalize_skill(skill_name)
                    if canonical_name:
                        normalized_skills.append({
                            "name": canonical_name,
                            "experience_years": exp_years
                        })
        normalized["skills"] = normalized_skills

        # 5. Normalize Experience Dates
        experience = record.get("experience", [])
        normalized_exp = []
        if isinstance(experience, list):
            for exp in experience:
                if isinstance(exp, dict):
                    comp = exp.get("company")
                    role = exp.get("role")
                    s_date = exp.get("start_date")
                    e_date = exp.get("end_date")
                    desc = exp.get("description")
                else:
                    comp = getattr(exp, "company", None)
                    role = getattr(exp, "role", None)
                    s_date = getattr(exp, "start_date", None)
                    e_date = getattr(exp, "end_date", None)
                    desc = getattr(exp, "description", None)

                normalized_exp.append({
                    "company": str(comp).strip() if comp else None,
                    "role": str(role).strip() if role else None,
                    "start_date": self.normalize_date(s_date) if s_date else None,
                    "end_date": self.normalize_date(e_date) if e_date else None,
                    "description": desc
                })
        normalized["experience"] = normalized_exp

        # 6. Normalize Education Dates
        education = record.get("education", [])
        normalized_edu = []
        if isinstance(education, list):
            for edu in education:
                if isinstance(edu, dict):
                    inst = edu.get("institution")
                    deg = edu.get("degree")
                    field = edu.get("field_of_study")
                    s_date = edu.get("start_date")
                    e_date = edu.get("end_date")
                else:
                    inst = getattr(edu, "institution", None)
                    deg = getattr(edu, "degree", None)
                    field = getattr(edu, "field_of_study", None)
                    s_date = getattr(edu, "start_date", None)
                    e_date = getattr(edu, "end_date", None)

                normalized_edu.append({
                    "institution": str(inst).strip() if inst else None,
                    "degree": str(deg).strip() if deg else None,
                    "field_of_study": str(field).strip() if field else None,
                    "start_date": self.normalize_date(s_date) if s_date else None,
                    "end_date": self.normalize_date(e_date) if e_date else None
                })
        normalized["education"] = normalized_edu

        return normalized

# Maintain compatibility
NormalizerService = Normalizer
