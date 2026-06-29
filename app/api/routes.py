import json
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional
from app.services.transformer import CandidateTransformer
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)

# Initialize pipeline orchestrator service
transformer = CandidateTransformer()

@router.post("/transform")
async def transform_candidate_data(
    csv_file: Optional[UploadFile] = File(None),
    resume_file: Optional[UploadFile] = File(None),
    config: Optional[str] = Form(None)
):
    """
    HTTP POST transforms, merges, and normalizes candidate data from Recruiter CSV and PDF resumes.
    Projects the canonical candidate output following a dynamic runtime configuration.
    """
    # 1. Input Presence Validation
    if not csv_file and not resume_file:
        logger.error("No input source files uploaded for transformation.")
        raise HTTPException(
            status_code=400,
            detail="At least one candidate source file (CSV or PDF) is required."
        )

    csv_bytes = None
    if csv_file:
        try:
            logger.info(f"Reading CSV UploadFile payload: {csv_file.filename}")
            csv_bytes = await csv_file.read()
        except Exception as e:
            logger.exception("Failed to read CSV file content.")
            raise HTTPException(
                status_code=422,
                detail=f"Failed to read CSV upload file: {str(e)}"
            )

    resume_bytes = None
    if resume_file:
        try:
            logger.info(f"Reading Resume PDF UploadFile payload: {resume_file.filename}")
            resume_bytes = await resume_file.read()
        except Exception as e:
            logger.exception("Failed to read PDF file content.")
            raise HTTPException(
                status_code=422,
                detail=f"Failed to read PDF upload file: {str(e)}"
            )

    config_dict = None
    if config:
        try:
            config_dict = json.loads(config)
        except json.JSONDecodeError as e:
            logger.error(f"Malformed config JSON parameter: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid config JSON syntax: {str(e)}"
            )

    # 2. Delegate transformation execution to candidate transformer orchestrator
    try:
        projected_result = transformer.process(
            csv_bytes=csv_bytes,
            resume_bytes=resume_bytes,
            config_payload=config_dict
        )
        return projected_result
    except ValueError as e:
        logger.error(f"Validation failure during transformation pipeline: {e}")
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        logger.exception("Unexpected server failure during transformation pipeline.")
        raise HTTPException(
            status_code=500,
            detail=f"Candidate transformation pipeline failed: {str(e)}"
        )
