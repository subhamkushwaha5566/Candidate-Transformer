import uuid
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.schemas.candidate import Candidate, Location, Links, Skill, Experience, Education, Provenance
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Predefined source confidence scores
CONFIDENCE_MAP = {
    "csv": 0.95,
    "resume": 0.85,
    "notes": 0.60
}

class CandidateMerger:
    """
    Deduplicates and merges candidate records from multiple sources (CSV, Resume, Notes)
    using source confidence values for scalar fields conflict resolution and tracks detailed provenance.
    """
    def merge(self, candidate_records: List[Dict[str, Any]]) -> Candidate:
        """
        Merges multiple raw candidate dictionaries into a single canonical Candidate profile.

        Args:
            candidate_records: A list of candidate property dictionaries.
                               Each dictionary can contain a 'source' key (e.g. 'csv', 'resume', 'notes').

        Returns:
            Candidate: The final merged canonical candidate object.
            """
        if not candidate_records:
            raise ValueError("Cannot merge an empty list of candidate records")

        logger.info(f"Merging {len(candidate_records)} candidate records.")

        # 1. Normalize source information and map confidence scores
        records_with_confidence = []
        for rec in candidate_records:
            src = rec.get("source", "notes").lower()
            confidence = CONFIDENCE_MAP.get(src, 0.50)
            records_with_confidence.append({
                "source": src,
                "confidence": confidence,
                "data": rec,
                "timestamp": datetime.utcnow().isoformat()
            })

        # Sort records by confidence descending (highest confidence first) for priority resolution
        records_with_confidence.sort(key=lambda x: x["confidence"], reverse=True)

        provenance_list: List[Provenance] = []

        # Helper function to resolve conflict in scalar fields and register provenance
        def resolve_scalar(field_name: str, keys_path: List[str]) -> Optional[Any]:
            for item in records_with_confidence:
                data = item["data"]
                val = data
                for k in keys_path:
                    if isinstance(val, dict):
                        val = val.get(k)
                    else:
                        val = None
                        break

                # Resolve to value if it is non-empty
                if val is not None and str(val).strip() != "":
                    provenance_list.append(Provenance(
                        field=field_name,
                        source=item["source"],
                        confidence=item["confidence"],
                        extracted_at=item["timestamp"],
                        raw_value=val
                    ))
                    return val
            return None

        # 2. Resolve base scalar fields in dependency order
        full_name = resolve_scalar("full_name", ["full_name"]) or "Unknown Candidate"
        headline = resolve_scalar("headline", ["headline"])
        
        # Merge emails array (union merged)
        emails_set = set()
        for item in records_with_confidence:
            emails = item["data"].get("emails", [])
            if isinstance(emails, list):
                for email in emails:
                    if email and str(email).strip():
                        clean_email = str(email).strip().lower()
                        if clean_email not in emails_set:
                            emails_set.add(clean_email)
                            provenance_list.append(Provenance(
                                field="emails",
                                source=item["source"],
                                confidence=item["confidence"],
                                extracted_at=item["timestamp"],
                                raw_value=email
                            ))

        # Deterministic Candidate ID from stable candidate fields (name + primary_email)
        sorted_emails = sorted(list(emails_set))
        primary_email = sorted_emails[0] if sorted_emails else ""
        stable_str = (full_name or "").strip().lower() + primary_email.strip().lower()
        candidate_id = hashlib.sha256(stable_str.encode("utf-8")).hexdigest()[:12]
        
        # Add provenance for candidate_id
        provenance_list.append(Provenance(
            field="candidate_id",
            source=records_with_confidence[0]["source"],
            confidence=records_with_confidence[0]["confidence"],
            extracted_at=records_with_confidence[0]["timestamp"],
            raw_value=candidate_id
        ))

        # Resolve Location nested scalars
        city = resolve_scalar("location.city", ["location", "city"])
        region = resolve_scalar("location.region", ["location", "region"])
        country = resolve_scalar("location.country", ["location", "country"])
        location = Location(city=city, region=region, country=country)

        # Resolve Links nested scalars
        linkedin = resolve_scalar("links.linkedin", ["links", "linkedin"])
        github = resolve_scalar("links.github", ["links", "github"])
        portfolio = resolve_scalar("links.portfolio", ["links", "portfolio"])

        # Merge links.other array (union merged)
        other_links_set = set()
        for item in records_with_confidence:
            links_dict = item["data"].get("links")
            other_list = links_dict.get("other", []) if isinstance(links_dict, dict) else []
            for link in other_list:
                if link and str(link).strip():
                    clean_link = str(link).strip()
                    if clean_link not in other_links_set:
                        other_links_set.add(clean_link)
                        provenance_list.append(Provenance(
                            field="links.other",
                            source=item["source"],
                            confidence=item["confidence"],
                            extracted_at=item["timestamp"],
                            raw_value=clean_link
                        ))
        links = Links(linkedin=linkedin, github=github, portfolio=portfolio, other=list(other_links_set))

        # Merge phones array (union merged)
        phones_set = set()
        for item in records_with_confidence:
            phones = item["data"].get("phones", [])
            if isinstance(phones, list):
                for phone in phones:
                    if phone and str(phone).strip():
                        clean_phone = str(phone).strip()
                        if clean_phone not in phones_set:
                            phones_set.add(clean_phone)
                            provenance_list.append(Provenance(
                                field="phones",
                                source=item["source"],
                                confidence=item["confidence"],
                                extracted_at=item["timestamp"],
                                raw_value=phone
                            ))

        # Merge skills array uniquely by name (case-insensitive deduplication, keeping maximum experience years)
        skills_map = {}
        for item in records_with_confidence:
            skills = item["data"].get("skills", [])
            if isinstance(skills, list):
                for skill in skills:
                    skill_name = None
                    exp_years = None
                    if isinstance(skill, dict):
                        skill_name = skill.get("name")
                        exp_years = skill.get("experience_years")
                    elif isinstance(skill, str):
                        skill_name = skill
                    elif hasattr(skill, "name"):
                        skill_name = skill.name
                        exp_years = getattr(skill, "experience_years", None)

                    if skill_name and str(skill_name).strip():
                        clean_name = str(skill_name).strip()
                        key = clean_name.lower()
                        if key not in skills_map:
                            skills_map[key] = Skill(name=clean_name, experience_years=exp_years)
                            provenance_list.append(Provenance(
                                field="skills",
                                source=item["source"],
                                confidence=item["confidence"],
                                extracted_at=item["timestamp"],
                                raw_value=skill_name
                            ))
                        else:
                            if exp_years is not None:
                                current_exp = skills_map[key].experience_years
                                if current_exp is None or exp_years > current_exp:
                                    skills_map[key].experience_years = exp_years

        # Merge experience array with deep sub-property merging (company, title, start, end, summary)
        experience_map = {}
        for item in records_with_confidence:
            exp_items = item["data"].get("experience", [])
            if isinstance(exp_items, list):
                for exp in exp_items:
                    if isinstance(exp, dict):
                        comp = exp.get("company")
                        title = exp.get("title") or exp.get("role")
                        start = exp.get("start") or exp.get("start_date")
                        end = exp.get("end") or exp.get("end_date")
                        summary = exp.get("summary") or exp.get("description")
                    else:
                        comp = getattr(exp, "company", None)
                        title = getattr(exp, "title", getattr(exp, "role", None))
                        start = getattr(exp, "start", getattr(exp, "start_date", None))
                        end = getattr(exp, "end", getattr(exp, "end_date", None))
                        summary = getattr(exp, "summary", getattr(exp, "description", None))

                    if comp or title:
                        comp_clean = str(comp).strip() if comp else "Unknown Company"
                        title_clean = str(title).strip() if title else "Unknown Title"
                        key = f"{comp_clean.lower()}|{title_clean.lower()}"

                        if key not in experience_map:
                            exp_obj = Experience(
                                company=comp_clean,
                                title=title_clean,
                                start=start,
                                end=end,
                                summary=summary
                            )
                            experience_map[key] = exp_obj
                            provenance_list.append(Provenance(
                                field="experience",
                                source=item["source"],
                                confidence=item["confidence"],
                                extracted_at=item["timestamp"],
                                raw_value={"company": comp, "title": title}
                            ))
                        else:
                            existing = experience_map[key]
                            if not existing.start and start:
                                existing.start = start
                            if not existing.end and end:
                                existing.end = end
                            if not existing.summary and summary:
                                existing.summary = summary

        experience_list = list(experience_map.values())

        # Merge education array with deep sub-property merging (institution, degree, field, end_year)
        education_map = {}
        for item in records_with_confidence:
            edu_items = item["data"].get("education", [])
            if isinstance(edu_items, list):
                for edu in edu_items:
                    if isinstance(edu, dict):
                        inst = edu.get("institution")
                        deg = edu.get("degree")
                        field = edu.get("field") or edu.get("field_of_study")
                        end_yr = edu.get("end_year") or edu.get("end_date")
                    else:
                        inst = getattr(edu, "institution", None)
                        deg = getattr(edu, "degree", None)
                        field = getattr(edu, "field", getattr(edu, "field_of_study", None))
                        end_yr = getattr(edu, "end_year", getattr(edu, "end_date", None))

                    if inst:
                        inst_clean = str(inst).strip()
                        deg_clean = str(deg).strip() if deg else ""
                        key = f"{inst_clean.lower()}|{deg_clean.lower()}"

                        if key not in education_map:
                            edu_obj = Education(
                                institution=inst_clean,
                                degree=deg_clean if deg_clean else None,
                                field=field,
                                end_year=end_yr
                            )
                            education_map[key] = edu_obj
                            provenance_list.append(Provenance(
                                field="education",
                                source=item["source"],
                                confidence=item["confidence"],
                                extracted_at=item["timestamp"],
                                raw_value={"institution": inst, "degree": deg}
                            ))
                        else:
                            existing = education_map[key]
                            if not existing.field and field:
                                existing.field = field
                            if not existing.end_year and end_yr is not None:
                                existing.end_year = end_yr

        education_list = list(education_map.values())

        # Infer headline if not present
        if not headline:
            latest_experience = None
            latest_date = None
            
            def parse_date_to_compare(dt_str: Optional[str]) -> datetime:
                if not dt_str:
                    return datetime.min
                if dt_str.lower() in ["present", "current", "ongoing"]:
                    return datetime.max
                try:
                    return datetime.strptime(dt_str, "%Y-%m")
                except Exception:
                    try:
                        return datetime.strptime(dt_str, "%Y")
                    except Exception:
                        return datetime.min
                        
            for exp in experience_list:
                if exp.title:
                    exp_start = parse_date_to_compare(exp.start)
                    exp_end = parse_date_to_compare(exp.end)
                    if latest_experience is None:
                        latest_experience = exp
                        latest_date = (exp_end, exp_start)
                    else:
                        current_date = (exp_end, exp_start)
                        if current_date > latest_date:
                            latest_experience = exp
                            latest_date = current_date
                            
            if latest_experience and latest_experience.title:
                headline = latest_experience.title
            elif skills_map:
                top_skills = [s.name for s in list(skills_map.values())[:3]]
                if top_skills:
                    headline = f"{', '.join(top_skills)} Developer"
            else:
                headline = "Candidate"

        # Calculate years_experience
        total_months = 0
        for exp in experience_list:
            if not exp.start:
                continue
            try:
                start_dt = datetime.strptime(exp.start, "%Y-%m")
            except Exception:
                try:
                    start_dt = datetime.strptime(exp.start, "%Y")
                except Exception:
                    continue
            if not exp.end or exp.end.lower() in ["present", "current", "ongoing"]:
                end_dt = datetime.now()
            else:
                try:
                    end_dt = datetime.strptime(exp.end, "%Y-%m")
                except Exception:
                    try:
                        end_dt = datetime.strptime(exp.end, "%Y")
                    except Exception:
                        continue
            diff_months = (end_dt.year - start_dt.year) * 12 + (end_dt.month - start_dt.month) + 1
            if diff_months > 0:
                total_months += diff_months
                
        years_experience = round(total_months / 12.0, 1) if experience_list else 0.0

        # Compute overall confidence (use highest confidence among the merged sources)
        overall_confidence = max([item["confidence"] for item in records_with_confidence]) if records_with_confidence else 0.0

        return Candidate(
            candidate_id=candidate_id,
            full_name=full_name,
            emails=list(emails_set),
            phones=list(phones_set),
            location=location,
            links=links,
            headline=headline,
            years_experience=years_experience,
            skills=list(skills_map.values()),
            experience=experience_list,
            education=education_list,
            provenance=provenance_list,
            overall_confidence=overall_confidence
        )

# Maintain MergerService name mapping for layout compatibility
MergerService = CandidateMerger
