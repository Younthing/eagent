import os
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, HTTPException, Query
from starlette.background import BackgroundTasks

from cli.commands.shared import load_doc_structure
from schemas.internal.documents import DocStructure

router = APIRouter()

def cleanup_file(path: Path):
    if path.exists():
        os.remove(path)

@router.post("/preprocess", response_model=DocStructure, tags=["Pipeline"])
async def preprocess_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    drop_references: bool = Query(True, description="Drop reference sections from the document."),
    reference_titles: str | None = Query(None, description="Comma-separated list of reference section titles to identify and drop."),
):
    """
    Process a PDF document and return its structured representation.
    
    This endpoint:
    1. Uploads the PDF.
    2. Parses it using Docling.
    3. (Optional) Filters out reference sections.
    4. Returns the structured content (body, sections, etc.).
    """
    
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    # Create temp file
    suffix = Path(file.filename).suffix
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp_path = Path(tmp.name)
        shutil.copyfileobj(file.file, tmp)
        tmp.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save upload: {e}")

    # Schedule cleanup
    background_tasks.add_task(cleanup_file, tmp_path)

    try:
        # We need to run this potentially heavy sync operation. 
        # In a real production app, this should be offloaded to a worker or run_in_executor.
        # For this example, we'll run it directly (FastAPI runs async defs in event loop, 
        # so this might block if not careful, but load_doc_structure is sync).
        # To avoid blocking the event loop, we should use run_in_executor or define this as `def` instead of `async def`.
        # However, FastAPI runs `def` routes in a threadpool. `async def` runs in main loop.
        # Since I used `async def` above (for file I/O which is async-ish in FastAPI), 
        # I should probably just change the route to `def` OR use run_in_executor.
        # But wait, `file.read()` is async. `shutil.copyfileobj` is sync.
        # `file.file` is a standard python file object (SpooledTemporaryFile).
        
        # Let's change the function to `def` to let FastAPI run it in a threadpool, 
        # BUT `UploadFile` methods are async. 
        # Actually `file.file` is synchronous file-like object.
        # `file.read()` is async.
        
        # Best practice: keep `async def` and use `run_in_threadpool` or just `to_thread`.
        from fastapi.concurrency import run_in_threadpool
        
        doc_structure = await run_in_threadpool(
            load_doc_structure,
            tmp_path,
            drop_references=drop_references,
            reference_titles=reference_titles
        )
        
        return doc_structure

    except Exception as e:
        # cleanup if we crash before background task
        # actually background tasks run after response.
        # if we raise here, background tasks might not run? 
        # FastAPI background tasks run even if exception? No, only on success response usually.
        # So I should cleanup here if exception.
        cleanup_file(tmp_path)
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
