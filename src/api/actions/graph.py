from fastapi import APIRouter, File, UploadFile, HTTPException, Form
from fastapi.concurrency import run_in_threadpool
from pydantic import Json

from schemas.requests import Rob2Input, Rob2RunOptions
from schemas.responses import Rob2RunResult
from services.rob2_runner import run_rob2

router = APIRouter()

@router.post("/run", response_model=Rob2RunResult, tags=["Pipeline"])
async def run_pipeline(
    file: UploadFile = File(...),
    options: Json[Rob2RunOptions] | None = Form(None), 
):
    """
    Run the full ROB2 pipeline on a PDF document.
    """
    filename = file.filename
    if not filename or not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    
    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {e}")
    
    input_data = Rob2Input(
        pdf_bytes=content,
        filename=filename
    )
    
    try:
        # run_rob2 is blocking, so we run it in a threadpool
        result = await run_in_threadpool(
            run_rob2,
            input_data=input_data,
            options=options or Rob2RunOptions()
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline execution failed: {str(e)}")
