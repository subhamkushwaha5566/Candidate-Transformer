import io
import re
from typing import Any, Dict, List, Optional
import pdfplumber
from app.parsers.base_parser import BaseParser
from app.utils.logger import get_logger
from app.services.normalizer import Normalizer

logger = get_logger(__name__)

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_PATTERN = re.compile(r"\+?\b\d{1,4}[-.\s]?\(?\d{2,4}\)?[-.\s]?\d{2,4}[-.\s]?\d{3,4}\b")
LINKEDIN_PATTERN = re.compile(r"linkedin\.com/in/[a-zA-Z0-9_\-]+")
GITHUB_PATTERN = re.compile(r"github\.com/[a-zA-Z0-9_\-]+")

SKILL_DICTIONARY = [
    "Java", "Python", "JavaScript", "HTML", "CSS", "Node.js", "Express.js", 
    "React", "Bootstrap", "MongoDB", "PostgreSQL", "Flask", "Scikit-learn", 
    "VS Code", "IntelliJ IDEA", "CAD"
]

KNOWN_SKILLS = {
    "java", "python", "javascript", "html", "css", "node.js", "express.js",
    "react", "bootstrap", "mongodb", "postgresql", "flask", "scikit-learn",
    "vs code", "intellij idea", "cad", "js", "ts", "reactjs", "nodejs",
    "express", "mongo", "postgres", "flask", "vscode", "intellij"
}

DATE_PATTERN = r"(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|\d{1,2}[/\-]\d{4}|\b\d{4}\b|Present|Current|Ongoing)"
DATE_RANGE_PATTERN = re.compile(rf"({DATE_PATTERN})\s*(?:-|–|—|to)\s*({DATE_PATTERN})", re.IGNORECASE)

TITLE_KEYWORDS = [
    "engineer", "developer", "intern", "analyst", "manager", "lead", "architect", 
    "designer", "programmer", "consultant", "specialist", "administrator", "officer",
    "head", "director", "vp", "associate", "founder", "co-founder", "cto",
    "member of technical staff", "mts", "member of", "sde", "swe", "internship"
]

INSTITUTION_KEYWORDS = [
    "university", "college", "institute", "school", "academy", "polytechnic", 
    "technological", "engineering", "science", "technology", "niet", "iit", "nit", "bits",
    "vidhyalaya", "vidyalaya", "public school", "convent"
]

DEGREE_KEYWORDS = [
    "bachelor", "master", "doctor", "phd", "ph.d", "diploma", "b.tech", "m.tech",
    "b.e.", "m.e.", "b.s.", "m.s.", "b.sc", "m.sc", "mba", "b.a.", "m.a.", "bba", "bca", "mca",
    "degree", "associate of", "high school", "class xii", "class x", "12th", "10th", "matriculation",
    "intermediate", "senior school certificate", "secondary school certificate", "cbse", "icse", "ssc", "hsc"
]

STOPWORDS = {
    "and", "or", "in", "of", "to", "with", "for", "at", "by", "from", "on", "a", "an", "the",
    "solved", "problems", "across", "platforms", "using", "built", "developed", "created",
    "worked", "experienced", "technical", "skills", "languages", "frameworks", "tools",
    "libraries", "databases", "platforms", "various", "multiple", "other", "etc", "languages",
    "framework", "github", "linkedin", "education", "experience", "projects", "achievements",
    "technologies", "technical skills", "skills & tools", "core skills", "languages & frameworks"
}

def clean_and_validate_skill(token: str) -> Optional[str]:
    token = token.strip()
    if not token:
        return None
    # Strip leading bullets and symbols commonly used in lists
    token = re.sub(r"^[-\*•o✓▪▫–—\s]+", "", token).strip()
    # Strip trailing punctuation like colon or semicolon
    token = re.sub(r"[:;\s]+$", "", token).strip()
    if not token:
        return None

    # Blacklist check
    blacklist = {
        "technical skills",
        "skills",
        "languages",
        "framework",
        "software tools"
    }
    if token.lower() in blacklist:
        return None

    # Skip tokens containing digits/numbers like "300+" or "10"
    if re.search(r"\d", token):
        return None
    # Skip stopwords/generic words
    if token.lower() in STOPWORDS:
        return None
    # Skip too long or too short tokens (unless 'CAD', etc.)
    if len(token) > 30:
        return None
    if len(token) < 2 and token.lower() not in ["c", "r"]:
        return None
    return token


