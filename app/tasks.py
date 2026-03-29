"""
Celery Background Tasks for Async PDF Processing

Handles:
- Asynchronous PDF processing via Celery
- Task status tracking and monitoring
- Retry logic with exponential backoff
- Error handling and alerting
- Task queuing and result caching
"""

import logging
import os
from datetime import datetime

from celery import Celery, Task
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import update, select

from .config import DATABASE_URL
from .db_models import PDFUpload
from .pdf_processing import extract_pdf_text, process_pdf_for_concepts

logger = logging.getLogger(__name__)

# Initialize Celery app
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

celery_app = Celery(
    "eduvision",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Retry configuration
    task_autoretry_for=(Exception,),
    task_max_retries=3,
    task_default_retry_delay=60,  # 1 minute initial delay
)


class ContextTask(Task):
    """Celery task with async SQLAlchemy session management"""

    def __call__(self, *args, **kwargs):
        return self.run(*args, **kwargs)


async def get_db_session():
    """Create async database session for Celery tasks"""
    engine = create_async_engine(
        DATABASE_URL.replace("+asyncpg", "+aiosqlite"),
        echo=False,
    )
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    return async_session()


@celery_app.task(
    name="process_pdf",
    base=ContextTask,
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
    default_retry_delay=60,
)
async def process_pdf_task(
    self,
    pdf_id: str,
    file_path: str,
    user_id: str,
    title: str = None,
):
    """
    Background task to process PDF asynchronously

    Args:
        pdf_id: Unique PDF identifier
        file_path: Path to PDF file
        user_id: UUID of user who uploaded
        title: Optional document title

    Returns:
        Dict with processing results or raise exception for retry

    Task Flow:
    1. Update status to 'processing'
    2. Extract text from PDF
    3. Extract concepts using LLM
    4. Update database with results
    5. Return results or update error status

    Retry Logic:
    - Max 3 retries
    - Initial delay: 60 seconds
    - Exponential backoff on subsequent retries
    """
    import asyncio

    try:
        # Get database session
        db = await get_db_session()

        # Update status to processing
        stmt = (
            update(PDFUpload)
            .where(PDFUpload.id == pdf_id)
            .values(
                status="processing",
                started_at=datetime.utcnow(),
            )
        )
        await db.execute(stmt)
        await db.commit()

        logger.info(f"Starting PDF processing task: {pdf_id}")

        # Process PDF for concepts
        result = await process_pdf_for_concepts(
            db=db,
            pdf_id=pdf_id,
            file_path=file_path,
            user_id=user_id,
            title=title,
        )

        logger.info(f"PDF processing task completed: {pdf_id}")
        return result

    except Exception as e:
        logger.error(f"PDF processing task failed for {pdf_id}: {str(e)}")

        # Update error status
        try:
            db = await get_db_session()
            stmt = (
                update(PDFUpload)
                .where(PDFUpload.id == pdf_id)
                .values(
                    status="error",
                    error_message=str(e)[:500],
                    completed_at=datetime.utcnow(),
                )
            )
            await db.execute(stmt)
            await db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update error status: {str(db_error)}")

        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))


@celery_app.task(
    name="extract_pdf_text",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 2},
    default_retry_delay=30,
)
async def extract_pdf_text_task(self, file_path: str):
    """
    Background task to extract text from PDF

    Args:
        file_path: Path to PDF file

    Returns:
        Dict with extracted text and metadata

    Used for:
    - Initial text extraction before concept extraction
    - Parallel extraction when processing multiple PDFs
    - Text preview generation for PDF list view
    """
    try:
        logger.info(f"Extracting text from PDF: {file_path}")
        text, metadata = await extract_pdf_text(file_path)

        logger.info(f"Text extraction successful: {len(text)} chars from {file_path}")
        return {
            "file_path": file_path,
            "text_length": len(text),
            "metadata": metadata,
        }

    except Exception as e:
        logger.error(f"Text extraction failed for {file_path}: {str(e)}")
        raise self.retry(exc=e, countdown=30 * (self.request.retries + 1))


@celery_app.task(name="get_task_status")
def get_task_status(task_id: str):
    """
    Get status of a Celery task

    Args:
        task_id: Celery task ID

    Returns:
        Dict with:
        - task_id: The task ID
        - status: Current status (PENDING/STARTED/SUCCESS/FAILURE/RETRY)
        - result: Task result if completed
        - error: Error message if failed
    """
    from celery.result import AsyncResult

    task = AsyncResult(task_id, app=celery_app)

    return {
        "task_id": task_id,
        "status": task.status,
        "result": task.result if task.successful() else None,
        "error": str(task.info) if task.failed() else None,
    }


@celery_app.task(name="health_check")
def health_check():
    """
    Health check task for monitoring Celery worker

    Returns:
        Dict with:
        - status: 'healthy' if task executes successfully
        - timestamp: Current UTC timestamp
        - worker_name: Name of executing worker
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "worker_name": self.request.hostname if hasattr(self, "request") else "unknown",
    }


def enqueue_pdf_processing(
    pdf_id: str,
    file_path: str,
    user_id: str,
    title: str = None,
) -> str:
    """
    Enqueue PDF for asynchronous processing

    Args:
        pdf_id: Unique PDF identifier
        file_path: Path to PDF file
        user_id: UUID of user who uploaded
        title: Optional document title

    Returns:
        str: Celery task ID for status tracking

    Enqueues PDF processing task with:
    - Medium priority
    - 10-minute timeout
    - Error handling via retry logic
    """
    try:
        task = process_pdf_task.apply_async(
            kwargs={
                "pdf_id": pdf_id,
                "file_path": file_path,
                "user_id": user_id,
                "title": title,
            },
            queue="default",
            priority=5,
            time_limit=600,  # 10 minute hard limit
            soft_time_limit=540,  # 9 minute soft limit
        )

        logger.info(f"PDF processing task enqueued: {pdf_id} -> task_id={task.id}")
        return task.id

    except Exception as e:
        logger.error(f"Failed to enqueue PDF processing: {str(e)}")
        raise
