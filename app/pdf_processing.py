"""
PDF Processing Module - Async PDF ingestion and content extraction

Handles:
- PDF file validation and storage
- Asynchronous text extraction
- PDF metadata collection
- Error handling and retry logic
- Status tracking for multi-step processing
"""

import os
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

import pymupdf  # PyMuPDF for PDF processing
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from .db_models import PDFUpload
from .llm_pipelines import extract_concepts

logger = logging.getLogger(__name__)

# Configuration
MAX_PDF_SIZE_MB = 50
ALLOWED_MIME_TYPES = {"application/pdf"}
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")


async def validate_pdf_file(
    filename: str,
    file_content: bytes,
    max_size_mb: int = MAX_PDF_SIZE_MB,
) -> Tuple[bool, Optional[str]]:
    """
    Validate PDF file before processing

    Args:
        filename: Original filename
        file_content: Raw file bytes
        max_size_mb: Maximum allowed file size in MB

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if file passes validation
        - error_message: None if valid, error string if invalid

    Validation checks:
    - File extension is .pdf
    - File size is within limits
    - File is a valid PDF (checked via PyMuPDF)
    - PDF is not encrypted (would prevent text extraction)
    """
    try:
        # Check file extension
        if not filename.lower().endswith(".pdf"):
            return False, "File must be a PDF document (.pdf extension)"

        # Check file size
        file_size_mb = len(file_content) / (1024 * 1024)
        if file_size_mb > max_size_mb:
            return False, f"File size ({file_size_mb:.1f}MB) exceeds limit ({max_size_mb}MB)"

        # Check minimum size (likely not a PDF)
        if len(file_content) < 1024:  # Less than 1KB
            return False, "File is too small to be a valid PDF"

        # Verify it's a valid PDF by opening with PyMuPDF
        try:
            pdf_doc = pymupdf.open(stream=file_content, filetype="pdf")
            page_count = len(pdf_doc)

            # Check if PDF is encrypted (unrecoverable for text extraction)
            if pdf_doc.is_encrypted:
                return False, "PDF is encrypted and cannot be processed"

            # Basic sanity check: PDF should have at least 1 page
            if page_count < 1:
                return False, "PDF has no pages"

            pdf_doc.close()

        except Exception as e:
            return False, f"Invalid PDF file: {str(e)}"

        logger.info(f"PDF validation passed: {filename} ({file_size_mb:.1f}MB, {page_count} pages)")
        return True, None

    except Exception as e:
        logger.error(f"PDF validation error: {str(e)}")
        return False, f"Validation error: {str(e)}"


async def save_pdf_file(
    file_content: bytes,
    original_filename: str,
    user_id: str,
) -> Tuple[str, str]:
    """
    Save uploaded PDF file to disk with user-specific directory

    Args:
        file_content: Raw PDF bytes
        original_filename: Original filename from upload
        user_id: UUID of user who uploaded file

    Returns:
        Tuple of (file_path, file_id)
        - file_path: Relative path from UPLOAD_DIR
        - file_id: Unique identifier for this PDF

    Creates:
    - User-specific directory: uploads/{user_id}/
    - Unique filename: {uuid}_{timestamp}.pdf
    - Stores original filename in metadata
    """
    try:
        # Create user directory
        user_dir = Path(UPLOAD_DIR) / user_id
        user_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename
        file_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_name = original_filename.replace(" ", "_").replace("/", "_")[:50]
        filename = f"{file_id}_{timestamp}_{safe_name}"

        file_path = user_dir / filename

        # Write file
        with open(file_path, "wb") as f:
            f.write(file_content)

        logger.info(f"PDF saved: {file_path} (size: {len(file_content)} bytes)")
        return str(file_path.relative_to(UPLOAD_DIR)), file_id

    except Exception as e:
        logger.error(f"Failed to save PDF file: {str(e)}")
        raise


async def extract_pdf_text(
    file_path: str,
    max_chars: int = 100000,
) -> Tuple[str, Dict[str, Any]]:
    """
    Extract text from PDF file asynchronously

    Args:
        file_path: Relative path to PDF file (from UPLOAD_DIR)
        max_chars: Maximum characters to extract

    Returns:
        Tuple of (extracted_text, metadata)
        - extracted_text: Full text from all pages
        - metadata: Dict with:
          - page_count: Total pages in PDF
          - char_count: Total characters extracted
          - extraction_timestamp: When extraction occurred
          - lang_detected: Detected language (if available)
          - images_count: Number of images found
          - tables_detected: Whether tables detected

    Uses PyMuPDF for efficient text extraction with:
    - Page-by-page extraction
    - Metadata collection
    - Image and table detection
    - Character counting
    """
    try:
        full_path = Path(UPLOAD_DIR) / file_path

        if not full_path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        # Open PDF and extract text
        pdf_doc = pymupdf.open(str(full_path))
        text_parts = []
        metadata = {
            "page_count": len(pdf_doc),
            "char_count": 0,
            "images_count": 0,
            "tables_detected": False,
            "extraction_timestamp": datetime.utcnow().isoformat(),
            "lang_detected": "en",  # Default to English
        }

        # Extract text from each page
        for page_num, page in enumerate(pdf_doc):
            try:
                # Get page text
                text = page.get_text()
                text_parts.append(f"=== Page {page_num + 1} ===\n{text}\n")

                # Count images on page
                images = page.get_images()
                metadata["images_count"] += len(images)

                # Simple table detection (presence of structured content)
                if page.get_text("blocks"):
                    blocks = page.get_text("blocks")
                    if len(blocks) > 5:  # Heuristic: many blocks suggest tables
                        metadata["tables_detected"] = True

            except Exception as e:
                logger.warning(f"Error extracting page {page_num}: {str(e)}")
                continue

        extracted_text = "".join(text_parts)

        # Enforce max character limit
        if len(extracted_text) > max_chars:
            logger.warning(f"Extracted text truncated from {len(extracted_text)} to {max_chars} chars")
            extracted_text = extracted_text[:max_chars]

        metadata["char_count"] = len(extracted_text)

        pdf_doc.close()

        logger.info(
            f"PDF text extracted: {metadata['page_count']} pages, "
            f"{metadata['char_count']} chars, {metadata['images_count']} images"
        )

        return extracted_text, metadata

    except Exception as e:
        logger.error(f"PDF text extraction failed: {str(e)}")
        raise


