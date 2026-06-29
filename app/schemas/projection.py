from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Union
from enum import Enum

class OnMissingBehavior(str, Enum):
    """
    Action to take when a selected output field is missing.
    """
    NULL = "null"
    OMIT = "omit"
    ERROR = "error"

class OutputConfig(BaseModel):
    """
    Runtime configurations dynamically applied to candidate output projection.
    """
    fields: Optional[List[Union[str, Dict[str, Any]]]] = None  # Subset of fields to select
    rename_map: Optional[Dict[str, str]] = None  # Mapping of old field names to new names
    include_confidence: bool = True
    include_provenance: bool = True
    on_missing: OnMissingBehavior = OnMissingBehavior.NULL
