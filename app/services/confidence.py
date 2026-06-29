from typing import List, Optional
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

    def calculate_overall_confidence(self, candidate: Candidate, important_fields: Optional[List[str]] = None) -> float:
        """
        Computes the overall candidate profile confidence as the average score of important fields.
        Pulls confidence details from the candidate's provenance record.

        Args:
            candidate: The final Candidate profile object.
            important_fields: A list of field names that are critical for profile evaluation.
                              Defaults to ["full_name", "emails", "phones", "skills"].

        Returns:
            float: Average confidence score of important fields (between 0.0 and 1.0).
        """
        if important_fields is None:
            important_fields = ["full_name", "emails", "phones", "skills"]

        if not important_fields:
            logger.warning("No important fields specified for overall confidence calculation. Returning 0.0.")
            return 0.0

        field_scores = []
        for field in important_fields:
            # Check for exact field name or nested path matches (like location.city)
            matching_provs = [
                p for p in candidate.provenance 
                if p.field == field or p.field.startswith(field + ".")
            ]

            if matching_provs:
                # Average the confidence scores if there are multiple values (e.g. multiple emails/phones)
                avg_score = sum(p.confidence for p in matching_provs) / len(matching_provs)
                field_scores.append(avg_score)
            else:
                # Missing important fields get a confidence score of 0.0
                field_scores.append(0.0)

        overall_score = sum(field_scores) / len(field_scores)
        logger.info(f"Computed overall confidence score: {overall_score:.4f} based on fields: {important_fields}")
        return float(overall_score)

# Maintain alias compatibility
ConfidenceService = ConfidenceEngine