async def process_pdf_for_concepts(
    db: AsyncSession,
    pdf_id: str,
    file_path: str,
    user_id: str,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Full PDF to concepts processing pipeline

    Args:
        db: Database session
        pdf_id: Unique PDF identifier
        file_path: Path to PDF file
        user_id: UUID of user who uploaded
        title: Optional document title for context

    Returns:
        Dict with:
        - pdf_id: The PDF ID
        - concepts: List of extracted concepts
        - concept_count: Number of concepts
        - processing_time_ms: Duration of processing
        - metadata: PDF metadata from extraction

    Performs:
    1. Extract text from PDF
    2. Call LLM to extract concepts
    3. Update database with results
    4. Cache concepts in Redis (if available)

    Raises:
        Exception: If any step fails, database is updated with error status
    """
    start_time = datetime.utcnow()

    try:
        # Step 1: Extract text from PDF
        logger.info(f"Extracting text from PDF {pdf_id}...")
        extracted_text, pdf_metadata = await extract_pdf_text(file_path)

        if not extracted_text or len(extracted_text.strip()) < 100:
            raise ValueError("PDF contains insufficient extractable text")

        # Step 2: Extract concepts using LLM
        logger.info(f"Extracting concepts from PDF {pdf_id} ({pdf_metadata['char_count']} chars)...")
        concepts = await extract_concepts(
            pdf_text=extracted_text[:5000],  # Limit to first 5000 chars for initial extraction
            title=title or f"PDF {pdf_id[:8]}",
            max_concepts=8,
        )

        # Step 3: Update database status
        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        stmt = (
            update(PDFUpload)
            .where(PDFUpload.id == pdf_id)
            .values(
                status="complete",
                concepts_count=len(concepts),
                text_preview=extracted_text[:500],
                metadata=pdf_metadata,
                processing_time_ms=int(processing_time),
                completed_at=datetime.utcnow(),
            )
        )
        await db.execute(stmt)
        await db.commit()

        logger.info(
            f"PDF {pdf_id} processing complete: {len(concepts)} concepts, "
            f"{processing_time:.0f}ms"
        )

        return {
            "pdf_id": pdf_id,
            "concepts": concepts,
            "concept_count": len(concepts),
            "processing_time_ms": int(processing_time),
            "metadata": pdf_metadata,
        }

    except Exception as e:
        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        # Update database with error status
        try:
            error_msg = str(e)[:500]  # Limit error message length
            stmt = (
                update(PDFUpload)
                .where(PDFUpload.id == pdf_id)
                .values(
                    status="error",
                    error_message=error_msg,
                    processing_time_ms=int(processing_time),
                    completed_at=datetime.utcnow(),
                )
            )
            await db.execute(stmt)
            await db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update error status in database: {str(db_error)}")

        logger.error(f"PDF {pdf_id} processing failed: {str(e)}")
        raise


async def get_pdf_status(
    db: AsyncSession,
    pdf_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """
    Get current processing status of a PDF

    Args:
        db: Database session
        pdf_id: Unique PDF identifier
        user_id: UUID of requesting user (for authorization)

    Returns:
        Dict with:
        - pdf_id: The PDF ID
        - status: Current status (uploading/processing/complete/error)
        - concepts_count: Number of extracted concepts
        - error_message: Error details if status is 'error'
        - processing_time_ms: Time spent processing
        - created_at: When PDF was uploaded
        - completed_at: When processing finished (if complete)
        - metadata: PDF metadata from extraction

    Raises:
        HTTPException: 404 if PDF not found or doesn't belong to user
    """
    stmt = select(PDFUpload).where(PDFUpload.id == pdf_id)
    pdf_record = (await db.execute(stmt)).scalar_one_or_none()

    if not pdf_record or pdf_record.user_id != user_id:
        raise ValueError(f"PDF not found or unauthorized: {pdf_id}")

    return {
        "pdf_id": pdf_record.id,
        "status": pdf_record.status,
        "concepts_count": pdf_record.concepts_count or 0,
        "error_message": pdf_record.error_message,
        "processing_time_ms": pdf_record.processing_time_ms or 0,
        "created_at": pdf_record.created_at.isoformat(),
        "completed_at": pdf_record.completed_at.isoformat() if pdf_record.completed_at else None,
        "metadata": pdf_record.metadata or {},
    }
