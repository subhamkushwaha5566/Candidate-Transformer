import uuid
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

        # Resolve Candidate ID
        candidate_id = resolve_scalar("candidate_id", ["candidate_id"])
        if not candidate_id:
            candidate_id = "cand_" + str(uuid.uuid4())[:8]

        # Resolve base scalar fields
        full_name = resolve_scalar("full_name", ["full_name"]) or "Unknown Candidate"
        headline = resolve_scalar("headline", ["headline"])
        years_exp_val = resolve_scalar("years_experience", ["years_experience"])

        years_experience = None
        if years_exp_val is not None:
            try:
                years_experience = float(years_exp_val)
            except ValueError:
                pass

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

        # Merge experience array with deep sub-property merging
        experience_map = {}
        for item in records_with_confidence:
            exp_items = item["data"].get("experience", [])
            if isinstance(exp_items, list):
                for exp in exp_items:
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

                    if comp or role:
                        comp_clean = str(comp).strip() if comp else "Unknown Company"
                        role_clean = str(role).strip() if role else "Unknown Role"
                        key = f"{comp_clean.lower()}|{role_clean.lower()}"

                        if key not in experience_map:
                            exp_obj = Experience(
                                company=comp_clean,
                                role=role_clean,
                                start_date=s_date,
                                end_date=e_date,
                                description=desc
                            )
                            experience_map[key] = exp_obj
                            provenance_list.append(Provenance(
                                field="experience",
                                source=item["source"],
                                confidence=item["confidence"],
                                extracted_at=item["timestamp"],
                                raw_value={"company": comp, "role": role}
                            ))
                        else:
                            # Fallback writers populate missing fields
                            existing = experience_map[key]
                            if not existing.start_date and s_date:
                                existing.start_date = s_date
                            if not existing.end_date and e_date:
                                existing.end_date = e_date
                            if not existing.description and desc:
                                existing.description = desc

        experience_list = list(experience_map.values())

        # Merge education array with deep sub-property merging
        education_map = {}
        for item in records_with_confidence:
            edu_items = item["data"].get("education", [])
            if isinstance(edu_items, list):
                for edu in edu_items:
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

                    if inst:
                        inst_clean = str(inst).strip()
                        deg_clean = str(deg).strip() if deg else ""
                        key = f"{inst_clean.lower()}|{deg_clean.lower()}"

                        if key not in education_map:
                            edu_obj = Education(
                                institution=inst_clean,
                                degree=deg_clean if deg_clean else None,
                                field_of_study=field,
                                start_date=s_date,
                                end_date=e_date
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
                            # Fallback writers populate missing fields
                            existing = education_map[key]
                            if not existing.field_of_study and field:
                                existing.field_of_study = field
                            if not existing.start_date and s_date:
                                existing.start_date = s_date
                            if not existing.end_date and e_date:
                                existing.end_date = e_date

        education_list = list(education_map.values())

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
