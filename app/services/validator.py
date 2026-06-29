import json
from typing import Any, Dict, List
from pydantic import ValidationError
from app.schemas.candidate import Candidate
from app.schemas.projection import OutputConfig
from app.utils.logger import get_logger

logger = get_logger(__name__)

class CandidateValidator:
    """
    Validates output payload structures, required properties, JSON serializability,
    and runtime config schemas, raising descriptive exceptions.
    """
    def validate_profile(self, profile: Candidate) -> bool:
        """
        Validates the integrity rules of the canonical Pydantic Candidate profile.
        """
        if not profile:
            raise ValueError("Candidate profile cannot be None.")
        if not profile.candidate_id or not profile.candidate_id.strip():
            raise ValueError("Candidate profile must have a valid candidate_id.")
        if not profile.full_name or not profile.full_name.strip():
            raise ValueError("Candidate profile must have a valid full_name.")
        return True

    def validate_runtime_config_schema(self, config: Any) -> bool:
        """
        Validates that the provided runtime config conforms to the OutputConfig schema.
        Raises ValueError with detail description on validation errors.
        """
        if config is None:
            return True

        try:
            if isinstance(config, str):
                config_dict = json.loads(config)
                OutputConfig(**config_dict)
            elif isinstance(config, dict):
                OutputConfig(**config)
            elif isinstance(config, OutputConfig):
                pass
            else:
                raise TypeError(f"Config must be a JSON string, dict, or OutputConfig. Got {type(config)}")
        except (ValidationError, json.JSONDecodeError, TypeError) as e:
            logger.error(f"Runtime config schema validation failed: {e}")
            raise ValueError(f"Invalid runtime configuration schema: {e}")

        return True

    def validate_output_json(self, output: Dict[str, Any]) -> bool:
        """
        Verifies that the output is a valid dict and can be successfully serialized to JSON.
        Raises ValueError if serialization fails.
        """
        if not isinstance(output, dict):
            raise TypeError(f"Output payload must be a dictionary. Got {type(output)}")

        try:
            # Force serialization check
            json.dumps(output)
        except (TypeError, OverflowError) as e:
            logger.error(f"Output dictionary is not JSON serializable: {e}")
            raise ValueError(f"Output candidate structure is not JSON serializable: {e}")

        return True

    def validate_required_fields(self, output: Dict[str, Any], required_fields: List[str]) -> bool:
        """
        Checks that all specified required fields are present in the projected dictionary
        and contain non-empty values. Raises ValueError if validation fails.
        """
        missing_fields = []
        for field in required_fields:
            if field not in output:
                missing_fields.append(field)
            else:
                val = output[field]
                # Consider None or empty/whitespace strings as missing
                if val is None or (isinstance(val, str) and not val.strip()):
                    missing_fields.append(field)

        if missing_fields:
            logger.error(f"Required fields are missing or empty: {missing_fields}")
            raise ValueError(f"Required fields are missing or empty: {missing_fields}")

        return True

# Maintain compatibility with stubs
ValidatorService = CandidateValidator
