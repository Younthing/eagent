from __future__ import annotations

import json
from typing import Annotated, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError

from schemas.requests import Rob2Input, Rob2RunOptions
from schemas.responses import Rob2RunResult
from services.rob2_runner import run_rob2

app = FastAPI(title="ROB2 API")


@app.post("/run", response_model=Rob2RunResult)
async def run_rob2_endpoint(
    file: Annotated[Optional[UploadFile], File()] = None,
    pdf_path: Annotated[Optional[str], Form()] = None,
    options: Annotated[Optional[str], Form()] = None,
):
    """
    Run ROB2 evaluation.

    Args:
        file: PDF file to upload.
        pdf_path: Path to PDF file on server (if not uploading).
        options: JSON string of Rob2RunOptions.
    """
    if not file and not pdf_path:
        raise HTTPException(
            status_code=400, detail="Either file or pdf_path must be provided."
        )

    if file and pdf_path:
        raise HTTPException(
            status_code=400, detail="Provide only one of file or pdf_path."
        )

    if file:
        content = await file.read()
        try:
            input_data = Rob2Input(pdf_bytes=content, filename=file.filename)
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=f"Invalid input: {e}")
    else:
        try:
            input_data = Rob2Input(pdf_path=pdf_path)
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=f"Invalid input: {e}")

    options_obj = Rob2RunOptions()
    if options:
        try:
            options_dict = json.loads(options)
            options_obj = Rob2RunOptions.model_validate(options_dict)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid options JSON: {e}")
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=f"Invalid options: {e}")

    try:
        result = await run_in_threadpool(run_rob2, input_data, options_obj)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
