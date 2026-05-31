"""CSV upload router — self-service listing optimization via CSV file upload.

Routes:
  POST /api/csv/upload    → Upload CSV, get optimized listings back
  GET  /api/csv/template  → Download CSV template
  GET  /api/csv/job/{id}  → Check job status
"""
import csv
import io
import os
import uuid
import asyncio
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.csv_optimizer import CSVOptimizerService

router = APIRouter(prefix="/api/csv", tags=["CSV Upload"])

# Instantiate CSV optimizer service
optimizer_service = CSVOptimizerService()

import logging
from core.supabase import get_supabase


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class CSVJobStatus(BaseModel):
    job_id: str
    status: str  # 'processing', 'completed', 'failed'
    row_count: int = 0
    processed: int = 0
    scores_before: list[dict] = []
    scores_after: list[dict] = []
    error: Optional[str] = None


# In-memory job tracking (replace with Supabase for persistence)
_jobs: dict[str, CSVJobStatus] = {}

REQUIRED_COLUMNS = {"asin", "title"}
OPTIONAL_COLUMNS = {"bullets", "description", "brand", "category"}
MAX_ROWS = 50
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/template")
async def download_template():
    """Download a CSV template with the expected column format."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["asin", "title", "bullets", "description", "brand", "category"])
    writer.writerow([
        "B08N5WRWNW",
        "Stainless Steel Water Bottle 32oz - Insulated Vacuum Flask",
        "TRIPLE-WALL VACUUM INSULATION|PERFECT FOR GYM ENTHUSIASTS|LEAK-PROOF LID|BPA-FREE STAINLESS STEEL",
        "Premium insulated water bottle designed for active lifestyles...",
        "HydroMax",
        "water bottles"
    ])
    
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=optimus_rufus_template.csv"}
    )


@router.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    """Upload a CSV of listings for batch COSMO optimization.
    
    Returns a job ID for tracking progress. The optimized CSV can be
    downloaded once processing completes.
    """
    # Validate file type
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a .csv")
    
    # Read file
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large. Max {MAX_FILE_SIZE // (1024*1024)}MB")
    
    # Parse CSV
    try:
        text = contents.decode("utf-8")
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid CSV format: {e}")
    
    if not rows:
        raise HTTPException(status_code=400, detail="CSV is empty")
    
    if len(rows) > MAX_ROWS:
        raise HTTPException(status_code=400, detail=f"Too many rows. Max {MAX_ROWS} listings per upload")
    
    # Validate columns
    headers = set(rows[0].keys())
    missing = REQUIRED_COLUMNS - headers
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required columns: {missing}")
    
    # Create job
    job_id = str(uuid.uuid4())[:8]
    job = CSVJobStatus(
        job_id=job_id,
        status="processing",
        row_count=len(rows),
    )
    _jobs[job_id] = job
    
    # Process in background
    task = asyncio.create_task(_process_csv_job(job_id, rows))
    task.add_done_callback(lambda t: t.exception() and logging.getLogger("csv_upload").error("Job failed", exc_info=t.exception()))
    
    return {"job_id": job_id, "status": "processing", "row_count": len(rows)}


@router.get("/job/{job_id}")
async def get_job_status(job_id: str):
    """Check the status of a CSV optimization job."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job


@router.get("/job/{job_id}/download")
async def download_result(job_id: str):
    """Download the optimized CSV for a completed job."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    if job.status != "completed":
        raise HTTPException(status_code=400, detail=f"Job is still {job.status}")
    
    # Build optimized CSV from scores_after
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "asin", "title_original", "title_optimized",
        "bullets_original", "bullets_optimized",
        "description_original", "description_optimized",
        "score_before", "score_after", "grade_before", "grade_after"
    ])
    
    for before, after in zip(job.scores_before, job.scores_after):
        writer.writerow([
            before.get("asin", ""),
            before.get("title", ""),
            after.get("title", ""),
            before.get("bullets", ""),
            after.get("bullets", ""),
            before.get("description", ""),
            after.get("description", ""),
            before.get("score", 0),
            after.get("score", 0),
            before.get("grade", "F"),
            after.get("grade", "F"),
        ])
    
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=optimized_{job_id}.csv"}
    )


# ---------------------------------------------------------------------------
# Background processing
# ---------------------------------------------------------------------------

def _score_to_grade(s: float) -> str:
    if s >= 80: return "A"
    if s >= 65: return "B"
    if s >= 50: return "C"
    if s >= 35: return "D"
    return "F"


async def _process_csv_job(job_id: str, rows: list[dict]):
    """Process each row through COSMO analysis and agentic optimization."""
    job = _jobs[job_id]
    
    try:
        for i, row in enumerate(rows):
            res = await optimizer_service.optimize_row(row, i)
            
            job.scores_before.append(res["before"])
            job.scores_after.append(res["after"])
            
            job.processed = i + 1
        
        job.status = "completed"
        
        # Persist to Supabase if available
        sb = get_supabase()
        if sb:
            try:
                sb.table("csv_jobs").insert({
                    "id": job_id,
                    "upload_filename": f"upload_{job_id}.csv",
                    "row_count": job.row_count,
                    "status": "completed",
                    "scores_before": job.scores_before,
                    "scores_after": job.scores_after,
                    "completed_at": datetime.utcnow().isoformat(),
                }).execute()
            except Exception:
                logging.exception(f"Failed to persist CSV job {job_id} to Supabase")
                
    except Exception as e:
        job.status = "failed"
        job.error = str(e)
