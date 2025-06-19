import os
import logging
import tempfile
import shutil
import asyncio
import threading
from typing import Dict, List, Optional
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Import processing modules
from pipeline import process_uploaded_pdf, check_all_services
from background_processor import get_background_processor
from models import ProcessingJob
from db import (
    get_paper_by_id, get_metadata_by_id, 
    get_embedding_by_id, get_layout_by_id,
    get_page_embeddings_by_id, get_page_embedding_by_page
)
from admin import router as admin_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="RefServer - PDF Intelligence Pipeline",
    description="Unified PDF processing system for academic papers with OCR, embedding, layout analysis, and metadata extraction",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Global cleanup task control
_cleanup_task = None
_cleanup_stop_event = None

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Background job cleanup scheduler
async def cleanup_jobs_periodically():
    """Periodically clean up old processing jobs"""
    global _cleanup_stop_event
    
    logger.info("Starting background job cleanup scheduler")
    
    while not _cleanup_stop_event.is_set():
        try:
            # Clean up jobs older than 7 days every 24 hours
            processor = get_background_processor()
            processor.cleanup_old_jobs(days_old=7)
            
            # Wait 24 hours (86400 seconds) or until stop event
            await asyncio.sleep(86400)  # 24 hours
            
        except Exception as e:
            logger.error(f"Error in background cleanup: {e}")
            # Wait 1 hour before retrying on error
            await asyncio.sleep(3600)

