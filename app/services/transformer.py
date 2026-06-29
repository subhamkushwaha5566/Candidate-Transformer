from typing import Dict, Any, List, Optional
from app.parsers.csv_parser import CSVParser
from app.parsers.resume_parser import ResumeParser
from app.services.normalizer import Normalizer
from app.services.merger import CandidateMerger
from app.services.confidence import ConfidenceEngine
from app.services.projector import ProjectionEngine
from app.services.validator import CandidateValidator
from app.utils.logger import get_logger

logger = get_logger(__name__)

class CandidateTransformer:
    """
    Orchestrates the entire candidate ingestion, normalization,
    merging, confidence scoring, output projection, and validation pipeline.
    """
    def __init__(self):
        self.csv_parser = CSVParser()
        self.resume_parser = ResumeParser()
        self.normalizer = Normalizer()
        self.merger = CandidateMerger()
        self.confidence_engine = ConfidenceEngine()
        self.projector = ProjectionEngine()
        self.validator = CandidateValidator()

    def process(
        self,
        csv_bytes: Optional[bytes] = None,
        resume_bytes: Optional[bytes] = None,
        config_payload: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Executes the candidate data transformation pipeline.

        Args:
            csv_bytes: Raw bytes from the uploaded CSV.
            resume_bytes: Raw bytes from the uploaded PDF resume.
            config_payload: Runtime output configuration (JSON string, dict, or model).

        Returns:
            Dict[str, Any]: The fully projected and validated canonical candidate dictionary.
        """
        if not csv_bytes and not resume_bytes:
            logger.error("No source data bytes provided.")
            raise ValueError("At least one candidate source file (CSV or PDF) is required.")

        raw_records: List[Dict[str, Any]] = []

        # 1. Parse CSV source
        if csv_bytes:
            logger.info("Ingesting CSV source.")
            csv_candidates = self.csv_parser.parse(csv_bytes)
            for cand in csv_candidates:
                cand["source"] = "csv"
                raw_records.append(cand)

        # 2. Parse Resume PDF source
        if resume_bytes:
            logger.info("Ingesting Resume PDF source.")
            resume_candidate = self.resume_parser.parse(resume_bytes)
            # Ensure PDF parsing extracted relevant identifiers before appending
            if resume_candidate.get("full_name") or resume_candidate.get("emails") or resume_candidate.get("phones"):
                resume_candidate["source"] = "resume"
                raw_records.append(resume_candidate)

        if not raw_records:
            logger.error("No candidate data could be parsed from inputs.")
            raise ValueError("No valid candidate data could be parsed from the provided files.")

        # 3. Normalize parsed records
        normalized_records: List[Dict[str, Any]] = []
        for rec in raw_records:
            try:
                normalized_records.append(self.normalizer.normalize_record(rec))
            except Exception as e:
                logger.exception(f"Normalization failed for record: {rec}")
                raise ValueError(f"Normalization failure: {str(e)}")

        # 4. Merge duplicate records using source confidence priorities
        try:
            merged_candidate = self.merger.merge(normalized_records)
        except Exception as e:
            logger.exception("Merging candidate records failed.")
            raise ValueError(f"Merging and conflict resolution failed: {str(e)}")

        # 5. Compute overall confidence score
        try:
            overall_conf = self.confidence_engine.calculate_overall_confidence(merged_candidate)
            merged_candidate.overall_confidence = overall_conf
        except Exception as e:
            logger.exception("Failed to compute candidate overall confidence.")
            raise ValueError(f"Confidence score calculation failed: {str(e)}")

        # 6. Validate runtime configuration schema
        self.validator.validate_runtime_config_schema(config_payload)

        # 7. Apply projection mapping and formatting
        try:
            projected_output = self.projector.project(merged_candidate, config_payload)
        except Exception as e:
            logger.exception("Candidate projection mapping failed.")
            raise ValueError(f"Output projection failed: {str(e)}")

        # 8. Run final JSON and field completeness validations
        self.validator.validate_output_json(projected_output)

        # Enforce name validation unless omitted explicitly by the output config
        on_missing = "null"
        if isinstance(config_payload, dict):
            on_missing = str(config_payload.get("on_missing", "null")).lower()
        elif isinstance(config_payload, str) and config_payload.strip():
            try:
                on_missing = str(json.loads(config_payload).get("on_missing", "null")).lower()
            except Exception:
                pass
        
        if "full_name" in projected_output or on_missing != "omit":
            self.validator.validate_required_fields(projected_output, ["full_name"])

        logger.info("Candidate transformation pipeline executed successfully.")
        return projected_output
