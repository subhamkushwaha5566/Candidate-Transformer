import json
import re
from typing import Any, Dict, List, Optional, Union
from app.schemas.candidate import Candidate
from app.utils.logger import get_logger

logger = get_logger(__name__)

def parse_path_tokens(path_str: str) -> List[Union[str, int]]:
    """
    Parses field paths like 'emails[0]' or 'location.city' into key and index tokens.
    """
    # Split by dot or lookahead index brackets
    parts = re.split(r"\.|(?=\[)", path_str)
    tokens = []
    for part in parts:
        if not part:
            continue
        if part.startswith("["):
            match = re.match(r"\[(\d+)\]", part)
            if match:
                tokens.append(int(match.group(1)))
        else:
            tokens.append(part)
    return tokens

def resolve_value(data: Any, tokens: List[Union[str, int]]) -> Any:
    """
    Traverses a nested structure using token paths.
    """
    curr = data
    for token in tokens:
        if isinstance(token, int):
            if isinstance(curr, list):
                if 0 <= token < len(curr):
                    curr = curr[token]
                else:
                    return None
            else:
                return None
        else:
            if isinstance(curr, dict):
                curr = curr.get(token)
            elif hasattr(curr, token):
                curr = getattr(curr, token)
            else:
                return None
    return curr

class ProjectionEngine:
    """
    Filters, renames, and formats canonical candidate objects based on runtime configuration.
    """
    def project(self, candidate: Candidate, config: Any) -> Dict[str, Any]:
        """
        Applies a runtime projection configuration on a Candidate profile.

        Args:
            candidate: The canonical Candidate object.
            config: A JSON string, dictionary, or OutputConfig Pydantic model.

        Returns:
            Dict[str, Any]: The projected dictionary output.
        """
        # 1. Parse configuration into standard dict format
        config_dict = {}
        if isinstance(config, str):
            try:
                config_dict = json.loads(config)
            except Exception as e:
                logger.error(f"Failed to parse runtime config JSON string: {e}")
                config_dict = {}
        elif isinstance(config, dict):
            config_dict = config
        elif hasattr(config, "model_dump"):
            config_dict = config.model_dump()

        # Extract options with defaults
        fields = config_dict.get("fields")
        include_confidence = config_dict.get("include_confidence", True)
        include_provenance = config_dict.get("include_provenance", True)
        
        # Normalize missing value behavior (null, omit, error)
        on_missing = str(config_dict.get("on_missing", "null")).lower()

        # Deep copy to ensure projection isolation and prevent mutation
        candidate_copy = candidate.model_copy(deep=True)
        candidate_dict = candidate_copy.model_dump()
        projected: Dict[str, Any] = {}

        # 2. Extract and rename fields
        if fields is not None:
            for f in fields:
                if isinstance(f, dict):
                    target_key = f.get("path")
                    source_path = f.get("from", target_key)
                else:
                    # Fallback for simple list of field names ["full_name", "emails"]
                    target_key = str(f)
                    source_path = str(f)

                if not target_key:
                    continue

                tokens = parse_path_tokens(source_path)
                val = resolve_value(candidate_dict, tokens)

                # Check if resolved value is missing (None or empty/whitespace string)
                if val is None or (isinstance(val, str) and not val.strip()):
                    if on_missing == "error":
                        raise ValueError(f"Required field path '{source_path}' is missing.")
                    elif on_missing == "omit":
                        continue
                    else:  # "null"
                        projected[target_key] = None
                else:
                    projected[target_key] = val
        else:
            # If fields subset is not defined, project all standard Candidate fields
            standard_fields = [
                "candidate_id", "full_name", "emails", "phones", "location",
                "links", "headline", "years_experience", "skills", "experience", "education"
            ]
            for key in standard_fields:
                val = candidate_dict.get(key)
                if val is None or (isinstance(val, str) and not val.strip()):
                    if on_missing == "error":
                        raise ValueError(f"Required field '{key}' is missing.")
                    elif on_missing == "omit":
                        continue
                    else:  # "null"
                        projected[key] = None
                else:
                    projected[key] = val

        # 3. Handle confidence metadata
        if include_confidence:
            projected["overall_confidence"] = candidate_dict.get("overall_confidence", 0.0)

        # 4. Handle provenance metadata
        if include_provenance:
            projected["provenance"] = candidate_dict.get("provenance", [])

        return projected

# Maintain compatibility with stubs
ProjectorService = ProjectionEngine
