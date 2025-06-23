import os
import logging
import tempfile
import shutil
import asyncio
import threading
from typing import Dict, List, Optional
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, BackgroundTasks, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Import processing modules
from pipeline import process_uploaded_pdf, check_all_services
from background_processor import get_background_processor
from version import get_version
from models import ProcessingJob
from db import (
    get_paper_by_id, get_metadata_by_id, 
    get_embedding_by_id, get_layout_by_id,
    get_page_embeddings_by_id, get_page_embedding_by_page
)
from admin import router as admin_router
from performance_monitor import get_system_performance_stats, get_performance_monitor
from job_queue import get_queue_status, cancel_queued_job, JobPriority
from file_security import validate_uploaded_file, get_security_status, FileSecurityError
from vector_db import initialize_vector_db, get_vector_db
from embedding import find_similar_papers_vectordb, get_embedding_model
from duplicate_detector import get_duplicate_detector
from scheduler import get_background_scheduler, start_background_scheduler

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
    version=get_version(),
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
    
    # Initialize backup scheduler
    try:
        from backup import get_backup_manager
        backup_manager = get_backup_manager()
        backup_manager.start_scheduler()
        logger.info("✅ Backup scheduler started")
    except Exception as e:
        logger.error(f"Failed to start backup scheduler: {e}")

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
    
    # Stop backup scheduler
    try:
        from backup import get_backup_manager
        backup_manager = get_backup_manager()
        backup_manager.stop_scheduler()
        logger.info("✅ Backup scheduler stopped")
    except Exception as e:
        logger.error(f"Failed to stop backup scheduler: {e}")
    
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
    version: str
    deployment_mode: str

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
        logger.info("🚀 Starting RefServer v0.1.10...")
        
        # Initialize ChromaDB
        try:
            chroma_success = initialize_vector_db()
            if chroma_success:
                logger.info("✅ ChromaDB initialized successfully")
            else:
                logger.warning("⚠️ ChromaDB initialization failed - vector search may be limited")
        except Exception as chroma_error:
            logger.error(f"❌ ChromaDB initialization error: {chroma_error}")
        
        # Check service status
        status = check_all_services()
        logger.info(f"Service status: {status}")
        
        # Start background scheduler
        try:
            start_background_scheduler()
            logger.info("✅ Background scheduler started")
        except Exception as scheduler_error:
            logger.error(f"❌ Background scheduler startup failed: {scheduler_error}")
        
        logger.info("✅ RefServer v0.1.10 startup completed")
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
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
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PDF file to upload and process")
):
    """
    Upload PDF file and start background processing with security validation
    Returns job_id for status tracking
    """
    temp_file_path = None
    
    try:
        logger.info(f"Uploading PDF: {file.filename}")
        
        # Get client IP for rate limiting
        client_ip = request.client.host if request.client else None
        
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_file_path = temp_file.name
            content = await file.read()
            temp_file.write(content)
        
        logger.info(f"Uploaded file saved to: {temp_file_path}")
        
        # Comprehensive security validation
        try:
            validation_result = validate_uploaded_file(temp_file_path, file.filename, client_ip)
            logger.info(f"File security validation passed for {file.filename}")
            logger.debug(f"Validation details: {validation_result.get('checks_performed', [])}")
        except FileSecurityError as e:
            # Clean up temp file
            if temp_file_path and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
            logger.warning(f"Security validation failed for {file.filename}: {e}")
            raise HTTPException(status_code=400, detail=f"Security validation failed: {str(e)}")
        
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
        
    except HTTPException:
        raise
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
    request: Request,
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
        
        # Get client IP for rate limiting
        client_ip = request.client.host if request.client else None
        
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_file_path = temp_file.name
            content = await file.read()
            temp_file.write(content)
        
        logger.info(f"Uploaded file saved to: {temp_file_path}")
        
        # Comprehensive security validation
        try:
            validation_result = validate_uploaded_file(temp_file_path, file.filename, client_ip)
            logger.info(f"File security validation passed for legacy endpoint: {file.filename}")
        except FileSecurityError as e:
            # Clean up temp file
            if temp_file_path and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
            logger.warning(f"Security validation failed for legacy endpoint {file.filename}: {e}")
            raise HTTPException(status_code=400, detail=f"Security validation failed: {str(e)}")
        
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
        image_path = Path("/refdata/images") / f"{doc_id}_page1.png"
        
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

