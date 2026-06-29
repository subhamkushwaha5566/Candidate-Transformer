import io
import os
from typing import Any, List, Dict, Optional
import pandas as pd
from app.parsers.base_parser import BaseParser
from app.utils.logger import get_logger

logger = get_logger(__name__)

class CSVParser(BaseParser):
    """
    Concrete parser that processes structured Recruiter CSV files using pandas.
    Handles missing files, malformed CSV records, and unexpected inputs gracefully.
    """
    def parse(self, source: Any) -> List[Dict[str, Any]]:
        """
        Parses a recruiter CSV from a file path, raw bytes, or a file-like stream.
        Returns a list of structured candidate dictionaries.

        Args:
            source: A file path (str), bytes, or a file-like object.

        Returns:
            List[Dict[str, Any]]: List of parsed candidates mapped to candidate schema fields.
        """
        candidates: List[Dict[str, Any]] = []

        try:
            # 1. Load the data into a pandas DataFrame based on input type
            if isinstance(source, str):
                if not os.path.exists(source):
                    logger.error(f"CSV file not found at path: {source}")
                    return []
                df = pd.read_csv(source, dtype=str)
            elif isinstance(source, bytes):
                df = pd.read_csv(io.BytesIO(source), dtype=str)
            elif hasattr(source, "read"):
                # Handle file-like objects (e.g. SpooledTemporaryFile from FastAPI)
                content = source.read()
                if isinstance(content, bytes):
                    df = pd.read_csv(io.BytesIO(content), dtype=str)
                else:
                    df = pd.read_csv(io.StringIO(str(content)), dtype=str)
            else:
                logger.error(f"Unsupported source type for CSV parsing: {type(source)}")
                return []
        except pd.errors.EmptyDataError:
            logger.warning("CSV data is empty.")
            return []
        except pd.errors.ParserError as e:
            logger.error(f"Malformed CSV parsed error: {e}")
            return []
        except Exception as e:
            logger.exception(f"Unexpected error loading CSV data: {e}")
            return []

        # 2. Extract and format rows
        # Expected columns: name, email, phone, current_company, title
        expected_cols = {"name", "email", "phone", "current_company", "title"}
        actual_cols = set(df.columns)

        missing_cols = expected_cols - actual_cols
        if missing_cols:
            logger.warning(f"CSV is missing expected columns: {missing_cols}. Continuing parsing with available columns.")

        # Ensure all expected columns exist in the DataFrame for safe row iteration
        for col in expected_cols:
            if col not in df.columns:
                df[col] = None

        # Clean NaN/Null values to standard Python None
        df = df.where(pd.notnull(df), None)

        for _, row in df.iterrows():
            try:
                candidate_data = self._map_row_to_candidate(row)
                candidates.append(candidate_data)
            except Exception as e:
                logger.error(f"Error mapping CSV row: {row.to_dict()}. Error: {e}")
                # Continue parsing other rows
                continue

        logger.info(f"Successfully parsed {len(candidates)} candidate(s) from CSV source.")
        return candidates

    def _map_row_to_candidate(self, row: Any) -> Dict[str, Any]:
        """
        Maps a single CSV DataFrame row to the canonical candidate dictionary format.
        """
        import math
        def clean_val(val: Any) -> Optional[str]:
            if val is None:
                return None
            if isinstance(val, float) and math.isnan(val):
                return None
            val_str = str(val).strip()
            if val_str.lower() in ["nan", "none", "null", ""]:
                return None
            return val_str

        name = clean_val(row["name"])
        email = clean_val(row["email"])
        phone = clean_val(row["phone"])
        current_company = clean_val(row["current_company"])
        title = clean_val(row["title"])

        emails = [email] if email else []
        phones = [phone] if phone else []

        experience = []
        if current_company or title:
            experience.append({
                "company": current_company,
                "role": title,
                "start_date": None,
                "end_date": None,
                "description": None
            })

        return {
            "full_name": name,
            "emails": emails,
            "phones": phones,
            "headline": title,
            "experience": experience,
            "location": None,
            "links": {
                "linkedin": None,
                "github": None,
                "portfolio": None,
                "other": []
            },
            "years_experience": None,
            "skills": [],
            "education": [],
            "provenance": [],
            "overall_confidence": 0.0
        }
