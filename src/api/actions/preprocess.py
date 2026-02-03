import os
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from starlette.background import BackgroundTasks

from core.config import get_settings
from pipelines.graphs.nodes.preprocess import parse_docling_pdf, filter_reference_sections
from schemas.internal.documents import DocStructure

router = APIRouter()

def cleanup_file(path: Path):
    if path.exists():
        os.remove(path)

def _process_pdf(
    pdf_path: Path,
    drop_references: bool,
    reference_titles: str | None,
) -> DocStructure:
    settings = get_settings()
    doc_structure = parse_docling_pdf(pdf_path)
    
    if drop_references:
        if reference_titles is None:
            reference_titles = settings.preprocess_reference_titles
        doc_structure = filter_reference_sections(
            doc_structure, reference_titles=reference_titles
        )
    return doc_structure

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
    
    filename = file.filename
    if not filename or not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    # Create temp file
    suffix = Path(filename).suffix
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
        doc_structure = await run_in_threadpool(
            _process_pdf,
            tmp_path,
            drop_references=drop_references,
            reference_titles=reference_titles
        )
        
        return doc_structure

    except Exception as e:
        cleanup_file(tmp_path)
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
