import io
import re
from typing import Any, Dict, List, Optional
import pdfplumber
from app.parsers.base_parser import BaseParser
from app.utils.logger import get_logger

logger = get_logger(__name__)

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
# Match simple phone patterns: +XX-XXX-XXX-XXXX, +XX XXXXX XXXXX, (XXX) XXX-XXXX, etc.
PHONE_PATTERN = re.compile(r"\+?\b\d{1,4}[-.\s]?\(?\d{2,4}\)?[-.\s]?\d{2,4}[-.\s]?\d{3,4}\b")
LINKEDIN_PATTERN = re.compile(r"linkedin\.com/in/[a-zA-Z0-9_\-]+")
GITHUB_PATTERN = re.compile(r"github\.com/[a-zA-Z0-9_\-]+")

SKILL_DICTIONARY = [
    "Python",
    "React",
    "Node.js",
    "MongoDB",
    "SQL",
    "Docker",
    "AWS",
    "FastAPI"
]

class ResumeParser(BaseParser):
    """
    Concrete parser that processes unstructured PDF Resumes using pdfplumber.
    Extracts candidate profile data including name, email, phone, links, and predefined skills.
    """
    def parse(self, source: Any) -> Dict[str, Any]:
        """
        Parses a PDF resume from a file path, bytes, or file stream.
        Returns a dictionary of extracted fields or standard null values on failure.

        Args:
            source: A file path (str), bytes, or a file-like stream object.

        Returns:
            Dict[str, Any]: Extracted candidate properties mapped to the canonical candidate structure.
        """
        null_profile = {
            "full_name": None,
            "emails": [],
            "phones": [],
            "skills": [],
            "experience": [],
            "education": [],
            "location": None,
            "links": {
                "linkedin": None,
                "github": None,
                "portfolio": None,
                "other": []
            },
            "headline": None,
            "years_experience": None,
            "provenance": [],
            "overall_confidence": 0.0
        }

        pdf = None
        try:
            # 1. Open the PDF file using pdfplumber depending on source type
            if isinstance(source, str):
                logger.info(f"Opening PDF file from path: {source}")
                pdf = pdfplumber.open(source)
            elif isinstance(source, bytes):
                logger.info("Opening PDF from bytes payload.")
                pdf = pdfplumber.open(io.BytesIO(source))
            elif hasattr(source, "read"):
                # Handle file-like objects (e.g. FastAPI SpooledTemporaryFile)
                content = source.read()
                if isinstance(content, bytes):
                    pdf = pdfplumber.open(io.BytesIO(content))
                else:
                    logger.error("File-like object did not contain bytes.")
                    return null_profile
            else:
                logger.error(f"Unsupported source type for PDF parsing: {type(source)}")
                return null_profile
        except Exception as e:
            logger.exception(f"Corrupted or invalid PDF format: {e}")
            return null_profile

        try:
            # 2. Extract text from pages
            full_text = ""
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"

            if not full_text.strip():
                logger.warning("PDF parsed successfully, but no text content could be extracted.")
                return null_profile

            # 3. Parse fields using pattern matching and rules
            emails = self._extract_emails(full_text)
            phones = self._extract_phones(full_text)
            skills = self._extract_skills(full_text)
            full_name = self._extract_name(full_text)
            linkedin = self._extract_linkedin(full_text)
            github = self._extract_github(full_text)

            profile = {
                "full_name": full_name,
                "emails": emails,
                "phones": phones,
                "skills": [{"name": skill} for skill in skills],
                "experience": [],
                "education": [],
                "location": None,
                "links": {
                    "linkedin": linkedin,
                    "github": github,
                    "portfolio": None,
                    "other": []
                },
                "headline": None,
                "years_experience": None,
                "provenance": [],
                "overall_confidence": 0.0
            }
            logger.info("Successfully completed PDF resume extraction.")
            return profile

        except Exception as e:
            logger.exception(f"Unexpected error during PDF parsing: {e}")
            return null_profile
        finally:
            if pdf is not None:
                try:
                    pdf.close()
                except Exception:
                    pass

    def _extract_emails(self, text: str) -> List[str]:
        matches = EMAIL_PATTERN.findall(text)
        return list(set([m.strip() for m in matches]))

    def _extract_phones(self, text: str) -> List[str]:
        matches = PHONE_PATTERN.findall(text)
        verified_phones = []
        for m in matches:
            digits = re.sub(r"\D", "", m)
            # Standard E.164 candidates usually have 7 to 15 digits
            if 7 <= len(digits) <= 15:
                verified_phones.append(m.strip())
        return list(set(verified_phones))

    def _extract_skills(self, text: str) -> List[str]:
        found_skills = []
        for skill in SKILL_DICTIONARY:
            # Match skill names using word boundaries.
            # Handle aliases or variation groupings for React, Node, and FastAPI.
            if skill.lower() in ["node.js", "nodejs", "node js"]:
                pattern_str = r"\b(node\.js|nodejs|node\s+js)\b"
            elif skill.lower() in ["fastapi", "fast api"]:
                pattern_str = r"\b(fastapi|fast\s+api)\b"
            elif skill.lower() in ["react", "reactjs"]:
                pattern_str = r"\b(react|reactjs|react\.js)\b"
            else:
                pattern_str = r"\b" + re.escape(skill) + r"\b"

            pattern = re.compile(pattern_str, re.IGNORECASE)
            if pattern.search(text):
                found_skills.append(skill)
        return found_skills

    def _extract_name(self, text: str) -> Optional[str]:
        """
        Extracts a candidate's full name from the top non-empty lines.
        Skips lines containing emails, urls, digits, or standard metadata markers.
        """
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        for line in lines[:5]:
            if "@" in line:
                continue
            if "http" in line or "github" in line or "linkedin" in line:
                continue
            if any(char.isdigit() for char in line):
                continue
            words = line.split()
            if 2 <= len(words) <= 4:
                return line
        return None

    def _extract_linkedin(self, text: str) -> Optional[str]:
        match = LINKEDIN_PATTERN.search(text)
        if match:
            return "https://" + match.group(0)
        return None

    def _extract_github(self, text: str) -> Optional[str]:
        match = GITHUB_PATTERN.search(text)
        if match:
            return "https://" + match.group(0)
        return None