# Performance monitoring endpoints
@app.get("/performance/stats")
async def get_performance_statistics():
    """Get comprehensive performance statistics and metrics"""
    try:
        stats = get_system_performance_stats()
        return stats
        
    except Exception as e:
        logger.error(f"Error getting performance statistics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get performance statistics: {str(e)}")

@app.get("/performance/export")
async def export_performance_metrics(format: str = "json"):
    """Export performance metrics in specified format"""
    try:
        if format not in ["json", "csv"]:
            raise HTTPException(status_code=400, detail="Format must be 'json' or 'csv'")
        
        monitor = get_performance_monitor()
        exported_data = monitor.export_metrics(format)
        
        if format == "json":
            import json
            return JSONResponse(content=json.loads(exported_data))
        else:  # CSV
            from fastapi.responses import Response
            return Response(
                content=exported_data,
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=performance_metrics.csv"}
            )
        
    except Exception as e:
        logger.error(f"Error exporting performance metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to export metrics: {str(e)}")

@app.get("/performance/system")
async def get_system_metrics():
    """Get current system resource metrics"""
    try:
        import psutil
        import time
        
        # Current system metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Load average (Unix only)
        load_avg = None
        if hasattr(os, 'getloadavg'):
            load_avg = list(os.getloadavg())
        
        # Active processes
        active_jobs = len(get_background_processor()._active_jobs)
        
        return {
            "timestamp": time.time(),
            "cpu": {
                "percent": cpu_percent,
                "load_average": load_avg
            },
            "memory": {
                "total_mb": memory.total / 1024 / 1024,
                "used_mb": memory.used / 1024 / 1024,
                "available_mb": memory.available / 1024 / 1024,
                "percent": memory.percent
            },
            "disk": {
                "total_mb": disk.total / 1024 / 1024,
                "used_mb": disk.used / 1024 / 1024,
                "free_mb": disk.free / 1024 / 1024,
                "percent": disk.percent
            },
            "jobs": {
                "active_count": active_jobs
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting system metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get system metrics: {str(e)}")

@app.get("/performance/jobs")
async def get_job_performance_metrics():
    """Get performance metrics for recent jobs"""
    try:
        monitor = get_performance_monitor()
        
        # Get recent completed jobs (last 50)
        recent_jobs = list(monitor.completed_jobs)[-50:] if monitor.completed_jobs else []
        
        job_metrics = []
        for job in recent_jobs:
            job_metrics.append({
                "job_id": job.job_id,
                "filename": job.filename,
                "duration": job.duration,
                "success": job.success,
                "file_size_mb": job.file_size_mb,
                "page_count": job.page_count,
                "steps_completed": job.steps_completed,
                "steps_failed": job.steps_failed,
                "start_time": job.start_time,
                "error_message": job.error_message
            })
        
        # Get active jobs
        active_jobs = []
        for job_id, info in monitor.active_jobs.items():
            active_jobs.append({
                "job_id": job_id,
                "filename": info['filename'],
                "current_step": info['current_step'],
                "runtime_seconds": time.time() - info['start_time']
            })
        
        return {
            "recent_jobs": job_metrics,
            "active_jobs": active_jobs,
            "total_completed": len(monitor.completed_jobs),
            "total_active": len(monitor.active_jobs)
        }
        
    except Exception as e:
        logger.error(f"Error getting job performance metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get job metrics: {str(e)}")

# Job queue management endpoints
@app.get("/queue/status")
async def get_job_queue_status():
    """Get current job queue status and statistics"""
    try:
        status = get_queue_status()
        return status
        
    except Exception as e:
        logger.error(f"Error getting queue status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get queue status: {str(e)}")

@app.post("/queue/cancel/{job_id}")
async def cancel_job_in_queue(job_id: str):
    """Cancel a job in the queue"""
    try:
        success = cancel_queued_job(job_id)
        
        if success:
            return {"message": f"Job {job_id} cancelled successfully"}
        else:
            raise HTTPException(status_code=400, detail=f"Failed to cancel job {job_id} (may not be in queue)")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel job: {str(e)}")

@app.post("/upload-priority")
async def upload_pdf_with_priority(
    request: Request,
    file: UploadFile = File(...),
    priority: str = "normal"
):
    """Upload PDF with priority level for queue processing with security validation"""
    try:
        # Validate priority
        priority_map = {
            "low": JobPriority.LOW,
            "normal": JobPriority.NORMAL, 
            "high": JobPriority.HIGH,
            "urgent": JobPriority.URGENT
        }
        
        if priority.lower() not in priority_map:
            raise HTTPException(status_code=400, detail="Priority must be one of: low, normal, high, urgent")
        
        job_priority = priority_map[priority.lower()]
        
        # Get client IP for rate limiting
        client_ip = request.client.host if request.client else None
        
        # Create temporary file
        temp_file_path = None
        try:
            # Create temp file
            temp_fd, temp_file_path = tempfile.mkstemp(suffix='.pdf', prefix='refserver_')
            
            # Write uploaded content
            content = await file.read()
            with os.fdopen(temp_fd, 'wb') as temp_file:
                temp_file.write(content)
            
            # Comprehensive security validation
            try:
                validation_result = validate_uploaded_file(temp_file_path, file.filename, client_ip)
                logger.info(f"File security validation passed for priority upload: {file.filename}")
            except FileSecurityError as e:
                # Clean up temp file
                if temp_file_path and os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                logger.warning(f"Security validation failed for priority upload {file.filename}: {e}")
                raise HTTPException(status_code=400, detail=f"Security validation failed: {str(e)}")
            
            # Get background processor
            processor = get_background_processor()
            
            # Create job record
            job_id = processor.create_upload_job(file.filename, temp_file_path)
            
            # Submit to queue with priority
            success = processor.submit_job_to_queue(job_id, file.filename, temp_file_path, job_priority)
            
            if success:
                return {
                    "job_id": job_id,
                    "message": f"PDF uploaded and queued with {priority} priority",
                    "priority": priority.upper(),
                    "status": "queued"
                }
            else:
                # Clean up temp file if job submission failed
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                raise HTTPException(status_code=503, detail="Queue is full, please try again later")
            
        except HTTPException:
            # Clean up temp file on HTTP error
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except:
                    pass
            raise
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in priority upload: {e}")
        # Clean up temp file on error
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except:
                pass
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

# Security status endpoint
@app.get("/security/status")
async def get_security_system_status():
    """Get current file security system status and configuration"""
    try:
        status = get_security_status()
        return status
        
    except Exception as e:
        logger.error(f"Error getting security status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get security status: {str(e)}")

# Vector search endpoints
@app.get("/similar/{doc_id}")
async def get_similar_papers(doc_id: str, limit: int = 10):
    """
    Find papers similar to the given document using ChromaDB vector search
    
    Args:
        doc_id: str, document ID to find similar papers for
        limit: int, maximum number of similar papers to return
    
    Returns:
        List[dict]: similar papers with metadata and similarity scores
    """
    try:
        # Get embedding for the given document
        embedding = get_embedding_by_id(doc_id)
        if embedding is None:
            raise HTTPException(status_code=404, detail=f"No embedding found for document {doc_id}")
        
        # Find similar papers using ChromaDB
        similar_papers = find_similar_papers_vectordb(embedding, n_results=limit)
        
        # Filter out the query document itself
        similar_papers = [paper for paper in similar_papers if paper['doc_id'] != doc_id]
        
        return {
            "query_doc_id": doc_id,
            "similar_papers": similar_papers[:limit],
            "total_found": len(similar_papers)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finding similar papers for {doc_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to find similar papers: {str(e)}")

@app.post("/search/vector")
async def vector_search(
    query: str,
    limit: int = 10,
    filters: Optional[dict] = None
):
    """
    Search papers using text query converted to embedding vector
    
    Args:
        query: str, text query to search for
        limit: int, maximum number of results to return
        filters: dict, optional metadata filters
    
    Returns:
        List[dict]: similar papers with metadata and similarity scores
    """
    try:
        if not query or not query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        # Generate embedding for the query text
        embedding_model = get_embedding_model()
        query_embedding = embedding_model.encode_text(query.strip())
        
        # Search using ChromaDB
        similar_papers = find_similar_papers_vectordb(query_embedding, n_results=limit, filters=filters)
        
        return {
            "query": query,
            "similar_papers": similar_papers,
            "total_found": len(similar_papers),
            "search_method": "vector_similarity"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in vector search for query '{query}': {e}")
        raise HTTPException(status_code=500, detail=f"Vector search failed: {str(e)}")

# ChromaDB statistics endpoint
@app.get("/vector/stats")
async def get_vector_db_stats():
    """
    Get ChromaDB collection statistics and health status
    
    Returns:
        dict: ChromaDB statistics and status
    """
    try:
        vector_db = get_vector_db()
        stats = vector_db.get_collection_stats()
        health = vector_db.health_check()
        
        return {
            "chromadb_stats": stats,
            "health_status": "healthy" if health else "unhealthy",
            "version": "v0.1.10"
        }
        
    except Exception as e:
        logger.error(f"Error getting vector DB stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get vector DB stats: {str(e)}")

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

# Duplicate Prevention API Endpoints

@app.get("/duplicate-prevention/stats")
async def get_duplicate_prevention_stats():
    """Get duplicate prevention system statistics"""
    try:
        detector = get_duplicate_detector()
        stats = detector.get_duplicate_stats()
        
        return {
            "success": True,
            "statistics": stats,
            "total_hashes": (
                stats['file_hashes_count'] + 
                stats['content_hashes_count'] + 
                stats['sample_embedding_hashes_count']
            )
        }
        
    except Exception as e:
        logger.error(f"Error getting duplicate prevention stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")

@app.post("/duplicate-prevention/check")
async def check_duplicate_file(file: UploadFile = File(...)):
    """Check if uploaded file is a duplicate without processing it"""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    try:
        # Validate file
        validate_uploaded_file(file)
        
        # Save to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        try:
            # Check for duplicates
            detector = get_duplicate_detector()
            duplicate_doc_id, detection_layer, detection_time = detector.check_all_layers(
                temp_file_path, file.filename
            )
            
            result = {
                "success": True,
                "filename": file.filename,
                "is_duplicate": duplicate_doc_id is not None,
                "detection_time": round(detection_time, 3),
                "detection_layer": detection_layer
            }
            
            if duplicate_doc_id:
                result["existing_doc_id"] = duplicate_doc_id
                result["message"] = f"Duplicate detected via {detection_layer}"
            else:
                result["message"] = "No duplicates found"
            
            return result
            
        finally:
            # Clean up temp file
            cleanup_temp_file(temp_file_path)
            
    except FileSecurityError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in duplicate check: {e}")
        raise HTTPException(status_code=500, detail=f"Duplicate check failed: {str(e)}")

@app.get("/duplicate-prevention/paper/{doc_id}")
async def get_paper_duplicate_hashes(doc_id: str):
    """Get all duplicate prevention hashes for a specific paper"""
    try:
        from models import Paper, FileHash, ContentHash, SampleEmbeddingHash
        
        # Check if paper exists
        paper = Paper.get_or_none(Paper.doc_id == doc_id)
        if not paper:
            raise HTTPException(status_code=404, detail="Paper not found")
        
        # Get all hash records
        file_hash = FileHash.get_or_none(FileHash.paper == paper)
        content_hash = ContentHash.get_or_none(ContentHash.paper == paper)
        sample_hash = SampleEmbeddingHash.get_or_none(SampleEmbeddingHash.paper == paper)
        
        result = {
            "success": True,
            "doc_id": doc_id,
            "hashes": {
                "file_hash": {
                    "exists": file_hash is not None,
                    "md5": file_hash.file_md5 if file_hash else None,
                    "file_size": file_hash.file_size if file_hash else None,
                    "created_at": file_hash.created_at.isoformat() if file_hash else None
                },
                "content_hash": {
                    "exists": content_hash is not None,
                    "hash": content_hash.content_hash if content_hash else None,
                    "page_count": content_hash.page_count if content_hash else None,
                    "pdf_title": content_hash.pdf_title if content_hash else None,
                    "created_at": content_hash.created_at.isoformat() if content_hash else None
                },
                "sample_embedding_hash": {
                    "exists": sample_hash is not None,
                    "hash": sample_hash.embedding_hash if sample_hash else None,
                    "strategy": sample_hash.sample_strategy if sample_hash else None,
                    "vector_dim": sample_hash.vector_dim if sample_hash else None,
                    "created_at": sample_hash.created_at.isoformat() if sample_hash else None
                }
            }
        }
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting paper hashes: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get hashes: {str(e)}")

@app.get("/duplicate-prevention/performance")
async def get_duplicate_prevention_performance(days: int = 30):
    """Get detailed performance statistics for duplicate prevention system"""
    try:
        if days < 1 or days > 365:
            raise HTTPException(status_code=400, detail="Days must be between 1 and 365")
        
        detector = get_duplicate_detector()
        performance_stats = detector.get_performance_stats(days)
        
        return {
            "success": True,
            "performance_statistics": performance_stats,
            "analysis_note": f"Performance data analyzed for the last {days} days"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting duplicate prevention performance: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get performance stats: {str(e)}")

@app.get("/duplicate-prevention/recent-detections")
async def get_recent_duplicate_detections(limit: int = 50):
    """Get recent duplicate detection attempts with details"""
    try:
        if limit < 1 or limit > 1000:
            raise HTTPException(status_code=400, detail="Limit must be between 1 and 1000")
        
        detector = get_duplicate_detector()
        recent_detections = detector.get_recent_detections(limit)
        
        return {
            "success": True,
            "recent_detections": recent_detections,
            "total_returned": len(recent_detections)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting recent detections: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get recent detections: {str(e)}")

@app.post("/duplicate-prevention/cleanup-logs")
async def cleanup_duplicate_detection_logs(days_to_keep: int = 90):
    """Clean up old duplicate detection logs to manage database size"""
    try:
        if days_to_keep < 7 or days_to_keep > 730:
            raise HTTPException(status_code=400, detail="Days to keep must be between 7 and 730")
        
        detector = get_duplicate_detector()
        deleted_count = detector.cleanup_old_detection_logs(days_to_keep)
        
        return {
            "success": True,
            "deleted_logs": deleted_count,
            "message": f"Cleaned up logs older than {days_to_keep} days"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cleaning up detection logs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cleanup logs: {str(e)}")

@app.post("/duplicate-prevention/cleanup-orphaned")
async def cleanup_orphaned_hashes():
    """Clean up orphaned hash records that reference deleted papers"""
    try:
        detector = get_duplicate_detector()
        cleanup_stats = detector.cleanup_orphaned_hashes()
        
        total_cleaned = sum(cleanup_stats.values())
        
        return {
            "success": True,
            "cleanup_type": "orphaned_hashes",
            "total_cleaned": total_cleaned,
            "details": cleanup_stats,
            "message": f"Cleaned up {total_cleaned} orphaned hash records"
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up orphaned hashes: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cleanup orphaned hashes: {str(e)}")

@app.post("/duplicate-prevention/cleanup-duplicates")
async def cleanup_duplicate_hashes():
    """Clean up duplicate hash records for the same paper"""
    try:
        detector = get_duplicate_detector()
        cleanup_stats = detector.cleanup_duplicate_hashes()
        
        total_cleaned = sum(cleanup_stats.values())
        
        return {
            "success": True,
            "cleanup_type": "duplicate_hashes",
            "total_cleaned": total_cleaned,
            "details": cleanup_stats,
            "message": f"Cleaned up {total_cleaned} duplicate hash records"
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up duplicate hashes: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cleanup duplicate hashes: {str(e)}")

@app.post("/duplicate-prevention/cleanup-unused")
async def cleanup_unused_hashes(months_threshold: int = 6):
    """Clean up unused hash records older than specified months"""
    try:
        if months_threshold < 1 or months_threshold > 24:
            raise HTTPException(status_code=400, detail="Months threshold must be between 1 and 24")
        
        detector = get_duplicate_detector()
        cleanup_stats = detector.cleanup_unused_hashes(months_threshold)
        
        total_cleaned = sum(cleanup_stats.values())
        
        return {
            "success": True,
            "cleanup_type": "unused_hashes",
            "months_threshold": months_threshold,
            "total_cleaned": total_cleaned,
            "details": cleanup_stats,
            "message": f"Cleaned up {total_cleaned} unused hash records older than {months_threshold} months"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cleaning up unused hashes: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cleanup unused hashes: {str(e)}")

@app.post("/duplicate-prevention/cleanup-all")
async def cleanup_all_hashes(months_threshold: int = 6, detection_logs_days: int = 90):
    """Perform comprehensive cleanup of all hash data"""
    try:
        if months_threshold < 1 or months_threshold > 24:
            raise HTTPException(status_code=400, detail="Months threshold must be between 1 and 24")
        
        if detection_logs_days < 7 or detection_logs_days > 730:
            raise HTTPException(status_code=400, detail="Detection logs days must be between 7 and 730")
        
        detector = get_duplicate_detector()
        cleanup_summary = detector.cleanup_all_hashes(months_threshold, detection_logs_days)
        
        if cleanup_summary.get('success'):
            return {
                "success": True,
                "cleanup_type": "comprehensive",
                "parameters": {
                    "months_threshold": months_threshold,
                    "detection_logs_days": detection_logs_days
                },
                "summary": cleanup_summary,
                "message": f"Comprehensive cleanup completed: {cleanup_summary['total_records_cleaned']} records cleaned"
            }
        else:
            raise HTTPException(status_code=500, detail=f"Cleanup failed: {cleanup_summary.get('error', 'Unknown error')}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in comprehensive cleanup: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to perform comprehensive cleanup: {str(e)}")

# Background Scheduler API Endpoints

@app.get("/scheduler/status")
async def get_scheduler_status():
    """Get background scheduler status and information"""
    try:
        scheduler = get_background_scheduler()
        status = scheduler.get_status()
        
        return {
            "success": True,
            "scheduler_status": status
        }
        
    except Exception as e:
        logger.error(f"Error getting scheduler status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get scheduler status: {str(e)}")

@app.post("/scheduler/force-cleanup")
async def force_scheduler_cleanup(cleanup_type: str = "comprehensive"):
    """Force immediate execution of scheduled cleanup"""
    try:
        if cleanup_type not in ["daily", "weekly", "comprehensive", "monthly"]:
            raise HTTPException(status_code=400, detail="Cleanup type must be one of: daily, weekly, comprehensive, monthly")
        
        scheduler = get_background_scheduler()
        result = scheduler.force_cleanup(cleanup_type)
        
        if result.get('success'):
            return {
                "success": True,
                "cleanup_type": cleanup_type,
                "result": result,
                "message": f"Forced {cleanup_type} cleanup completed successfully"
            }
        else:
            raise HTTPException(status_code=500, detail=f"Forced cleanup failed: {result.get('error', 'Unknown error')}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in forced cleanup: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to execute forced cleanup: {str(e)}")

@app.post("/scheduler/restart")
async def restart_scheduler():
    """Restart the background scheduler"""
    try:
        scheduler = get_background_scheduler()
        
        # Stop and restart scheduler
        scheduler.stop()
        scheduler.start()
        
        return {
            "success": True,
            "message": "Background scheduler restarted successfully"
        }
        
    except Exception as e:
        logger.error(f"Error restarting scheduler: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to restart scheduler: {str(e)}")

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