@app.on_event("startup")
async def startup_event():
    """Initialize background tasks on startup"""
    global _cleanup_task, _cleanup_stop_event
    
    logger.info("🚀 RefServer starting up...")
    
    # Initialize cleanup task
    _cleanup_stop_event = asyncio.Event()
    _cleanup_task = asyncio.create_task(cleanup_jobs_periodically())
    
    logger.info("✅ Background job cleanup scheduler started")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up background tasks on shutdown"""
    global _cleanup_task, _cleanup_stop_event
    
    logger.info("🛑 RefServer shutting down...")
    
    # Stop cleanup task
    if _cleanup_stop_event:
        _cleanup_stop_event.set()
    
    if _cleanup_task:
        _cleanup_task.cancel()
        try:
            await _cleanup_task
        except asyncio.CancelledError:
            pass
    
    logger.info("✅ Background tasks stopped")

# Pydantic models for API responses
class ProcessingResult(BaseModel):
    doc_id: str
    filename: str
    success: bool
    processing_time: float
    steps_completed: List[str]
    steps_failed: List[str]
    warnings: List[str]
    data: Dict

class ServiceStatus(BaseModel):
    database: bool
    quality_assessment: bool
    layout_analysis: bool
    metadata_extraction: bool
    timestamp: float

class PaperInfo(BaseModel):
    doc_id: str
    filename: str
    file_path: str
    ocr_text: Optional[str]
    ocr_quality: Optional[str]
    created_at: str
    updated_at: str

class MetadataInfo(BaseModel):
    title: Optional[str]
    authors: List[str]
    journal: Optional[str]
    year: Optional[int]
    doi: Optional[str]
    abstract: Optional[str]
    keywords: List[str]

class EmbeddingInfo(BaseModel):
    dimension: int
    vector: List[float]

class UploadResponse(BaseModel):
    job_id: str
    filename: str
    message: str
    status: str

class JobStatus(BaseModel):
    job_id: str
    filename: str
    status: str
    current_step: Optional[str]
    progress_percentage: int
    steps_completed: List[Dict]
    steps_failed: List[Dict]
    error_message: Optional[str]
    result_summary: Optional[Dict]
    created_at: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    paper_id: Optional[str]

class PageEmbeddingInfo(BaseModel):
    page_number: int
    page_text: str
    dimension: int
    vector: List[float]

class AllPageEmbeddingsInfo(BaseModel):
    document_id: str
    total_pages: int
    pages: List[PageEmbeddingInfo]

class LayoutInfo(BaseModel):
    page_count: int
    total_elements: int
    element_types: Dict
    pages: List[Dict]

# Startup event
@app.on_event("startup")
async def startup_event():
    """Check services on startup"""
    try:
        logger.info("Starting RefServer...")
        
        # Check service status
        status = check_all_services()
        logger.info(f"Service status: {status}")
        
        logger.info("RefServer startup completed")
        
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "RefServer"}

# Service status endpoint
@app.get("/status", response_model=ServiceStatus)
async def get_service_status():
    """Get status of all processing services"""
    try:
        status = check_all_services()
        return ServiceStatus(**status)
    except Exception as e:
        logger.error(f"Error getting service status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get service status: {str(e)}")

# PDF processing endpoint
@app.post("/upload", response_model=UploadResponse)
async def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PDF file to upload and process")
):
    """
    Upload PDF file and start background processing
    Returns job_id for status tracking
    """
    # Validate file
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    if file.size and file.size > 50 * 1024 * 1024:  # 50MB limit
        raise HTTPException(status_code=400, detail="File size too large (max 50MB)")
    
    temp_file_path = None
    
    try:
        logger.info(f"Uploading PDF: {file.filename}")
        
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_file_path = temp_file.name
            content = await file.read()
            temp_file.write(content)
        
        logger.info(f"Uploaded file saved to: {temp_file_path}")
        
        # Create processing job
        processor = get_background_processor()
        job_id = processor.create_upload_job(file.filename, temp_file_path)
        
        # Start background processing
        processor.start_processing(job_id, temp_file_path, background_tasks)
        
        return UploadResponse(
            job_id=job_id,
            filename=file.filename,
            message="File uploaded successfully. Processing started in background.",
            status="processing"
        )
        
    except Exception as e:
        logger.error(f"Error uploading PDF: {e}")
        
        # Cleanup temp file on error
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except:
                pass
        
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


def cleanup_temp_file(file_path: str):
    """Clean up temporary file"""
    try:
        if os.path.exists(file_path):
            os.unlink(file_path)
            logger.info(f"Cleaned up temp file: {file_path}")
    except Exception as e:
        logger.error(f"Failed to cleanup temp file {file_path}: {e}")


@app.get("/job/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """Get processing job status"""
    try:
        processor = get_background_processor()
        status = processor.get_job_status(job_id)
        
        if not status:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return JobStatus(**status)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get job status: {str(e)}")


@app.post("/process", response_model=ProcessingResult, deprecated=True)
async def process_pdf_legacy(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PDF file to process")
):
    """
    Legacy endpoint for backward compatibility
    Processes PDF synchronously (deprecated - use /upload instead)
    """
    # Validate file
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    if file.size and file.size > 50 * 1024 * 1024:  # 50MB limit
        raise HTTPException(status_code=400, detail="File size too large (max 50MB)")
    
    temp_file_path = None
    
    try:
        logger.info(f"Processing PDF upload (legacy): {file.filename}")
        
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_file_path = temp_file.name
            content = await file.read()
            temp_file.write(content)
        
        logger.info(f"Uploaded file saved to: {temp_file_path}")
        
        # Process PDF through pipeline (synchronous)
        result = process_uploaded_pdf(temp_file_path, file.filename)
        
        # Schedule cleanup of temporary file
        background_tasks.add_task(cleanup_temp_file, temp_file_path)
        
        return ProcessingResult(**result)
        
    except Exception as e:
        logger.error(f"Error processing PDF: {e}")
        
        # Cleanup temp file on error
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except:
                pass
        
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

# Paper information endpoint
@app.get("/paper/{doc_id}", response_model=PaperInfo)
async def get_paper_info(doc_id: str):
    """Get basic paper information"""
    try:
        paper = get_paper_by_id(doc_id)
        
        if not paper:
            raise HTTPException(status_code=404, detail="Paper not found")
        
        return PaperInfo(
            doc_id=paper.doc_id,
            filename=paper.filename,
            file_path=paper.file_path,
            ocr_text=paper.ocr_text,
            ocr_quality=paper.ocr_quality,
            created_at=paper.created_at.isoformat() if paper.created_at else "",
            updated_at=paper.updated_at.isoformat() if paper.updated_at else ""
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting paper info: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get paper info: {str(e)}")

# Metadata endpoint
@app.get("/metadata/{doc_id}", response_model=MetadataInfo)
async def get_paper_metadata(doc_id: str):
    """Get paper bibliographic metadata"""
    try:
        metadata = get_metadata_by_id(doc_id)
        
        if not metadata:
            raise HTTPException(status_code=404, detail="Metadata not found")
        
        return MetadataInfo(
            title=metadata.title,
            authors=metadata.get_authors_list(),
            journal=metadata.journal,
            year=metadata.year if metadata.year > 0 else None,
            doi=metadata.doi,
            abstract=metadata.abstract,
            keywords=metadata.get_keywords_list()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting metadata: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get metadata: {str(e)}")

# Embedding endpoint
@app.get("/embedding/{doc_id}", response_model=EmbeddingInfo)
async def get_paper_embedding(doc_id: str):
    """Get paper embedding vector"""
    try:
        embedding = get_embedding_by_id(doc_id)
        
        if embedding is None:
            raise HTTPException(status_code=404, detail="Embedding not found")
        
        return EmbeddingInfo(
            dimension=len(embedding),
            vector=embedding.tolist()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting embedding: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get embedding: {str(e)}")

# Page embeddings endpoints
@app.get("/embedding/{doc_id}/pages", response_model=AllPageEmbeddingsInfo)
async def get_all_page_embeddings(doc_id: str):
    """Get all page embeddings for a document"""
    try:
        page_embeddings = get_page_embeddings_by_id(doc_id)
        
        if page_embeddings is None:
            raise HTTPException(status_code=404, detail="Page embeddings not found")
        
        pages = []
        for page_number, page_text, embedding_vector in page_embeddings:
            pages.append(PageEmbeddingInfo(
                page_number=page_number,
                page_text=page_text,
                dimension=len(embedding_vector),
                vector=embedding_vector.tolist()
            ))
        
        return AllPageEmbeddingsInfo(
            document_id=doc_id,
            total_pages=len(pages),
            pages=pages
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting page embeddings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get page embeddings: {str(e)}")

@app.get("/embedding/{doc_id}/page/{page_number}", response_model=PageEmbeddingInfo)
async def get_single_page_embedding(doc_id: str, page_number: int):
    """Get embedding for a specific page"""
    try:
        page_data = get_page_embedding_by_page(doc_id, page_number)
        
        if page_data is None:
            raise HTTPException(status_code=404, detail=f"Page {page_number} embedding not found")
        
        page_text, embedding_vector = page_data
        
        return PageEmbeddingInfo(
            page_number=page_number,
            page_text=page_text,
            dimension=len(embedding_vector),
            vector=embedding_vector.tolist()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting page embedding: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get page embedding: {str(e)}")

# Layout analysis endpoint
@app.get("/layout/{doc_id}", response_model=LayoutInfo)
async def get_paper_layout(doc_id: str):
    """Get paper layout analysis results"""
    try:
        layout_data = get_layout_by_id(doc_id)
        
        if not layout_data:
            raise HTTPException(status_code=404, detail="Layout analysis not found")
        
        return LayoutInfo(
            page_count=layout_data.get('page_count', 0),
            total_elements=layout_data.get('total_elements', 0),
            element_types=layout_data.get('element_types', {}),
            pages=layout_data.get('pages', [])
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting layout: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get layout: {str(e)}")

# Preview image endpoint
@app.get("/preview/{doc_id}")
async def get_paper_preview(doc_id: str):
    """Get first page preview image"""
    try:
        # Construct image path
        image_path = Path("/data/images") / f"{doc_id}_page1.png"
        
        if not image_path.exists():
            raise HTTPException(status_code=404, detail="Preview image not found")
        
        return FileResponse(
            str(image_path),
            media_type="image/png",
            filename=f"{doc_id}_preview.png"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting preview: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get preview: {str(e)}")

# PDF download endpoint
@app.get("/download/{doc_id}")
async def download_paper_pdf(doc_id: str):
    """Download processed PDF file"""
    try:
        paper = get_paper_by_id(doc_id)
        
        if not paper:
            raise HTTPException(status_code=404, detail="Paper not found")
        
        pdf_path = Path(paper.file_path)
        
        if not pdf_path.exists():
            raise HTTPException(status_code=404, detail="PDF file not found")
        
        return FileResponse(
            str(pdf_path),
            media_type="application/pdf",
            filename=paper.filename
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading PDF: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to download PDF: {str(e)}")

# Text content endpoint
@app.get("/text/{doc_id}")
async def get_paper_text(doc_id: str):
    """Get extracted text content"""
    try:
        paper = get_paper_by_id(doc_id)
        
        if not paper:
            raise HTTPException(status_code=404, detail="Paper not found")
        
        return {
            "doc_id": doc_id,
            "text": paper.ocr_text or "",
            "text_length": len(paper.ocr_text) if paper.ocr_text else 0,
            "ocr_quality": paper.ocr_quality
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting text: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get text: {str(e)}")

# Search endpoint (basic implementation)
@app.get("/search")
async def search_papers(
    q: Optional[str] = None,
    title: Optional[str] = None,
    author: Optional[str] = None,
    year: Optional[int] = None,
    limit: int = 20,
    offset: int = 0
):
    """Search papers by various criteria"""
    try:
        # This is a basic implementation - can be enhanced with vector similarity search
        from models import Paper, Metadata
        
        query = Paper.select()
        
        # Add filters based on provided parameters
        if title:
            query = query.join(Metadata).where(Metadata.title.contains(title))
        
        if author:
            query = query.join(Metadata).where(Metadata.authors.contains(author))
        
        if year:
            query = query.join(Metadata).where(Metadata.year == year)
        
        # Apply pagination
        papers = query.limit(limit).offset(offset)
        
        results = []
        for paper in papers:
            try:
                metadata = paper.metadata.get() if hasattr(paper, 'metadata') else None
                results.append({
                    "doc_id": paper.doc_id,
                    "filename": paper.filename,
                    "title": metadata.title if metadata else None,
                    "authors": metadata.get_authors_list() if metadata else [],
                    "year": metadata.year if metadata and metadata.year > 0 else None,
                    "created_at": paper.created_at.isoformat() if paper.created_at else None
                })
            except:
                # Skip papers without metadata
                continue
        
        return {
            "query": q or "",
            "total": len(results),
            "limit": limit,
            "offset": offset,
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error searching papers: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

# Statistics endpoint
@app.get("/stats")
async def get_statistics():
    """Get system statistics"""
    try:
        from models import Paper, Metadata, Embedding, LayoutAnalysis
        
        # Count records
        total_papers = Paper.select().count()
        papers_with_metadata = Paper.select().join(Metadata).count()
        papers_with_embeddings = Paper.select().join(Embedding).count()
        papers_with_layout = Paper.select().join(LayoutAnalysis).count()
        
        # Calculate processing rates
        processing_rates = {
            "metadata_rate": (papers_with_metadata / total_papers * 100) if total_papers > 0 else 0,
            "embedding_rate": (papers_with_embeddings / total_papers * 100) if total_papers > 0 else 0,
            "layout_rate": (papers_with_layout / total_papers * 100) if total_papers > 0 else 0
        }
        
        return {
            "total_papers": total_papers,
            "papers_with_metadata": papers_with_metadata,
            "papers_with_embeddings": papers_with_embeddings,
            "papers_with_layout": papers_with_layout,
            "processing_rates": processing_rates,
            "service_status": check_all_services()
        }
        
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")

# Job cleanup endpoint
@app.post("/admin/cleanup-jobs")
async def cleanup_old_jobs_manual(days_old: int = 7):
    """Manually trigger cleanup of old processing jobs"""
    try:
        processor = get_background_processor()
        
        # Get count before cleanup
        from models import ProcessingJob
        import datetime
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days_old)
        
        old_jobs_count = (ProcessingJob
                         .select()
                         .where(
                             (ProcessingJob.status.in_(['completed', 'failed'])) &
                             (ProcessingJob.created_at < cutoff_date)
                         )
                         .count())
        
        # Perform cleanup
        processor.cleanup_old_jobs(days_old)
        
        return {
            "success": True,
            "days_old": days_old,
            "jobs_cleaned": old_jobs_count,
            "message": f"Cleaned up {old_jobs_count} jobs older than {days_old} days"
        }
        
    except Exception as e:
        logger.error(f"Error in manual job cleanup: {e}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")

# Utility function for background tasks
def cleanup_temp_file(file_path: str):
    """Clean up temporary file"""
    try:
        if os.path.exists(file_path):
            os.unlink(file_path)
            logger.info(f"Cleaned up temporary file: {file_path}")
    except Exception as e:
        logger.warning(f"Failed to cleanup temp file {file_path}: {e}")

# Error handler for unhandled exceptions
@app.exception_handler(500)
async def internal_server_error_handler(request, exc):
    logger.error(f"Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error occurred"}
    )

# Custom 404 handler
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"detail": "Resource not found"}
    )

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include admin router
app.include_router(admin_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)