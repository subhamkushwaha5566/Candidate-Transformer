from typing import List, Optional, Dict, Any
from app.schemas.candidate import Candidate, CandidateProfile
from app.utils.logger import get_logger

logger = get_logger(__name__)

class ConfidenceEngine:
    """
    Computes field-level and overall profile confidence scores for candidate data.
    """
    def score(self, source_trust: float, extraction_confidence: float, normalization_confidence: float) -> float:
        """
        Computes a field's extraction confidence score.

        Formula:
            source_trust * extraction_confidence * normalization_confidence
        """
        return float(source_trust * extraction_confidence * normalization_confidence)

    def calculate_overall_confidence(
        self, 
        candidate: Candidate, 
        important_fields: Optional[List[str]] = None,
        raw_records: Optional[List[Dict[str, Any]]] = None
    ) -> float:
        """
        Computes the overall candidate profile confidence using a weighted formula:
            40% source reliability + 35% field completeness + 25% conflict consistency

        Args:
            candidate: The final merged Candidate profile object.
            important_fields: A list of field names that are critical for completeness evaluation.
                              Defaults to ["full_name", "emails", "phones", "skills"].
            raw_records: The list of raw parsed and normalized candidate records prior to merging.

        Returns:
            float: Average confidence score of important fields (between 0.0 and 1.0).
        """
        if important_fields is None:
            important_fields = ["full_name", "emails", "phones", "skills", "experience", "education", "location.city", "location.country"]

        # 1. Source Reliability (40%)
        source_weights = {
            "csv": 0.95,
            "ats": 0.95,
            "resume": 0.85,
            "notes": 0.60
        }
        
        sources_present = set(p.source.lower() for p in candidate.provenance)
        if sources_present:
            source_reliability = sum(source_weights.get(src, 0.50) for src in sources_present) / len(sources_present)
        else:
            source_reliability = 0.0

        # 2. Field Completeness (35%)
        def is_field_complete(cand: Candidate, field: str) -> bool:
            parts = field.split(".")
            curr: Any = cand
            for part in parts:
                if curr is None:
                    return False
                if isinstance(curr, list):
                    return len(curr) > 0
                if isinstance(curr, dict):
                    curr = curr.get(part)
                else:
                    curr = getattr(curr, part, None)
                    
            if curr is None:
                return False
            if isinstance(curr, str):
                return bool(curr.strip() and curr != "Unknown Candidate" and curr != "Unknown Company" and curr != "Unknown Title")
            if isinstance(curr, list):
                return len(curr) > 0
            return True

        if important_fields:
            completed_count = sum(1 for f in important_fields if is_field_complete(candidate, f))
            field_completeness = completed_count / len(important_fields)
        else:
            field_completeness = 0.0

        # 3. Conflict Consistency (25%)
        conflict_consistency = 1.0
        if raw_records and len(raw_records) > 1:
            consistency_scores = []
            
            # Helper to get nested value from dict
            def get_nested(d: Dict[str, Any], path: str) -> Any:
                parts = path.split(".")
                curr = d
                for part in parts:
                    if isinstance(curr, dict):
                        curr = curr.get(part)
                    else:
                        return None
                return curr

            # Scalar fields: full_name, location.country, headline
            scalar_fields = ["full_name", "location.country", "headline"]
            for field in scalar_fields:
                vals = []
                for r in raw_records:
                    val = get_nested(r, field)
                    if val is not None and str(val).strip() != "":
                        vals.append(str(val).strip().lower())
                if len(vals) > 1:
                    if len(set(vals)) == 1:
                        consistency_scores.append(1.0)
                    else:
                        consistency_scores.append(0.4)

            # List fields: emails, phones
            list_fields = ["emails", "phones"]
            for field in list_fields:
                sets = []
                for r in raw_records:
                    val = r.get(field)
                    if isinstance(val, list) and val:
                        sets.append(set(str(v).strip().lower() for v in val if v))
                if len(sets) > 1:
                    union = set().union(*sets)
                    intersection = set.intersection(*sets)
                    if union == intersection:
                        consistency_scores.append(1.0)
                    elif intersection:
                        consistency_scores.append(0.8)
                    else:
                        consistency_scores.append(0.3)

            if consistency_scores:
                conflict_consistency = sum(consistency_scores) / len(consistency_scores)

        # Calculate final overall weighted confidence score
        overall_confidence = (0.40 * source_reliability) + (0.35 * field_completeness) + (0.25 * conflict_consistency)
        
        # Apply realistic penalties
        penalties = 0.0
        
        # 1. Unstructured PDF parsing uncertainty penalty
        if "resume" in sources_present:
            penalties += 0.05
            
        # 2. Location completeness check
        if not candidate.location or not (candidate.location.city and candidate.location.country):
            penalties += 0.05
            
        # 3. Experience detail completeness check
        if candidate.experience:
            for exp in candidate.experience:
                if not exp.summary or not exp.summary.strip():
                    penalties += 0.03
                    break
        else:
            penalties += 0.05
            
        # 4. Years of experience check
        if candidate.years_experience is None or candidate.years_experience < 1.0:
            penalties += 0.02
            
        # 5. Education detail completeness check
        if candidate.education:
            for edu in candidate.education:
                if not edu.field or not edu.field.strip():
                    penalties += 0.02
                    break
        else:
            penalties += 0.05
            
        # 6. Headline check
        if not candidate.headline or candidate.headline.lower() == "candidate":
            penalties += 0.03

        overall_confidence = max(0.0, min(1.0, overall_confidence - penalties))

        logger.info(
            f"Confidence breakdown: Source={source_reliability:.4f}, Completeness={field_completeness:.4f}, "
            f"Consistency={conflict_consistency:.4f}, Penalties={penalties:.4f} -> Overall={overall_confidence:.4f}"
        )
        return float(overall_confidence)

# Maintain alias compatibility
ConfidenceService = ConfidenceEngine