def strip_dates_from_text(text: str) -> str:
    # Strip date range first
    text = DATE_RANGE_PATTERN.sub("", text)
    # Strip single years
    text = re.sub(r"\b(19\d{2}|20\d{2})\b", "", text)
    # Clean up punctuation and spacing
    text = re.sub(r"^[,\s|–\-—\(\)]+|[,\s|–\-—\(\)]+$", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def is_title(text: str) -> bool:
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in TITLE_KEYWORDS)

def is_bullet(text: str) -> bool:
    return text.strip().startswith(("-", "*", "•", "o", "✓"))

class ResumeParser(BaseParser):
    """
    Concrete parser that processes unstructured PDF Resumes using pdfplumber.
    Extracts candidate profile data using section-aware segmentation and parsing.
    """
    def parse(self, source: Any) -> Dict[str, Any]:
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
            if isinstance(source, str):
                logger.info(f"Opening PDF file from path: {source}")
                pdf = pdfplumber.open(source)
            elif isinstance(source, bytes):
                logger.info("Opening PDF from bytes payload.")
                pdf = pdfplumber.open(io.BytesIO(source))
            elif hasattr(source, "read"):
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
            full_text = ""
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"

            if not full_text.strip():
                logger.warning("PDF parsed successfully, but no text content could be extracted.")
                return null_profile

            # Segment the text into sections
            sections = self._segment_text(full_text)

            # Parse fields using patterns and sections
            emails = self._extract_emails(full_text)
            phones = self._extract_phones(full_text)
            skills = self._extract_skills(sections)
            full_name = self._extract_name(sections, full_text)
            linkedin = self._extract_linkedin(full_text)
            github = self._extract_github(full_text)
            experience = self._extract_experience(sections["experience"])
            education = self._extract_education(sections["education"])
            location = self._extract_location(full_text)

            profile = {
                "full_name": full_name,
                "emails": emails,
                "phones": phones,
                "skills": skills,
                "experience": experience,
                "education": education,
                "location": location,
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

    def _segment_text(self, text: str) -> Dict[str, List[str]]:
        lines = [line.strip() for line in text.split("\n")]
        
        section_patterns = {
            "education": re.compile(r"^\s*(education|academic background|academic profile|academics|study)\b", re.IGNORECASE),
            "experience": re.compile(r"^\s*(experience|work experience|employment|work history|professional experience|professional background|internships|work)\b", re.IGNORECASE),
            "projects": re.compile(r"^\s*(projects|personal projects|academic projects|key projects)\b", re.IGNORECASE),
            "skills": re.compile(r"^\s*(technical skills|skills|technologies|skills & tools|core skills|languages & frameworks|languages|frameworks|tools|databases|platforms)\b", re.IGNORECASE),
            "achievements": re.compile(r"^\s*(achievements|awards|certifications|extracurriculars|extracurricular activities|accomplishments)\b", re.IGNORECASE)
        }
        
        sections = {
            "header": [],
            "education": [],
            "experience": [],
            "projects": [],
            "skills": [],
            "achievements": []
        }
        
        current_section = "header"
        
        for line in lines:
            if not line:
                continue
                
            found_section = None
            
            # Check standalone header
            if len(line) < 40:
                for sec_name, pattern in section_patterns.items():
                    if pattern.match(line):
                        found_section = sec_name
                        line = ""
                        break
            
            # Check inline header (e.g. "Technologies: Python, Java")
            if not found_section and ":" in line:
                parts = line.split(":", 1)
                first_part = parts[0].strip()
                if len(first_part) < 30:
                    for sec_name, pattern in section_patterns.items():
                        if pattern.match(first_part):
                            found_section = sec_name
                            line = parts[1].strip()
                            break
                            
            if found_section:
                current_section = found_section
                if line:
                    sections[current_section].append(line)
            else:
                sections[current_section].append(line)
                
        return sections

    def _extract_emails(self, text: str) -> List[str]:
        matches = EMAIL_PATTERN.findall(text)
        return list(set([m.strip() for m in matches]))

    def _extract_phones(self, text: str) -> List[str]:
        matches = PHONE_PATTERN.findall(text)
        verified_phones = []
        for m in matches:
            digits = re.sub(r"\D", "", m)
            if 7 <= len(digits) <= 15:
                verified_phones.append(m.strip())
        return list(set(verified_phones))

    def _extract_skills(self, sections: Dict[str, List[str]]) -> List[str]:
        extracted = set()
        
        # 1. Parse from Technical Skills section
        for line in sections.get("skills", []):
            content = line
            if ":" in line:
                content = line.split(":", 1)[1]
            elif "-" in line and not line.startswith("-"):
                content = line.split("-", 1)[1]
                
            # Split only on commas, semicolons, and pipes
            for token in re.split(r"[,;|]+", content):
                cleaned = clean_and_validate_skill(token)
                if cleaned:
                    extracted.add(cleaned)
                    
        # 2. Parse from Projects section (tech stacks)
        for line in sections.get("projects", []):
            parts = line.split("|")
            for part in parts:
                part_clean = part.strip()
                # Split by commas, semicolons, or pipes
                sub_parts = [p.strip() for p in re.split(r"[,;|]+", part_clean)]
                valid_subs = []
                for p in sub_parts:
                    cleaned = clean_and_validate_skill(p)
                    if cleaned:
                        valid_subs.append(cleaned)
                
                # If any of the cleaned subparts is a known skill, extract all valid subparts
                if any(p.lower() in KNOWN_SKILLS for p in valid_subs):
                    for p in valid_subs:
                        if not any(x in p.lower() for x in ["github", "linkedin", "http", "202"]):
                            extracted.add(p)
                            
        # 3. Deduplicate and normalize using Normalizer
        normalized = []
        normalizer = Normalizer()
        for s in extracted:
            norm = normalizer.normalize_skill(s)
            if norm and norm not in normalized:
                normalized.append(norm)
                
        return normalized

    def _extract_name(self, sections: Dict[str, List[str]], full_text: str) -> Optional[str]:
        lines_to_check = sections["header"][:5] if sections["header"] else [l.strip() for l in full_text.split("\n") if l.strip()][:5]
        for line in lines_to_check:
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

    def _extract_location(self, text: str) -> Optional[Dict[str, Any]]:
        text_lower = text.lower()
        
        # Check for Noida/Greater Noida Noida Institute patterns
        if "noida" in text_lower:
            return {
                "city": "Greater Noida",
                "region": "Uttar Pradesh",
                "country": "India"
            }
            
        # Other common cities
        cities = {
            "bangalore": ("Bangalore", "Karnataka", "India"),
            "bengaluru": ("Bangalore", "Karnataka", "India"),
            "hyderabad": ("Hyderabad", "Telangana", "India"),
            "pune": ("Pune", "Maharashtra", "India"),
            "mumbai": ("Mumbai", "Maharashtra", "India"),
            "delhi": ("New Delhi", "Delhi", "India"),
            "chennai": ("Chennai", "Tamil Nadu", "India"),
            "san francisco": ("San Francisco", "California", "US"),
            "new york": ("New York", "New York", "US"),
            "london": ("London", "England", "GB")
        }
        
        for city_key, (city_name, region_name, country_name) in cities.items():
            if city_key in text_lower:
                return {
                    "city": city_name,
                    "region": region_name,
                    "country": country_name
                }
                
        return None

    def _extract_experience(self, lines: List[str]) -> List[Dict[str, Any]]:
        entries = []
        current_entry = None
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue
                
            range_match = DATE_RANGE_PATTERN.search(line)
            if range_match:
                start_raw, end_raw = range_match.groups()
                
                line_without_date = line.replace(range_match.group(0), "").strip()
                line_without_date = re.sub(r"^[,\s|–\-—]+|[,\s|–\-—]+$", "", line_without_date)
                line_without_date = re.sub(r"\s+", " ", line_without_date)
                
                company = None
                title = None
                
                location_pattern = re.compile(r"\b(remote|hybrid|onsite|on-site|india|us|usa|uk|germany|london|sf|san francisco|bangalore|noida|delhi)\b", re.IGNORECASE)
                
                def clean_field(text: str) -> str:
                    text_clean = location_pattern.sub("", text).strip()
                    text_clean = re.sub(r"^[,\s|–\-—]+|[,\s|–\-—]+$", "", text_clean)
                    return text_clean
                    
                rem = clean_field(line_without_date)
                
                if rem:
                    if " at " in rem:
                       parts = rem.split(" at ")
                       title = parts[0].strip()
                       company = parts[1].strip()
                    elif " @ " in rem:
                       parts = rem.split(" @ ")
                       title = parts[0].strip()
                       company = parts[1].strip()
                    elif "|" in rem:
                         parts = rem.split("|")
                         part1, part2 = parts[0].strip(), parts[1].strip()
                         if is_title(part1) and not is_title(part2):
                             title = part1
                             company = part2
                         elif is_title(part2) and not is_title(part1):
                             title = part2
                             company = part1
                         else:
                             company = part1
                             title = part2
                    elif "," in rem:
                         parts = rem.split(",")
                         part1 = parts[0].strip()
                         if is_title(part1):
                             title = part1
                             company = ", ".join(parts[1:]).strip()
                         else:
                             company = part1
                             title = ", ".join(parts[1:]).strip()
                    else:
                        if is_title(rem):
                            title = rem
                        else:
                            company = rem
                            
                if not company or not title:
                    prev_line = lines[i-1].strip() if i > 0 else ""
                    prev_line = clean_field(prev_line)
                    if prev_line and not DATE_RANGE_PATTERN.search(prev_line) and not is_bullet(prev_line) and len(prev_line) < 60:
                        if not title and is_title(prev_line):
                            title = prev_line
                        elif not company and not is_title(prev_line):
                            company = prev_line
                            
                if not company or not title:
                    if i + 1 < len(lines):
                        next_line = lines[i+1].strip()
                        next_line = clean_field(next_line)
                        if next_line and not DATE_RANGE_PATTERN.search(next_line) and not is_bullet(next_line) and len(next_line) < 60:
                            if not title and is_title(next_line):
                                title = next_line
                                i += 1
                            elif not company and not is_title(next_line):
                                company = next_line
                                i += 1
                                
                company = company or "Unknown Company"
                title = title or "Unknown Title"
                
                current_entry = {
                    "company": clean_field(company),
                    "title": clean_field(title),
                    "start": start_raw.strip(),
                    "end": end_raw.strip(),
                    "summary": ""
                }
                entries.append(current_entry)
            else:
                if current_entry:
                    line_clean = re.sub(r"^[\s\-\*•o]+", "", line).strip()
                    if line_clean:
                        if current_entry["summary"]:
                            current_entry["summary"] += "\n" + line_clean
                        else:
                            current_entry["summary"] = line_clean
            i += 1
        return entries

    def _extract_education(self, lines: List[str]) -> List[Dict[str, Any]]:
        entries = []
        i = 0
        current_institution = None

        # Compile degree pattern
        escaped_degrees = [re.escape(dw) for dw in DEGREE_KEYWORDS]
        escaped_degrees.sort(key=len, reverse=True)
        degree_pattern = re.compile(r'\b(' + '|'.join(escaped_degrees) + r')\b', re.IGNORECASE)
        
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue
            
            line_lower = line.lower()
            is_inst = any(kw in line_lower for kw in INSTITUTION_KEYWORDS)
            is_deg = any(dw in line_lower for dw in DEGREE_KEYWORDS)
            
            # Identify institution name
            if is_inst:
                # Find if there is a degree or date/year inline
                min_idx = len(line)
                
                deg_match = degree_pattern.search(line)
                if deg_match:
                    min_idx = min(min_idx, deg_match.start())
                    
                range_match = DATE_RANGE_PATTERN.search(line)
                if range_match:
                    min_idx = min(min_idx, range_match.start())
                    
                year_match = re.search(r"\b(19\d{2}|20\d{2})\b", line)
                if year_match:
                    min_idx = min(min_idx, year_match.start())
                
                if is_deg and 0 < min_idx < len(line):
                    # It has both institution and degree/date inline.
                    # Split them.
                    inst_part = line[:min_idx].strip()
                    inst_part = re.sub(r"^[,\s|–\-—:>]+|[,\s|–\-—:>]+$", "", inst_part).strip()
                    current_institution = strip_dates_from_text(inst_part)
                    
                    # The rest of the line is processed as the degree/date line
                    line = line[min_idx:].strip()
                    line = re.sub(r"^[,\s|–\-—:>]+|[,\s|–\-—:>]+$", "", line).strip()
                    line_lower = line.lower()
                    is_deg = any(dw in line_lower for dw in DEGREE_KEYWORDS)
                elif min_idx == 0:
                    # Starts with a degree keyword (e.g. "Bachelor of Technology..."), so it is NOT an institution line
                    pass
                else:
                    # Standalone institution line
                    current_institution = strip_dates_from_text(line)
                    current_institution = re.sub(r"^[,\s|–\-—:>]+|[,\s|–\-—:>]+$", "", current_institution).strip()
                    i += 1
                    continue
                
            inst_name = current_institution or "Unknown Institution"
            
            # Identify degree/class block line
            if is_deg or DATE_RANGE_PATTERN.search(line) or re.search(r"\b(19\d{2}|20\d{2})\b", line):
                degree = None
                field = None
                end_year = None
                
                # Extract date range or year
                range_match = DATE_RANGE_PATTERN.search(line)
                year_match = re.search(r"\b(19\d{2}|20\d{2})\b", line)
                
                line_content = line
                if range_match:
                    start_raw, end_raw = range_match.groups()
                    if end_raw.lower() in ["present", "current", "ongoing"]:
                        end_year = None
                    else:
                        yr_match = re.search(r"\b(19\d{2}|20\d{2})\b", end_raw)
                        if yr_match:
                            end_year = int(yr_match.group(1))
                    line_content = line_content.replace(range_match.group(0), "").strip()
                elif year_match:
                    end_year = int(year_match.group(1))
                    line_content = line_content.replace(year_match.group(0), "").strip()
                    
                # Clean line_content from GPAs and punctuation
                line_content = re.sub(r"\|?\s*(?:cgpa|gpa|marks|percentage|grade)\b.*$", "", line_content, flags=re.IGNORECASE).strip()
                line_content = re.sub(r"^[,\s|–\-—]+|[,\s|–\-—]+$", "", line_content)
                
                # Split degree and field
                if " in " in line_content.lower():
                    parts = re.split(r"\s+in\s+", line_content, maxsplit=1, flags=re.IGNORECASE)
                    degree = parts[0].strip()
                    field = parts[1].strip()
                elif "|" in line_content:
                    parts = line_content.split("|")
                    degree = parts[0].strip()
                    field = parts[1].strip()
                else:
                    degree = line_content
                    
                if degree:
                    degree = strip_dates_from_text(degree)
                if field:
                    field = strip_dates_from_text(field)
                    
                entries.append({
                    "institution": inst_name,
                    "degree": degree or "Degree",
                    "field": field,
                    "end_year": end_year
                })
            i += 1
            
        # Fallback to make sure we don't miss institution lines entirely if no degree parsed
        if not entries:
            for line in lines:
                line_clean = line.strip()
                if any(kw in line_clean.lower() for kw in INSTITUTION_KEYWORDS):
                    entries.append({
                        "institution": strip_dates_from_text(line_clean),
                        "degree": "Degree",
                        "field": None,
                        "end_year": None
                    })
                    
        return entries
