from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseParser(ABC):
    """
    Abstract base class for all source candidate data parsers.
    """
    @abstractmethod
    def parse(self, source: Any) -> Any:
        """
        Parses raw input source and returns structured candidate data.
        """
        pass
