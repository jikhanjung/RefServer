# RefServer Admin Interface
# Jinja2-based administration panel for managing PDF papers

from fastapi import APIRouter, Request, Form, HTTPException, Depends, status, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import os
import logging

from models import Paper, Metadata, Embedding, LayoutAnalysis, AdminUser, PageEmbedding
from auth import AuthManager
from db import get_paper_by_id, get_page_embeddings_by_id, db
from vector_db import get_vector_db
from duplicate_detector import get_duplicate_detector
from service_circuit_breaker import get_circuit_breaker_manager
from version import get_version
from peewee import JOIN
import json

logger = logging.getLogger(__name__)

# Initialize router and templates
router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="templates")
security = HTTPBearer(auto_error=False)

# JWT configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Optional[AdminUser]:
    """Verify JWT token and return user"""
    if not credentials:
        return None
    
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        
        user = AdminUser.get_or_none(AdminUser.username == username)
        return user
    except JWTError:
        return None


def get_current_user(request: Request) -> Optional[AdminUser]:
    """Get current user from session or token"""
    # Check for token in Authorization header
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get("sub")
            if username:
                return AdminUser.get_or_none(AdminUser.username == username)
        except JWTError:
            pass
    
    # Check session cookie
    token = request.cookies.get("access_token")
    if token:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get("sub")
            if username:
                return AdminUser.get_or_none(AdminUser.username == username)
        except JWTError:
            pass
    
    return None


def require_auth(request: Request) -> AdminUser:
    """Require authentication for admin routes"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_stats() -> Dict[str, Any]:
    """Get dashboard statistics"""
    try:
        # Use simpler counting approach to avoid SQL issues
        total_papers = Paper.select().count()
        logger.info(f"get_stats: Total papers = {total_papers}")
        
        # Count papers with each type of data
        papers_with_metadata = 0
        papers_with_embeddings = 0 
        papers_with_layout = 0
        papers_with_page_embeddings = 0
        
        for paper in Paper.select():
            if Metadata.select().where(Metadata.paper == paper).exists():
                papers_with_metadata += 1
            if Embedding.select().where(Embedding.paper == paper).exists():
                papers_with_embeddings += 1
            if LayoutAnalysis.select().where(LayoutAnalysis.paper == paper).exists():
                papers_with_layout += 1
            if PageEmbedding.select().where(PageEmbedding.paper == paper).exists():
                papers_with_page_embeddings += 1
        
        # Get total page embeddings count
        total_page_embeddings = PageEmbedding.select().count()
        
        # Calculate processing rates
        metadata_rate = (papers_with_metadata / total_papers * 100) if total_papers > 0 else 0
        embedding_rate = (papers_with_embeddings / total_papers * 100) if total_papers > 0 else 0
        layout_rate = (papers_with_layout / total_papers * 100) if total_papers > 0 else 0
        page_embedding_rate = (papers_with_page_embeddings / total_papers * 100) if total_papers > 0 else 0
        
        # Check service status (simplified)
        service_status = {
            "database": True,  # If we're here, DB is working
            "ollama": True,    # Would need to check actual service
            "huridocs": True,  # Would need to check actual service
            "embedding_model": True  # Would need to check model loading
        }
        
        return {
            "total_papers": total_papers,
            "papers_with_metadata": papers_with_metadata,
            "papers_with_embeddings": papers_with_embeddings,
            "papers_with_layout": papers_with_layout,
            "papers_with_page_embeddings": papers_with_page_embeddings,
            "total_page_embeddings": total_page_embeddings,
            "processing_rates": {
                "metadata_rate": metadata_rate,
                "embedding_rate": embedding_rate,
                "layout_rate": layout_rate,
                "page_embedding_rate": page_embedding_rate
            },
            "service_status": service_status
        }
    except Exception as e:
        print(f"Error getting stats: {e}")
        return {
            "total_papers": 0,
            "papers_with_metadata": 0,
            "papers_with_embeddings": 0,
            "papers_with_layout": 0,
            "papers_with_page_embeddings": 0,
            "total_page_embeddings": 0,
            "processing_rates": {
                "metadata_rate": 0,
                "embedding_rate": 0,
                "layout_rate": 0,
                "page_embedding_rate": 0
            },
            "service_status": {
                "database": False,
                "ollama": False,
                "huridocs": False,
                "embedding_model": False
            }
        }


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Admin login page"""
    # Check if user is already logged in
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/admin/dashboard", status_code=302)
    
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    """Process admin login"""
    try:
        user = AuthManager.authenticate_user(username, password)
        if not user:
            return templates.TemplateResponse(
                "login.html", 
                {"request": request, "error": "Invalid username or password"}
            )
        
        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username}, expires_delta=access_token_expires
        )
        
        # Redirect to dashboard with cookie
        response = RedirectResponse(url="/admin/dashboard", status_code=302)
        response.set_cookie(
            key="access_token", 
            value=access_token, 
            httponly=True,
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        return response
        
    except Exception as e:
        return templates.TemplateResponse(
            "login.html", 
            {"request": request, "error": "Login failed. Please try again."}
        )


@router.get("/logout")
async def logout():
    """Admin logout"""
    response = RedirectResponse(url="/admin/login", status_code=302)
    response.delete_cookie(key="access_token")
    return response


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Admin dashboard"""
    user = require_auth(request)
    stats = get_stats()
    
    return templates.TemplateResponse(
        "dashboard.html", 
        {
            "request": request, 
            "user": user, 
            "stats": stats
        }
    )


@router.get("/papers", response_class=HTMLResponse)
async def papers_list(request: Request, search: Optional[str] = None):
    """Papers management page"""
    user = require_auth(request)
    
    try:
        # Get papers with optional search
        if search:
            papers = (Paper
                     .select()
                     .where(Paper.filename.contains(search))
                     .order_by(Paper.created_at.desc()))
        else:
            papers = Paper.select().order_by(Paper.created_at.desc())
        
        # Debug database connection
        logger.info(f"Database closed: {db.is_closed()}")
        if db.is_closed():
            db.connect()
            logger.info("Reconnected to database")
            
        # Count papers directly
        direct_count = Paper.select().count()
        query_count = papers.count()
        
        logger.info(f"Papers page: Direct count = {direct_count}, Query count = {query_count}")
        
        # List all papers for debugging
        all_papers = list(Paper.select())
        logger.info(f"All papers in DB: {[p.doc_id for p in all_papers]}")
        
        # Convert to list and add metadata
        papers_list = []
        for paper in papers:
            try:
                metadata = Metadata.get_or_none(Metadata.paper == paper)
                paper.metadata = metadata
                papers_list.append(paper)
                logger.info(f"Added paper {paper.doc_id} to list")
            except Exception as e:
                logger.error(f"Error processing paper {paper.doc_id}: {e}")
                paper.metadata = None
                papers_list.append(paper)
        
        logger.info(f"Final papers_list length: {len(papers_list)}")
        
        return templates.TemplateResponse(
            "papers.html", 
            {
                "request": request, 
                "user": user, 
                "papers": papers_list
            }
        )
        
    except Exception as e:
        logger.error(f"Error in papers page: {e}", exc_info=True)
        return templates.TemplateResponse(
            "papers.html", 
            {
                "request": request, 
                "user": user, 
                "papers": [],
                "error": f"Error loading papers: {str(e)}"
            }
        )


@router.get("/papers/{doc_id}", response_class=HTMLResponse)
async def paper_detail(request: Request, doc_id: str):
    """Paper detail page"""
    user = require_auth(request)
    
    try:
        paper = get_paper_by_id(doc_id)
        if not paper:
            raise HTTPException(status_code=404, detail="Paper not found")
        
        # Get associated data
        metadata = Metadata.get_or_none(Metadata.paper == paper)
        embedding = Embedding.get_or_none(Embedding.paper == paper)
        layout = LayoutAnalysis.get_or_none(LayoutAnalysis.paper == paper)
        page_embeddings = list(PageEmbedding.select().where(PageEmbedding.paper == paper))
        
        return templates.TemplateResponse(
            "paper_detail.html", 
            {
                "request": request, 
                "user": user, 
                "paper": paper,
                "metadata": metadata,
                "embedding": embedding,
                "layout": layout,
                "page_embeddings": page_embeddings
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading paper: {str(e)}")


@router.post("/papers/{doc_id}/delete")
async def delete_paper_post(request: Request, doc_id: str):
    """Delete paper"""
    user = require_auth(request)
    
    try:
        paper = get_paper_by_id(doc_id)
        if not paper:
            return RedirectResponse(url="/admin/papers?error=Paper not found", status_code=302)
        
        # Delete associated records
        PageEmbedding.delete().where(PageEmbedding.paper == paper).execute()
        Embedding.delete().where(Embedding.paper == paper).execute()
        Metadata.delete().where(Metadata.paper == paper).execute()
        LayoutAnalysis.delete().where(LayoutAnalysis.paper == paper).execute()
        
        # Delete paper
        paper.delete_instance()
        
        return RedirectResponse(url="/admin/papers?message=Paper deleted successfully", status_code=302)
            
    except Exception as e:
        return RedirectResponse(url=f"/admin/papers?error=Error deleting paper: {str(e)}", status_code=302)


@router.get("/change-password", response_class=HTMLResponse)
async def change_password_page(request: Request):
    """Password change page"""
    user = require_auth(request)
    
    return templates.TemplateResponse(
        "change_password.html", 
        {
            "request": request, 
            "user": user
        }
    )


@router.post("/change-password")
async def change_password_post(
    request: Request, 
    current_password: str = Form(...), 
    new_password: str = Form(...), 
    confirm_password: str = Form(...)
):
    """Process password change"""
    user = require_auth(request)
    
    # Validate password confirmation
    if new_password != confirm_password:
        return templates.TemplateResponse(
            "change_password.html", 
            {
                "request": request, 
                "user": user, 
                "error": "New passwords do not match"
            }
        )
    
    # Validate password length
    if len(new_password) < 6:
        return templates.TemplateResponse(
            "change_password.html", 
            {
                "request": request, 
                "user": user, 
                "error": "Password must be at least 6 characters long"
            }
        )
    
    try:
        # Change password using AuthManager
        success = AuthManager.change_password(user.username, current_password, new_password)
        
        if success:
            # Log out user for security (they need to login with new password)
            response = RedirectResponse(url="/admin/login?message=Password changed successfully. Please login with your new password.", status_code=302)
            response.delete_cookie(key="access_token")
            return response
        else:
            return templates.TemplateResponse(
                "change_password.html", 
                {
                    "request": request, 
                    "user": user, 
                    "error": "Current password is incorrect"
                }
            )
            
    except Exception as e:
        return templates.TemplateResponse(
            "change_password.html", 
            {
                "request": request, 
                "user": user, 
                "error": f"Error changing password: {str(e)}"
            }
        )






@router.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    """PDF upload page"""
    user = require_auth(request)
    
    return templates.TemplateResponse(
        "upload.html", 
        {
            "request": request, 
            "user": user
        }
    )


# ChromaDB vector database monitoring page
@router.get("/vector-db", response_class=HTMLResponse)
async def vector_db_monitoring(request: Request):
    """ChromaDB vector database monitoring dashboard"""
    user = require_auth(request)
    
    try:
        # Get ChromaDB statistics
        vector_db = get_vector_db()
        chroma_stats = vector_db.get_collection_stats()
        chroma_health = vector_db.health_check()
        
        # Get SQLite paper counts for comparison
        total_papers = Paper.select().count()
        
        # Count papers with embeddings using distinct
        papers_with_embeddings = (Embedding
                                .select(Embedding.paper)
                                .distinct()
                                .count())
        
        # Count papers with page embeddings using distinct
        papers_with_page_embeddings = (PageEmbedding
                                     .select(PageEmbedding.paper)
                                     .distinct()
                                     .count())
        
        # Calculate coverage percentages
        embedding_coverage = (chroma_stats['papers_count'] / total_papers * 100) if total_papers > 0 else 0
        page_coverage = (papers_with_page_embeddings / total_papers * 100) if total_papers > 0 else 0
        
        # Prepare dashboard data
        dashboard_data = {
            'chromadb': {
                'status': 'healthy' if chroma_health else 'unhealthy',
                'papers_count': chroma_stats['papers_count'],
                'pages_count': chroma_stats['pages_count'],
                'embedding_coverage': round(embedding_coverage, 1),
                'page_coverage': round(page_coverage, 1)
            },
            'sqlite': {
                'total_papers': total_papers,
                'papers_with_embeddings': papers_with_embeddings,
                'papers_with_page_embeddings': papers_with_page_embeddings
            },
            'sync_status': {
                'papers_synced': chroma_stats['papers_count'] == papers_with_embeddings,
                'sync_rate': round((chroma_stats['papers_count'] / papers_with_embeddings * 100) if papers_with_embeddings > 0 else 0, 1)
            }
        }
        
        return templates.TemplateResponse(
            "vector_db_monitoring.html", 
            {
                "request": request, 
                "user": user,
                "dashboard_data": dashboard_data,
                "version": get_version()
            }
        )
        
    except Exception as e:
        return templates.TemplateResponse(
            "vector_db_monitoring.html", 
            {
                "request": request, 
                "user": user,
                "error": f"Error loading ChromaDB statistics: {str(e)}",
                "version": get_version()
            }
        )


# Performance monitoring page
@router.get("/performance", response_class=HTMLResponse)
async def performance_monitoring(request: Request):
    """Performance monitoring dashboard"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/admin/login", status_code=302)
    
    try:
        # Import here to avoid circular imports
        from performance_monitor import get_system_performance_stats
        from job_queue import get_queue_status
        
        # Get performance statistics
        perf_stats = get_system_performance_stats()
        queue_status = get_queue_status()
        
        return templates.TemplateResponse(
            "admin/performance.html",
            {
                "request": request,
                "user": user,
                "performance_stats": perf_stats,
                "queue_status": queue_status,
                "page_title": "Performance Monitoring"
            }
        )
        
    except Exception as e:
        return templates.TemplateResponse(
            "admin/performance.html",
            {
                "request": request,
                "user": user,
                "error": f"Failed to load performance data: {str(e)}",
                "page_title": "Performance Monitoring"
            }
        )

# Queue management page
@router.get("/queue", response_class=HTMLResponse)
async def queue_management(request: Request):
    """Job queue management dashboard"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/admin/login", status_code=302)
    
    try:
        from job_queue import get_queue_status
        from models import ProcessingJob
        
        # Get queue status
        queue_status = get_queue_status()
        
        # Get recent processing jobs
        recent_jobs = (ProcessingJob
                      .select()
                      .order_by(ProcessingJob.created_at.desc())
                      .limit(20))
        
        return templates.TemplateResponse(
            "admin/queue.html",
            {
                "request": request,
                "user": user,
                "queue_status": queue_status,
                "recent_jobs": recent_jobs,
                "current_time": datetime.now(),
                "page_title": "Job Queue Management"
            }
        )
        
    except Exception as e:
        return templates.TemplateResponse(
            "admin/queue.html",
            {
                "request": request,
                "user": user,
                "error": f"Failed to load queue data: {str(e)}",
                "current_time": datetime.now(),
                "page_title": "Job Queue Management"
            }
        )

# System monitoring page
@router.get("/system", response_class=HTMLResponse)
async def system_monitoring(request: Request):
    """System resource monitoring dashboard"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/admin/login", status_code=302)
    
    try:
        import psutil
        import time
        from performance_monitor import get_performance_monitor
        
        # Get current system metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Load average (Unix only)
        load_avg = None
        if hasattr(os, 'getloadavg'):
            load_avg = list(os.getloadavg())
        
        # Get performance monitor for historical data
        monitor = get_performance_monitor()
        recent_metrics = list(monitor.system_metrics)[-100:]  # Last 100 data points
        
        system_metrics = {
            "timestamp": time.time(),
            "cpu": {
                "current_percent": cpu_percent,
                "load_average": load_avg
            },
            "memory": {
                "total_gb": memory.total / 1024 / 1024 / 1024,
                "used_gb": memory.used / 1024 / 1024 / 1024,
                "available_gb": memory.available / 1024 / 1024 / 1024,
                "percent": memory.percent
            },
            "disk": {
                "total_gb": disk.total / 1024 / 1024 / 1024,
                "used_gb": disk.used / 1024 / 1024 / 1024,
                "free_gb": disk.free / 1024 / 1024 / 1024,
                "percent": disk.percent
            },
            "historical": recent_metrics
        }
        
        return templates.TemplateResponse(
            "admin/system.html",
            {
                "request": request,
                "user": user,
                "system_metrics": system_metrics,
                "page_title": "System Monitoring"
            }
        )
        
    except Exception as e:
        return templates.TemplateResponse(
            "admin/system.html",
            {
                "request": request,
                "user": user,
                "error": f"Failed to load system data: {str(e)}",
                "page_title": "System Monitoring"
            }
        )

# Duplicate Prevention monitoring page
@router.get("/duplicate-prevention", response_class=HTMLResponse)
async def duplicate_prevention_monitoring(request: Request):
    """Duplicate prevention system monitoring dashboard"""
    user = require_auth(request)
    
    try:
        # Get duplicate prevention statistics
        detector = get_duplicate_detector()
        dup_stats = detector.get_duplicate_stats()
        
        # Get performance statistics (last 30 days)
        performance_stats = detector.get_performance_stats(30)
        
        # Get recent detection attempts
        recent_detections = detector.get_recent_detections(20)
        
        # Get some sample hash records for display
        from models import FileHash, ContentHash, SampleEmbeddingHash, Paper
        
        # Recent file hashes
        recent_file_hashes = (FileHash
                            .select(FileHash, Paper.filename)
                            .join(Paper)
                            .order_by(FileHash.created_at.desc())
                            .limit(10))
        
        # Recent content hashes  
        recent_content_hashes = (ContentHash
                               .select(ContentHash, Paper.filename)
                               .join(Paper)
                               .order_by(ContentHash.created_at.desc())
                               .limit(10))
        
        # Recent sample embedding hashes
        recent_sample_hashes = (SampleEmbeddingHash
                              .select(SampleEmbeddingHash, Paper.filename)
                              .join(Paper)
                              .order_by(SampleEmbeddingHash.created_at.desc())
                              .limit(10))
        
        # Calculate efficiency metrics
        total_papers = Paper.select().count()
        hash_coverage = {
            'file_hash_coverage': (dup_stats['file_hashes_count'] / total_papers * 100) if total_papers > 0 else 0,
            'content_hash_coverage': (dup_stats['content_hashes_count'] / total_papers * 100) if total_papers > 0 else 0,
            'sample_hash_coverage': (dup_stats['sample_embedding_hashes_count'] / total_papers * 100) if total_papers > 0 else 0
        }
        
        dashboard_data = {
            'statistics': dup_stats,
            'performance': performance_stats,
            'recent_detections': recent_detections,
            'coverage': hash_coverage,
            'total_papers': total_papers,
            'recent_hashes': {
                'file_hashes': list(recent_file_hashes),
                'content_hashes': list(recent_content_hashes),
                'sample_hashes': list(recent_sample_hashes)
            }
        }
        
        return templates.TemplateResponse(
            "duplicate_prevention_monitoring.html",
            {
                "request": request,
                "user": user,
                "dashboard_data": dashboard_data,
                "version": get_version()
            }
        )
        
    except Exception as e:
        return templates.TemplateResponse(
            "duplicate_prevention_monitoring.html",
            {
                "request": request,
                "user": user,
                "error": f"Error loading duplicate prevention statistics: {str(e)}",
                "version": get_version()
            }
        )

# Scheduler management page
@router.get("/scheduler", response_class=HTMLResponse)
async def scheduler_management(request: Request):
    """Background scheduler management dashboard"""
    user = require_auth(request)
    
    try:
        from scheduler import get_background_scheduler
        
        # Get scheduler status
        scheduler = get_background_scheduler()
        scheduler_status = scheduler.get_status()
        
        # Get recent cleanup statistics if available
        last_cleanup = scheduler_status.get('last_cleanup')
        
        dashboard_data = {
            'scheduler_status': scheduler_status,
            'last_cleanup': last_cleanup,
            'cleanup_types': [
                {'id': 'daily', 'name': 'Daily Cleanup', 'description': 'Light maintenance - orphaned hashes and old logs'},
                {'id': 'weekly', 'name': 'Weekly Comprehensive', 'description': 'Full cleanup including duplicates and unused hashes'},
                {'id': 'monthly', 'name': 'Monthly Deep Clean', 'description': 'Aggressive cleanup with extended thresholds'}
            ]
        }
        
        return templates.TemplateResponse(
            "scheduler_management.html",
            {
                "request": request,
                "user": user,
                "dashboard_data": dashboard_data,
                "version": get_version()
            }
        )
        
    except Exception as e:
        return templates.TemplateResponse(
            "scheduler_management.html",
            {
                "request": request,
                "user": user,
                "error": f"Error loading scheduler management: {str(e)}",
                "version": get_version()
            }
        )

# Backup management endpoints
@router.post("/backup/trigger")
async def trigger_backup(
    request: Request,
    backup_type: str = "snapshot",
    compress: bool = True,
    description: str = "",
    retention_days: int = 30,
    unified: bool = False,
    user: AdminUser = Depends(require_auth)
):
    """Manually trigger a database backup"""
    try:
        # Validate backup type
        if backup_type not in ["full", "incremental", "snapshot"]:
            raise HTTPException(status_code=400, detail="Invalid backup type")
        
        options = {
            "compress": compress,
            "description": description or f"Manual backup by {user.username}",
            "retention_days": retention_days
        }
        
        if unified:
            # Create unified backup (SQLite + ChromaDB)
            from backup import get_unified_backup_manager
            backup_manager = get_unified_backup_manager()
            result = backup_manager.create_unified_backup(backup_type, options)
        else:
            # Create SQLite-only backup
            from backup import get_backup_manager
            backup_manager = get_backup_manager()
            result = backup_manager.create_backup(backup_type, options)
        
        return result
        
    except Exception as e:
        logger.error(f"Backup trigger failed: {e}")
        raise HTTPException(status_code=500, detail=f"Backup failed: {str(e)}")


@router.get("/backup/status")
async def get_backup_status(user: AdminUser = Depends(require_auth)):
    """Get current backup system status"""
    try:
        from backup import get_backup_manager, get_chromadb_backup_manager
        from pathlib import Path
        
        # Get SQLite backup status
        sqlite_manager = get_backup_manager()
        sqlite_status = sqlite_manager.get_backup_status()
        
        # Get ChromaDB backup status
        chromadb_manager = get_chromadb_backup_manager()
        chromadb_dir = chromadb_manager.chromadb_dir
        chromadb_exists = chromadb_dir.exists()
        
        # Count ChromaDB backups
        chromadb_backups = 0
        chromadb_size = 0
        if chromadb_manager.chromadb_backup_dir.exists():
            for subdir in ["daily", "weekly", "snapshots"]:
                backup_dir = chromadb_manager.chromadb_backup_dir / subdir
                if backup_dir.exists():
                    for backup_file in backup_dir.glob("*.tar*"):
                        chromadb_backups += 1
                        chromadb_size += backup_file.stat().st_size
        
        # Combined status
        status = {
            "sqlite": sqlite_status,
            "chromadb": {
                "directory_exists": chromadb_exists,
                "backup_directory": str(chromadb_manager.chromadb_backup_dir),
                "total_backups": chromadb_backups,
                "total_size_bytes": chromadb_size
            },
            "unified_backup_available": True
        }
        
        return status
        
    except Exception as e:
        logger.error(f"Failed to get backup status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get backup status: {str(e)}")


@router.get("/backup/history")
async def get_backup_history(
    limit: int = 50,
    user: AdminUser = Depends(require_auth)
):
    """Get backup history"""
    try:
        from backup import get_backup_manager
        
        backup_manager = get_backup_manager()
        history = backup_manager.get_backup_history(limit=limit)
        
        return {"backups": history, "total": len(history)}
        
    except Exception as e:
        logger.error(f"Failed to get backup history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get backup history: {str(e)}")


@router.post("/backup/restore/{backup_id}")
async def restore_backup(
    backup_id: str,
    target_path: Optional[str] = None,
    user: AdminUser = Depends(require_auth)
):
    """Restore a specific backup"""
    try:
        # Only superusers can restore backups
        if not user.is_superuser:
            raise HTTPException(status_code=403, detail="Only superusers can restore backups")
        
        from backup import get_backup_manager
        
        backup_manager = get_backup_manager()
        result = backup_manager.restore_backup(backup_id, target_path)
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Backup restore failed: {e}")
        raise HTTPException(status_code=500, detail=f"Restore failed: {str(e)}")


@router.get("/backup", response_class=HTMLResponse)
async def backup_management_page(request: Request, user: AdminUser = Depends(require_auth)):
    """Backup management dashboard page"""
    try:
        # Get backup status using the same logic as the API endpoint
        backup_status = await get_backup_status(user)
        
        # Get recent backups
        from backup import get_backup_manager
        backup_manager = get_backup_manager()
        recent_backups = backup_manager.get_backup_history(limit=10)
        
        return templates.TemplateResponse(
            "backup_management.html",
            {
                "request": request,
                "user": user,
                "backup_status": backup_status,
                "recent_backups": recent_backups,
                "version": get_version()
            }
        )
        
    except Exception as e:
        return templates.TemplateResponse(
            "backup_management.html",
            {
                "request": request,
                "user": user,
                "error": f"Error loading backup management: {str(e)}",
                "version": get_version()
            }
        )


@router.post("/backup/health-check")
async def run_backup_health_check(user: AdminUser = Depends(require_auth)):
    """Run manual backup health check"""
    try:
        from backup import get_backup_manager
        
        backup_manager = get_backup_manager()
        
        # Run health check
        backup_manager._backup_health_check()
        
        # Get current status
        status = backup_manager.get_backup_status()
        
        return {
            "status": "completed",
            "timestamp": datetime.now().isoformat(),
            "backup_status": status
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@router.post("/backup/verify/{backup_id}")
async def verify_backup_integrity(backup_id: str, user: AdminUser = Depends(require_auth)):
    """Verify the integrity of a specific backup"""
    try:
        from backup import get_backup_manager
        from pathlib import Path
        
        backup_manager = get_backup_manager()
        
        # Find backup in history
        backup_info = None
        for backup in backup_manager.history:
            if backup.get("backup_id") == backup_id:
                backup_info = backup
                break
        
        if not backup_info:
            raise HTTPException(status_code=404, detail=f"Backup not found: {backup_id}")
        
        if backup_info.get("status") != "completed":
            raise HTTPException(status_code=400, detail="Cannot verify failed backup")
        
        backup_path = Path(backup_info["path"])
        if not backup_path.exists():
            raise HTTPException(status_code=404, detail="Backup file not found")
        
        # Verify integrity
        is_valid = backup_manager.verify_backup_integrity(backup_path)
        
        return {
            "backup_id": backup_id,
            "path": str(backup_path),
            "integrity_check": "passed" if is_valid else "failed",
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Backup verification failed: {e}")
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")


@router.get("/disaster-recovery/status")
async def get_disaster_recovery_status(user: AdminUser = Depends(require_auth)):
    """Get disaster recovery readiness status"""
    try:
        from backup import get_backup_manager, get_chromadb_backup_manager
        from pathlib import Path
        import shutil
        
        # Check backup systems
        sqlite_manager = get_backup_manager()
        chromadb_manager = get_chromadb_backup_manager()
        
        # Get backup counts and recent status
        sqlite_status = sqlite_manager.get_backup_status()
        recent_backups = sqlite_manager.get_backup_history(limit=5)
        
        # Check ChromaDB backups
        chromadb_backups = 0
        if chromadb_manager.chromadb_backup_dir.exists():
            for subdir in ["daily", "weekly", "snapshots"]:
                backup_dir = chromadb_manager.chromadb_backup_dir / subdir
                if backup_dir.exists():
                    chromadb_backups += len(list(backup_dir.glob("*.tar*")))
        
        # Check disk space
        total, used, free = shutil.disk_usage("/refdata")
        free_gb = free // (1024**3)
        
        # Check scripts
        scripts_dir = Path("/home/jikhanjung/projects/RefServer/scripts")
        recovery_script = scripts_dir / "disaster_recovery.sh"
        check_script = scripts_dir / "check_backups.sh"
        
        # Calculate readiness score
        score = 0
        max_score = 10
        
        # Recent backups (3 points)
        if len([b for b in recent_backups if b.get("status") == "completed"]) >= 3:
            score += 3
        elif len([b for b in recent_backups if b.get("status") == "completed"]) >= 1:
            score += 1
        
        # Disk space (2 points)
        if free_gb >= 10:
            score += 2
        elif free_gb >= 5:
            score += 1
        
        # ChromaDB backups (2 points)
        if chromadb_backups >= 3:
            score += 2
        elif chromadb_backups >= 1:
            score += 1
        
        # Scripts available (2 points)
        if recovery_script.exists() and check_script.exists():
            score += 2
        elif recovery_script.exists() or check_script.exists():
            score += 1
        
        # Scheduler running (1 point)
        if sqlite_status.get("scheduler_running"):
            score += 1
        
        # Determine readiness level
        if score >= 8:
            readiness = "excellent"
        elif score >= 6:
            readiness = "good"
        elif score >= 4:
            readiness = "fair"
        else:
            readiness = "poor"
        
        return {
            "readiness_score": f"{score}/{max_score}",
            "readiness_level": readiness,
            "sqlite_backups": sqlite_status.get("total_backups", 0),
            "chromadb_backups": chromadb_backups,
            "recent_successful_backups": len([b for b in recent_backups if b.get("status") == "completed"]),
            "free_disk_space_gb": free_gb,
            "scheduler_running": sqlite_status.get("scheduler_running", False),
            "recovery_scripts_available": {
                "disaster_recovery": recovery_script.exists(),
                "backup_check": check_script.exists()
            },
            "recommendations": [
                "Ensure at least 3 recent successful backups" if len([b for b in recent_backups if b.get("status") == "completed"]) < 3 else None,
                "Free up disk space (minimum 10GB recommended)" if free_gb < 10 else None,
                "Enable backup scheduler" if not sqlite_status.get("scheduler_running") else None,
                "Create ChromaDB backups" if chromadb_backups == 0 else None
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to get disaster recovery status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get disaster recovery status: {str(e)}")


# Database Consistency Check endpoints
@router.get("/consistency/check")
async def run_consistency_check(user: AdminUser = Depends(require_auth)):
    """Run full database consistency check"""
    try:
        from consistency_check import get_consistency_checker
        
        checker = get_consistency_checker()
        results = checker.run_full_consistency_check()
        
        return results
        
    except Exception as e:
        logger.error(f"Consistency check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Consistency check failed: {str(e)}")


@router.get("/consistency/summary")
async def get_consistency_summary(user: AdminUser = Depends(require_auth)):
    """Get quick consistency summary"""
    try:
        from consistency_check import get_consistency_checker
        
        checker = get_consistency_checker()
        summary = checker.get_consistency_summary()
        
        return summary
        
    except Exception as e:
        logger.error(f"Failed to get consistency summary: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get consistency summary: {str(e)}")


@router.post("/consistency/fix")
async def fix_consistency_issues(
    issue_types: List[str] = None,
    user: AdminUser = Depends(require_auth)
):
    """Automatically fix consistency issues"""
    try:
        # Only superusers can fix issues
        if not user.is_superuser:
            raise HTTPException(status_code=403, detail="Only superusers can fix consistency issues")
        
        from consistency_check import get_consistency_checker, ConsistencyIssueType
        
        checker = get_consistency_checker()
        
        # Convert string issue types to enum
        fix_types = None
        if issue_types:
            try:
                fix_types = [ConsistencyIssueType(issue_type) for issue_type in issue_types]
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid issue type: {str(e)}")
        
        results = checker.auto_fix_issues(fix_types)
        
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fix consistency issues: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fix issues: {str(e)}")


@router.get("/consistency", response_class=HTMLResponse)
async def consistency_management_page(request: Request, user: AdminUser = Depends(require_auth)):
    """Database consistency management page"""
    try:
        from consistency_check import get_consistency_checker
        
        checker = get_consistency_checker()
        summary = checker.get_consistency_summary()
        
        return templates.TemplateResponse(
            "consistency_management.html",
            {
                "request": request,
                "user": user,
                "consistency_summary": summary,
                "version": get_version()
            }
        )
        
    except Exception as e:
        return templates.TemplateResponse(
            "consistency_management.html",
            {
                "request": request,
                "user": user,
                "error": f"Error loading consistency management: {str(e)}",
                "version": get_version()
            }
        )


# Circuit Breaker Management
@router.get("/services", response_class=HTMLResponse)
async def services_management_page(request: Request, user: AdminUser = Depends(require_auth)):
    """Service circuit breaker management page"""
    try:
        circuit_manager = get_circuit_breaker_manager()
        services_status = circuit_manager.get_all_status()
        
        return templates.TemplateResponse(
            "services_management.html",
            {
                "request": request,
                "user": user,
                "services_status": services_status,
                "version": get_version()
            }
        )
        
    except Exception as e:
        return templates.TemplateResponse(
            "services_management.html",
            {
                "request": request,
                "user": user,
                "error": f"Error loading services management: {str(e)}",
                "version": get_version()
            }
        )


@router.get("/services/status")
async def get_services_status(user: AdminUser = Depends(require_auth)):
    """Get current status of all circuit breakers"""
    try:
        circuit_manager = get_circuit_breaker_manager()
        return circuit_manager.get_all_status()
        
    except Exception as e:
        logger.error(f"Failed to get services status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get services status: {str(e)}")


@router.post("/services/{service_name}/disable")
async def disable_service(
    service_name: str,
    reason: str = Form("Manually disabled by admin"),
    user: AdminUser = Depends(require_auth)
):
    """Manually disable a service (open circuit breaker)"""
    try:
        circuit_manager = get_circuit_breaker_manager()
        circuit_manager.force_open_service(service_name, reason)
        
        return {
            "success": True,
            "message": f"Service '{service_name}' has been disabled",
            "service_name": service_name,
            "reason": reason
        }
        
    except Exception as e:
        logger.error(f"Failed to disable service {service_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to disable service: {str(e)}")


@router.post("/services/{service_name}/enable")
async def enable_service(
    service_name: str,
    user: AdminUser = Depends(require_auth)
):
    """Manually enable a service (close circuit breaker)"""
    try:
        circuit_manager = get_circuit_breaker_manager()
        circuit_manager.force_close_service(service_name)
        
        return {
            "success": True,
            "message": f"Service '{service_name}' has been enabled",
            "service_name": service_name
        }
        
    except Exception as e:
        logger.error(f"Failed to enable service {service_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to enable service: {str(e)}")


@router.post("/services/{service_name}/reset")
async def reset_service_stats(
    service_name: str,
    user: AdminUser = Depends(require_auth)
):
    """Reset statistics for a service circuit breaker"""
    try:
        circuit_manager = get_circuit_breaker_manager()
        circuit_manager.reset_service_stats(service_name)
        
        return {
            "success": True,
            "message": f"Statistics for service '{service_name}' have been reset",
            "service_name": service_name
        }
        
    except Exception as e:
        logger.error(f"Failed to reset stats for service {service_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset service stats: {str(e)}")


@router.post("/services/{service_name}/test")
async def test_service_connection(
    service_name: str,
    user: AdminUser = Depends(require_auth)
):
    """Test connection to a specific service"""
    try:
        circuit_manager = get_circuit_breaker_manager()
        
        # Get the specific service and test its connection
        test_result = {"success": False, "error": "Unknown service"}
        
        if service_name == "ollama_llava":
            from ocr_quality import get_quality_assessor
            try:
                assessor = get_quality_assessor()
                test_result = {
                    "success": assessor.check_ollama_connection(),
                    "service_enabled": assessor.enabled,
                    "host": assessor.ollama_host if assessor.enabled else "Disabled"
                }
            except Exception as e:
                test_result = {"success": False, "error": str(e)}
                
        elif service_name == "ollama_metadata":
            from metadata import get_metadata_extractor
            try:
                extractor = get_metadata_extractor()
                test_result = {
                    "success": extractor.check_ollama_connection(),
                    "service_enabled": extractor.enabled,
                    "host": extractor.ollama_host if extractor.enabled else "Disabled",
                    "model": extractor.model_name if extractor.enabled else "N/A"
                }
            except Exception as e:
                test_result = {"success": False, "error": str(e)}
                
        elif service_name == "huridocs_layout":
            from layout import is_layout_service_available
            try:
                test_result = {"success": is_layout_service_available()}
            except Exception as e:
                test_result = {"success": False, "error": str(e)}
        
        # Get current circuit breaker status
        breaker_status = circuit_manager.get_breaker(service_name).get_status()
        
        return {
            "service_name": service_name,
            "test_result": test_result,
            "circuit_breaker_status": breaker_status,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to test service {service_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to test service: {str(e)}")


# Database management
@router.get("/database", response_class=HTMLResponse)
async def database_management(request: Request):
    """Database management page"""
    user = require_auth(request)
    
    # Only superusers can access database management
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser access required")
    
    stats = get_stats()
    
    return templates.TemplateResponse(
        "database_management.html", 
        {
            "request": request, 
            "user": user, 
            "stats": stats,
            "page_title": "Database Management",
            "version": get_version()
        }
    )

@router.post("/database/reset")
async def reset_database(request: Request):
    """Reset all database data (DANGER: This will delete all data!)"""
    user = require_auth(request)
    
    # Only superusers can reset database
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser access required")
    
    try:
        # Import necessary modules
        import os
        import shutil
        from vector_db import get_vector_db
        
        logger.warning(f"🚨 Database reset initiated by user: {user.username}")
        
        # 1. Clear SQLite tables
        logger.info("🗑️ Clearing SQLite tables...")
        
        # Delete in correct order to avoid foreign key constraints
        from models import ProcessingJob, PageEmbedding, Embedding, LayoutAnalysis, Metadata, Paper
        
        ProcessingJob.delete().execute()
        logger.info("  ✅ ProcessingJob table cleared")
        
        PageEmbedding.delete().execute()
        logger.info("  ✅ PageEmbedding table cleared")
        
        Embedding.delete().execute()
        logger.info("  ✅ Embedding table cleared")
        
        LayoutAnalysis.delete().execute()
        logger.info("  ✅ LayoutAnalysis table cleared")
        
        Metadata.delete().execute()
        logger.info("  ✅ Metadata table cleared")
        
        Paper.delete().execute()
        logger.info("  ✅ Paper table cleared")
        
        # 2. Clear ChromaDB collections
        logger.info("🗑️ Clearing ChromaDB collections...")
        try:
            vector_db = get_vector_db()
            
            # Delete all documents from collections
            papers_collection = vector_db.papers_collection
            pages_collection = vector_db.pages_collection
            
            # Get all IDs and delete them
            try:
                papers_result = papers_collection.get()
                if papers_result['ids']:
                    papers_collection.delete(ids=papers_result['ids'])
                    logger.info(f"  ✅ ChromaDB papers collection cleared ({len(papers_result['ids'])} documents)")
                else:
                    logger.info("  ✅ ChromaDB papers collection was already empty")
            except Exception as e:
                logger.warning(f"  ⚠️ Error clearing papers collection: {e}")
            
            try:
                pages_result = pages_collection.get()
                if pages_result['ids']:
                    pages_collection.delete(ids=pages_result['ids'])
                    logger.info(f"  ✅ ChromaDB pages collection cleared ({len(pages_result['ids'])} documents)")
                else:
                    logger.info("  ✅ ChromaDB pages collection was already empty")
            except Exception as e:
                logger.warning(f"  ⚠️ Error clearing pages collection: {e}")
                
        except Exception as e:
            logger.error(f"  ❌ Error clearing ChromaDB: {e}")
        
        # 3. Clear file storage
        logger.info("🗑️ Clearing file storage...")
        data_dirs = ['/refdata', './data']
        
        for data_dir in data_dirs:
            if os.path.exists(data_dir):
                # Clear PDFs directory
                pdfs_dir = os.path.join(data_dir, 'pdfs')
                if os.path.exists(pdfs_dir):
                    for filename in os.listdir(pdfs_dir):
                        if filename.endswith('.pdf'):
                            os.remove(os.path.join(pdfs_dir, filename))
                    logger.info(f"  ✅ PDF files cleared from {pdfs_dir}")
                
                # Clear images directory
                images_dir = os.path.join(data_dir, 'images')
                if os.path.exists(images_dir):
                    for filename in os.listdir(images_dir):
                        if filename.endswith(('.png', '.jpg', '.jpeg')):
                            os.remove(os.path.join(images_dir, filename))
                    logger.info(f"  ✅ Image files cleared from {images_dir}")
                
                # Clear temp directory
                temp_dir = os.path.join(data_dir, 'temp')
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                    os.makedirs(temp_dir, exist_ok=True)
                    logger.info(f"  ✅ Temp directory cleared: {temp_dir}")
        
        logger.info("✅ Database reset completed successfully")
        
        return {
            "success": True,
            "message": "Database reset completed successfully",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Database reset failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database reset failed: {str(e)}")

@router.post("/papers/{doc_id}/regenerate-page-embeddings")
async def regenerate_page_embeddings(doc_id: str, request: Request):
    """Regenerate page embeddings for a specific paper and save to ChromaDB"""
    user = require_auth(request)
    
    # Only superusers can regenerate embeddings
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser access required")
    
    try:
        from models import Paper, PageEmbedding
        from embedding import save_page_embeddings_to_vectordb
        from text_extraction import extract_page_texts_from_pdf
        from embedding import generate_page_embeddings
        
        logger.info(f"🔄 Regenerating page embeddings for paper: {doc_id}")
        
        # Get paper info
        try:
            paper = Paper.get(Paper.doc_id == doc_id)
        except Paper.DoesNotExist:
            raise HTTPException(status_code=404, detail=f"Paper not found: {doc_id}")
        
        # Check if PDF file exists
        pdf_path = paper.file_path
        if not os.path.exists(pdf_path):
            raise HTTPException(status_code=404, detail=f"PDF file not found: {pdf_path}")
        
        logger.info(f"📄 Found paper: {paper.filename} at {pdf_path}")
        
        # Extract page texts from PDF
        page_texts, page_count = extract_page_texts_from_pdf(pdf_path)
        logger.info(f"📚 Extracted {page_count} pages of text")
        
        if not page_texts or page_count == 0:
            raise HTTPException(status_code=400, detail="No text extracted from PDF")
        
        # Generate new embeddings
        logger.info(f"🧮 Generating new page embeddings...")
        page_embeddings = generate_page_embeddings(page_texts)
        
        if not page_embeddings or len(page_embeddings) != page_count:
            raise HTTPException(status_code=500, detail=f"Embedding generation failed: expected {page_count}, got {len(page_embeddings) if page_embeddings else 0}")
        
        # Prepare data for ChromaDB
        page_embeddings_data = []
        for i, (page_text, page_embedding) in enumerate(zip(page_texts, page_embeddings)):
            page_embeddings_data.append((i + 1, page_text, page_embedding))  # 1-based page numbering
        
        logger.info(f"📊 Prepared {len(page_embeddings_data)} page embeddings for save")
        
        # Save to ChromaDB
        logger.info(f"💾 Saving page embeddings to ChromaDB...")
        success = save_page_embeddings_to_vectordb(doc_id, page_embeddings_data)
        
        if success:
            logger.info(f"✅ Page embeddings regenerated successfully for {doc_id}")
            
            # Update SQLite metadata (replace existing records)
            try:
                # Delete existing page embeddings
                PageEmbedding.delete().where(PageEmbedding.paper == paper).execute()
                
                # Insert new metadata (without vector blobs since they're in ChromaDB)
                batch_data = []
                for page_number, page_text, embedding_vector in page_embeddings_data:
                    batch_data.append({
                        'paper': paper,
                        'page_number': page_number,
                        'page_text': page_text,
                        'vector_blob': b'',  # Empty blob - actual vector is in ChromaDB
                        'vector_dim': len(embedding_vector),
                        'model_name': 'bge-m3'
                    })
                
                PageEmbedding.insert_many(batch_data).execute()
                logger.info(f"✅ Updated SQLite metadata for {len(batch_data)} page embeddings")
                
            except Exception as sqlite_error:
                logger.warning(f"⚠️ Failed to update SQLite metadata: {sqlite_error}")
                # ChromaDB save was successful, so this is not critical
            
            return {
                "success": True,
                "message": f"Page embeddings regenerated successfully for {doc_id}",
                "pages_processed": len(page_embeddings_data),
                "saved_to_chromadb": True
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to save page embeddings to ChromaDB")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to regenerate page embeddings for {doc_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Embedding regeneration failed: {str(e)}")

# Security Settings Management
@router.get("/security", response_class=HTMLResponse)
async def security_settings_page(request: Request):
    """Security settings management page"""
    user = require_auth(request)
    
    # Only superusers can access security settings
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser access required")
    
    try:
        from file_security import get_security_status
        
        security_status = get_security_status()
        
        return templates.TemplateResponse(
            "security_settings.html",
            {
                "request": request,
                "user": user,
                "security_status": security_status,
                "version": get_version()
            }
        )
        
    except Exception as e:
        return templates.TemplateResponse(
            "security_settings.html",
            {
                "request": request,
                "user": user,
                "error": f"Error loading security settings: {str(e)}",
                "version": get_version()
            }
        )


@router.get("/security/status")
async def get_security_status_api(user: AdminUser = Depends(require_auth)):
    """Get current security system status"""
    try:
        from file_security import get_security_status
        return get_security_status()
        
    except Exception as e:
        logger.error(f"Failed to get security status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get security status: {str(e)}")


@router.post("/security/quarantine/toggle")
async def toggle_quarantine(
    enable: bool = Form(...),
    user: AdminUser = Depends(require_auth)
):
    """Toggle quarantine system on/off"""
    try:
        # Only superusers can change security settings
        if not user.is_superuser:
            raise HTTPException(status_code=403, detail="Only superusers can change security settings")
        
        from file_security import get_file_validator
        
        validator = get_file_validator()
        validator.config.enable_quarantine = enable
        
        # Update environment variable (for current session)
        import os
        os.environ['ENABLE_QUARANTINE'] = 'true' if enable else 'false'
        
        logger.info(f"File quarantine {'enabled' if enable else 'disabled'} by {user.username}")
        
        return {
            "success": True,
            "message": f"File quarantine {'enabled' if enable else 'disabled'} successfully",
            "quarantine_enabled": enable
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to toggle quarantine: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to toggle quarantine: {str(e)}")


@router.post("/security/limits/update")
async def update_security_limits(
    max_file_size_mb: int = Form(...),
    max_uploads_per_hour: int = Form(...),
    max_uploads_per_day: int = Form(...),
    user: AdminUser = Depends(require_auth)
):
    """Update file upload limits"""
    try:
        # Only superusers can change security settings
        if not user.is_superuser:
            raise HTTPException(status_code=403, detail="Only superusers can change security settings")
        
        from file_security import get_file_validator
        
        validator = get_file_validator()
        
        # Update configuration
        validator.config.max_file_size = max_file_size_mb * 1024 * 1024  # Convert MB to bytes
        validator.config.max_uploads_per_hour = max_uploads_per_hour
        validator.config.max_uploads_per_day = max_uploads_per_day
        
        # Update environment variables (for current session)
        import os
        os.environ['MAX_FILE_SIZE'] = str(validator.config.max_file_size)
        os.environ['MAX_UPLOADS_PER_HOUR'] = str(max_uploads_per_hour)
        os.environ['MAX_UPLOADS_PER_DAY'] = str(max_uploads_per_day)
        
        logger.info(f"Security limits updated by {user.username}: {max_file_size_mb}MB, {max_uploads_per_hour}/hour, {max_uploads_per_day}/day")
        
        return {
            "success": True,
            "message": "Security limits updated successfully",
            "limits": {
                "max_file_size_mb": max_file_size_mb,
                "max_uploads_per_hour": max_uploads_per_hour,
                "max_uploads_per_day": max_uploads_per_day
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update security limits: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update security limits: {str(e)}")


@router.get("/security/quarantine/files")
async def get_quarantine_files(user: AdminUser = Depends(require_auth)):
    """Get list of quarantined files"""
    try:
        from file_security import get_file_validator
        
        validator = get_file_validator()
        quarantine_info = validator.get_quarantine_info()
        
        return quarantine_info
        
    except Exception as e:
        logger.error(f"Failed to get quarantine files: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get quarantine files: {str(e)}")


@router.delete("/security/quarantine/clear")
async def clear_quarantine(user: AdminUser = Depends(require_auth)):
    """Clear all quarantined files"""
    try:
        # Only superusers can clear quarantine
        if not user.is_superuser:
            raise HTTPException(status_code=403, detail="Only superusers can clear quarantine")
        
        from file_security import get_file_validator
        import shutil
        
        validator = get_file_validator()
        
        if validator.config.enable_quarantine and validator.config.quarantine_dir.exists():
            # Remove all files in quarantine directory
            shutil.rmtree(validator.config.quarantine_dir)
            validator.config.quarantine_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Quarantine cleared by {user.username}")
            
            return {
                "success": True,
                "message": "Quarantine cleared successfully"
            }
        else:
            return {
                "success": True,
                "message": "Quarantine directory was already empty or quarantine is disabled"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to clear quarantine: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear quarantine: {str(e)}")


# Page Image Generation
@router.get("/page-image/{doc_id}/{page_number}")
async def get_page_image(
    doc_id: str, 
    page_number: int,
    user: AdminUser = Depends(require_auth)
):
    """Generate and return a specific page as an image"""
    try:
        from models import Paper
        import pdf2image
        from fastapi.responses import StreamingResponse
        import io
        import os
        
        # Get paper info
        try:
            paper = Paper.get(Paper.doc_id == doc_id)
        except Paper.DoesNotExist:
            raise HTTPException(status_code=404, detail=f"Paper not found: {doc_id}")
        
        # Check if PDF file exists
        pdf_path = paper.file_path
        if not os.path.exists(pdf_path):
            raise HTTPException(status_code=404, detail=f"PDF file not found: {pdf_path}")
        
        logger.info(f"Generating image for page {page_number} of {pdf_path}")
        
        # Convert specific page to image
        try:
            # Try with specific poppler path if needed
            poppler_path = None
            if os.path.exists('/usr/bin'):
                poppler_path = '/usr/bin'
            
            logger.info(f"Converting PDF to image with poppler_path: {poppler_path}")
            
            pages = pdf2image.convert_from_path(
                pdf_path,
                first_page=page_number,
                last_page=page_number,
                dpi=150,  # Good quality for display
                fmt='PNG',
                poppler_path=poppler_path
            )
            
            if not pages:
                logger.error(f"No pages returned for page {page_number}")
                raise HTTPException(status_code=404, detail=f"Page {page_number} not found in PDF")
            
            logger.info(f"Successfully converted page {page_number} to image")
            
            # Convert PIL image to bytes
            img_buffer = io.BytesIO()
            pages[0].save(img_buffer, format='PNG')
            img_buffer.seek(0)
            
            # Get the image data
            image_data = img_buffer.getvalue()
            logger.info(f"Image size: {len(image_data)} bytes")
            
            return StreamingResponse(
                io.BytesIO(image_data),
                media_type="image/png",
                headers={
                    "Content-Disposition": f"inline; filename=page_{page_number}_{doc_id}.png",
                    "Content-Length": str(len(image_data)),
                    "Cache-Control": "no-cache"
                }
            )
            
        except Exception as e:
            logger.error(f"Error converting PDF page to image: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to generate page image: {str(e)}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get page image for {doc_id} page {page_number}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get page image: {str(e)}")


@router.get("/page-viewer/{doc_id}/{page_number}", response_class=HTMLResponse)
async def page_viewer(
    request: Request,
    doc_id: str, 
    page_number: int
):
    """Page viewer showing image and text side by side"""
    user = require_auth(request)
    
    try:
        from models import Paper, PageEmbedding
        
        # Get paper info
        try:
            paper = Paper.get(Paper.doc_id == doc_id)
        except Paper.DoesNotExist:
            raise HTTPException(status_code=404, detail=f"Paper not found: {doc_id}")
        
        # Get page embedding (for text)
        try:
            page_embedding = PageEmbedding.get(
                (PageEmbedding.paper == paper) & 
                (PageEmbedding.page_number == page_number)
            )
        except PageEmbedding.DoesNotExist:
            page_embedding = None
        
        # Get all page numbers for this paper for navigation
        all_pages = list(
            PageEmbedding
            .select(PageEmbedding.page_number)
            .where(PageEmbedding.paper == paper)
            .order_by(PageEmbedding.page_number)
        )
        page_numbers = [p.page_number for p in all_pages]
        
        # Calculate navigation info
        total_pages = len(page_numbers)
        current_index = page_numbers.index(page_number) if page_number in page_numbers else -1
        
        prev_page = page_numbers[current_index - 1] if current_index > 0 else None
        next_page = page_numbers[current_index + 1] if current_index < total_pages - 1 else None
        
        return templates.TemplateResponse(
            "page_viewer.html",
            {
                "request": request,
                "user": user,
                "paper": paper,
                "page_number": page_number,
                "page_embedding": page_embedding,
                "total_pages": total_pages,
                "current_page_index": current_index + 1,  # 1-based index for display
                "prev_page": prev_page,
                "next_page": next_page,
                "page_numbers": page_numbers,
                "version": get_version()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to load page viewer for {doc_id} page {page_number}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load page viewer: {str(e)}")


@router.post("/page-viewer/{doc_id}/{page_number}/re-ocr")
async def re_ocr_page_with_tesseract(
    doc_id: str, 
    page_number: int,
    user: AdminUser = Depends(require_auth)
):
    """Re-OCR a specific page using Tesseract"""
    try:
        from models import Paper, PageEmbedding
        from ocr import perform_page_ocr_with_tesseract, detect_language_hybrid, get_tesseract_language
        import os
        
        # Get paper info
        try:
            paper = Paper.get(Paper.doc_id == doc_id)
        except Paper.DoesNotExist:
            raise HTTPException(status_code=404, detail=f"Paper not found: {doc_id}")
        
        # Check if PDF file exists
        pdf_path = paper.file_path
        if not os.path.exists(pdf_path):
            raise HTTPException(status_code=404, detail=f"PDF file not found: {pdf_path}")
        
        logger.info(f"Re-OCR starting for {doc_id} page {page_number} using Tesseract")
        
        # Detect language for better OCR results
        try:
            detected_lang = detect_language_hybrid(pdf_path)
            tesseract_lang = detected_lang if detected_lang else 'eng'
            logger.info(f"Using language {tesseract_lang} for OCR")
        except Exception as e:
            logger.warning(f"Language detection failed: {e}, using English")
            tesseract_lang = 'eng'
        
        # Perform OCR on the specific page with paragraph detection (PSM 4)
        extracted_text, confidence = perform_page_ocr_with_tesseract(
            pdf_path, page_number, tesseract_lang, psm_mode=4
        )
        
        if not extracted_text:
            raise HTTPException(status_code=500, detail="Tesseract OCR returned empty text")
        
        logger.info(f"Tesseract OCR extracted {len(extracted_text)} characters with {confidence:.1f}% confidence")
        
        # Get existing text for comparison
        existing_text = ""
        try:
            page_embedding = PageEmbedding.get(
                (PageEmbedding.paper == paper) & 
                (PageEmbedding.page_number == page_number)
            )
            existing_text = page_embedding.page_text or ""
        except PageEmbedding.DoesNotExist:
            existing_text = ""
        
        # Generate embedding comparison if both texts exist
        embedding_comparison = None
        if existing_text and extracted_text:
            try:
                from embedding import generate_text_embedding
                from embedding_utils import compare_embeddings
                
                # Generate embeddings for both texts
                existing_embedding = generate_text_embedding(existing_text)
                new_embedding = generate_text_embedding(extracted_text)
                
                if existing_embedding is not None and new_embedding is not None:
                    embedding_comparison = compare_embeddings(
                        existing_embedding, new_embedding,
                        existing_text, extracted_text
                    )
                    logger.info(f"Embedding comparison completed - similarity: {embedding_comparison.get('embedding_comparison', {}).get('cosine_similarity', 0):.3f}")
                else:
                    logger.warning("Failed to generate embeddings for comparison")
            except Exception as e:
                logger.error(f"Failed to compare embeddings: {e}")
        
        logger.info(f"Tesseract re-OCR completed for {doc_id} page {page_number}, awaiting user selection")
        
        response = {
            "success": True,
            "message": "OCR completed successfully",
            "requires_comparison": True,
            "existing_text": existing_text,
            "new_text": extracted_text,
            "existing_length": len(existing_text),
            "new_length": len(extracted_text),
            "confidence": confidence,
            "language": tesseract_lang,
            "preview_existing": existing_text[:300] + "..." if len(existing_text) > 300 else existing_text,
            "preview_new": extracted_text[:300] + "..." if len(extracted_text) > 300 else extracted_text
        }
        
        # Add embedding comparison if available
        if embedding_comparison:
            response["embedding_comparison"] = embedding_comparison
        
        return response
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to re-OCR page {page_number} for {doc_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Re-OCR failed: {str(e)}")


@router.post("/page-viewer/{doc_id}/{page_number}/apply-ocr")
async def apply_ocr_result(
    doc_id: str,
    page_number: int,
    request: Request,
    user: AdminUser = Depends(require_auth)
):
    """Apply selected OCR result to page embedding with comparison"""
    try:
        from models import Paper, PageEmbedding
        from embedding_utils import create_embedding_comparison_report
        import json
        
        # Get request body
        body = await request.body()
        data = json.loads(body.decode('utf-8'))
        
        selected_text = data.get('selected_text', '')
        apply_to_all = data.get('apply_to_all', False)
        
        if not selected_text:
            raise HTTPException(status_code=400, detail="No text selected")
        
        # Get paper info
        try:
            paper = Paper.get(Paper.doc_id == doc_id)
        except Paper.DoesNotExist:
            raise HTTPException(status_code=404, detail=f"Paper not found: {doc_id}")
        
        # Get existing embedding for comparison
        old_embedding = None
        old_text = ""
        embedding_comparison = None
        
        try:
            existing_page_embedding = PageEmbedding.get(
                (PageEmbedding.paper == paper) & 
                (PageEmbedding.page_number == page_number)
            )
            # Get existing embedding from vector_blob
            if existing_page_embedding.vector_blob:
                import numpy as np
                old_embedding = np.frombuffer(existing_page_embedding.vector_blob, dtype=np.float32).tolist()
            else:
                old_embedding = None
            old_text = existing_page_embedding.page_text or ""
        except PageEmbedding.DoesNotExist:
            pass
        
        # Generate new embedding for selected text
        new_embedding = None
        try:
            from embedding import generate_text_embedding
            embedding_vector = generate_text_embedding(selected_text)
            if embedding_vector is not None:
                new_embedding = embedding_vector.tolist()
        except Exception as emb_error:
            logger.warning(f"Failed to generate new embedding: {emb_error}")
        
        # Compare embeddings if both exist
        if old_embedding and new_embedding:
            embedding_comparison = create_embedding_comparison_report(
                old_embedding, new_embedding, old_text, selected_text
            )
            logger.info(f"Embedding comparison: {embedding_comparison.get('overall_assessment', 'unknown')}")
        
        # Update or create page embedding
        try:
            page_embedding = PageEmbedding.get(
                (PageEmbedding.paper == paper) & 
                (PageEmbedding.page_number == page_number)
            )
            # Update existing embedding
            page_embedding.page_text = selected_text
            if new_embedding:
                import numpy as np
                # Convert to numpy array and store as blob
                vector_array = np.array(new_embedding, dtype=np.float32)
                page_embedding.vector_blob = vector_array.tobytes()
                page_embedding.vector_dim = len(new_embedding)
            page_embedding.save()
            logger.info(f"Updated page embedding for page {page_number}")
            
        except PageEmbedding.DoesNotExist:
            # Create new page embedding
            try:
                from embedding import generate_text_embedding
                embedding_vector = generate_text_embedding(selected_text)
                if embedding_vector is not None:
                    import numpy as np
                    vector_array = np.array(embedding_vector, dtype=np.float32)
                    PageEmbedding.create(
                        paper=paper,
                        page_number=page_number,
                        page_text=selected_text,
                        vector_blob=vector_array.tobytes(),
                        vector_dim=len(embedding_vector),
                        model_name='bge-m3'
                    )
                else:
                    PageEmbedding.create(
                        paper=paper,
                        page_number=page_number,
                        page_text=selected_text,
                        vector_blob=None,
                        vector_dim=0,
                        model_name='tesseract-ocr'
                    )
                logger.info(f"Created new page embedding for page {page_number}")
            except Exception as emb_error:
                logger.warning(f"Failed to generate embedding: {emb_error}")
                PageEmbedding.create(
                    paper=paper,
                    page_number=page_number,
                    page_text=selected_text,
                    vector_blob=None,
                    vector_dim=0,
                    model_name='tesseract-ocr'
                )
        
        result = {
            "success": True,
            "message": "Text updated successfully",
            "text_length": len(selected_text),
            "embedding_comparison": embedding_comparison
        }
        
        # If user wants to apply to entire document
        if apply_to_all:
            result["full_document_ocr_required"] = True
            
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to apply OCR result for {doc_id} page {page_number}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to apply OCR result: {str(e)}")


@router.post("/papers/{doc_id}/full-ocr")
async def full_document_ocr(
    doc_id: str,
    background_tasks: BackgroundTasks,
    user: AdminUser = Depends(require_auth)
):
    """Re-OCR entire document with Tesseract"""
    try:
        from models import Paper, PageEmbedding
        from ocr import process_pdf_with_ocr, detect_language_hybrid
        import os
        import asyncio
        
        # Get paper info
        try:
            paper = Paper.get(Paper.doc_id == doc_id)
        except Paper.DoesNotExist:
            raise HTTPException(status_code=404, detail=f"Paper not found: {doc_id}")
        
        pdf_path = paper.file_path
        if not os.path.exists(pdf_path):
            raise HTTPException(status_code=404, detail=f"PDF file not found: {pdf_path}")
        
        logger.info(f"Starting full document re-OCR for {doc_id}")
        
        # Create processing job for status tracking
        from models import ProcessingJob
        import uuid
        
        processing_job = ProcessingJob.create(
            job_id=str(uuid.uuid4()),
            paper=paper,
            filename=os.path.basename(pdf_path),
            status='processing',
            current_step='Starting full document ReOCR'
        )
        
        # Start background task using FastAPI BackgroundTasks
        background_tasks.add_task(process_full_document_ocr_task, paper, processing_job)
        
        return {
            "success": True,
            "message": "Full document OCR started in background",
            "doc_id": doc_id,
            "job_id": processing_job.job_id,
            "status": "processing"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start full document OCR for {doc_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start full document OCR: {str(e)}")


def process_full_document_ocr_task(paper, processing_job=None):
    """Background task for full document OCR processing with PDF text layer regeneration"""
    try:
        # Ensure database connection for background task
        if db.is_closed():
            db.connect()
            logger.info("Database connection opened for background task")
        
        if processing_job:
            processing_job.started_at = datetime.now()
            processing_job.save()
        from ocr import (extract_page_texts_from_pdf, perform_page_ocr_with_tesseract, 
                        detect_language_hybrid, regenerate_pdf_text_layer)
        from models import PageEmbedding
        from embedding import generate_text_embedding
        import os
        import tempfile
        
        pdf_path = paper.file_path
        logger.info(f"Processing full document OCR for {paper.doc_id}")
        logger.info(f"PDF path: {pdf_path}")
        
        # Verify PDF file exists
        if not os.path.exists(pdf_path):
            logger.error(f"PDF file not found at {pdf_path} for paper {paper.doc_id}")
            raise Exception(f"PDF file not found: {pdf_path}")
        
        # Update progress
        if processing_job:
            processing_job.current_step = 'Detecting language'
            processing_job.progress_percentage = 5
            processing_job.save()
        
        # Detect language
        tesseract_lang = detect_language_hybrid(pdf_path)
        logger.info(f"Detected language: {tesseract_lang} for full document OCR")
        
        # Get total pages
        page_texts, total_pages = extract_page_texts_from_pdf(pdf_path)
        
        # Step 1: Process individual pages for database updates
        logger.info("Step 1: Processing individual pages...")
        if processing_job:
            processing_job.current_step = f'Processing pages (0/{total_pages})'
            processing_job.progress_percentage = 10
            processing_job.save()
        
        successful_pages = 0
        
        for page_num in range(1, total_pages + 1):
            try:
                # Perform OCR on each page
                extracted_text, confidence = perform_page_ocr_with_tesseract(
                    pdf_path, page_num, tesseract_lang
                )
                
                if extracted_text:
                    # Update or create page embedding
                    try:
                        page_embedding = PageEmbedding.get(
                            (PageEmbedding.paper == paper) & 
                            (PageEmbedding.page_number == page_num)
                        )
                        page_embedding.page_text = extracted_text
                        page_embedding.save()
                    except PageEmbedding.DoesNotExist:
                        # Generate embedding
                        try:
                            embedding_vector = generate_text_embedding(extracted_text)
                            if embedding_vector is not None:
                                import numpy as np
                                vector_array = np.array(embedding_vector, dtype=np.float32)
                                PageEmbedding.create(
                                    paper=paper,
                                    page_number=page_num,
                                    page_text=extracted_text,
                                    vector_blob=vector_array.tobytes(),
                                    vector_dim=len(embedding_vector),
                                    model_name='bge-m3'
                                )
                            else:
                                PageEmbedding.create(
                                    paper=paper,
                                    page_number=page_num,
                                    page_text=extracted_text,
                                    vector_blob=None,
                                    vector_dim=0,
                                    model_name='tesseract-ocr'
                                )
                        except Exception as emb_error:
                            logger.warning(f"Failed to generate embedding for page {page_num}: {emb_error}")
                            PageEmbedding.create(
                                paper=paper,
                                page_number=page_num,
                                page_text=extracted_text,
                                vector_blob=None,
                                vector_dim=0,
                                model_name='tesseract-ocr'
                            )
                    
                    successful_pages += 1
                    logger.info(f"Processed page {page_num}/{total_pages}")
                    
                    # Update progress
                    if processing_job:
                        progress = 10 + (page_num / total_pages) * 50  # Pages take 50% of progress (10-60%)
                        processing_job.current_step = f'Processing pages ({page_num}/{total_pages})'
                        processing_job.progress_percentage = int(progress)
                        processing_job.save()
                    
            except Exception as page_error:
                logger.error(f"Error processing page {page_num}: {page_error}")
                continue
        
        # Step 2: Regenerate PDF text layer if most pages were successful
        success_rate = successful_pages / total_pages if total_pages > 0 else 0
        logger.info(f"Page processing success rate: {success_rate:.2%} ({successful_pages}/{total_pages})")
        
        if success_rate >= 0.7:  # If 70% or more pages were successful
            logger.info("Step 2: Regenerating PDF text layer with ocrmypdf...")
            if processing_job:
                processing_job.current_step = 'Regenerating PDF text layer'
                processing_job.progress_percentage = 65
                processing_job.save()
            
            # Create temporary path for new PDF
            pdf_dir = os.path.dirname(pdf_path)
            pdf_filename = os.path.basename(pdf_path)
            temp_pdf_path = os.path.join(pdf_dir, f"temp_ocr_{pdf_filename}")
            
            try:
                # Regenerate PDF text layer
                result = regenerate_pdf_text_layer(
                    input_pdf_path=pdf_path,
                    output_pdf_path=temp_pdf_path,
                    language=tesseract_lang,
                    backup_original=True
                )
                
                if result['success']:
                    # Replace original PDF with new one
                    import shutil
                    shutil.move(temp_pdf_path, pdf_path)
                    
                    logger.info(f"PDF text layer regenerated successfully for {paper.doc_id}")
                    logger.info(f"Original PDF backed up to: {result['backup_path']}")
                    
                    # Refresh paper object from database to avoid stale data
                    paper = Paper.get_by_id(paper.id)
                    
                    # Update paper record to indicate text layer was regenerated
                    paper.processing_notes = (paper.processing_notes or '') + f"\nText layer regenerated with Tesseract ({tesseract_lang}) on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    paper.original_file_path = result['backup_path']
                    paper.ocr_regenerated = True
                    paper.save()
                    logger.info(f"Paper record updated for {paper.doc_id}")
                    
                else:
                    logger.error(f"Failed to regenerate PDF text layer: {result['error']}")
                    
            except Exception as pdf_error:
                logger.error(f"Error during PDF text layer regeneration: {pdf_error}")
                # Clean up temp file if it exists
                if os.path.exists(temp_pdf_path):
                    os.unlink(temp_pdf_path)
        else:
            logger.warning(f"Skipping PDF text layer regeneration due to low success rate: {success_rate:.2%}")
        
        # Step 3: Update document-level embedding with combined text from all pages
        logger.info("Step 3: Updating document-level embedding...")
        if processing_job:
            processing_job.current_step = 'Updating document embedding'
            processing_job.progress_percentage = 80
            processing_job.save()
        try:
            from models import Embedding
            from embedding import generate_text_embedding
            
            # Collect all page texts
            page_embeddings = PageEmbedding.select().where(
                PageEmbedding.paper == paper
            ).order_by(PageEmbedding.page_number)
            
            combined_text = ""
            first_pages_text = ""  # For metadata extraction
            for i, page_emb in enumerate(page_embeddings):
                if page_emb.page_text:
                    combined_text += page_emb.page_text + "\n\n"
                    # Collect first 2 pages for metadata extraction
                    if i < 2:
                        first_pages_text += page_emb.page_text + "\n\n"
            
            if combined_text.strip():
                # Generate document-level embedding
                doc_embedding_vector = generate_text_embedding(combined_text.strip())
                
                if doc_embedding_vector is not None:
                    import numpy as np
                    vector_array = np.array(doc_embedding_vector, dtype=np.float32)
                    
                    # Update or create document embedding
                    try:
                        doc_embedding = Embedding.get(Embedding.paper == paper)
                        doc_embedding.vector_blob = vector_array.tobytes()
                        doc_embedding.vector_dim = len(doc_embedding_vector)
                        doc_embedding.model_name = 'bge-m3'
                        doc_embedding.updated_at = datetime.now()
                        doc_embedding.save()
                        logger.info(f"Updated document-level embedding for {paper.doc_id}")
                    except Embedding.DoesNotExist:
                        Embedding.create(
                            paper=paper,
                            vector_blob=vector_array.tobytes(),
                            vector_dim=len(doc_embedding_vector),
                            model_name='bge-m3'
                        )
                        logger.info(f"Created new document-level embedding for {paper.doc_id}")
                else:
                    logger.warning(f"Failed to generate document-level embedding for {paper.doc_id}")
            else:
                logger.warning(f"No text available for document-level embedding for {paper.doc_id}")
                
        except Exception as emb_error:
            logger.error(f"Failed to update document-level embedding for {paper.doc_id}: {emb_error}")
        
        # Step 4: Re-extract metadata from improved OCR text
        logger.info("Step 4: Re-extracting paper metadata from improved OCR text...")
        if processing_job:
            processing_job.current_step = 'Re-extracting metadata'
            processing_job.progress_percentage = 90
            processing_job.save()
        try:
            from metadata import extract_paper_metadata
            from models import Metadata
            from ocr import extract_first_pages_with_formatting
            
            # Try to get formatted text with font sizes first
            formatted_text = None
            try:
                formatted_text = extract_first_pages_with_formatting(pdf_path, num_pages=2)
                if formatted_text:
                    logger.info("Using formatted text with font size information for metadata extraction")
            except Exception as fmt_error:
                logger.warning(f"Failed to extract formatted text: {fmt_error}")
            
            # Use formatted text if available, otherwise use plain text
            if formatted_text and formatted_text.strip():
                metadata_text = formatted_text
                logger.info(f"Metadata extraction will use {len(metadata_text)} chars of formatted text")
            else:
                # Fallback to plain text from first pages
                metadata_text = first_pages_text.strip() if first_pages_text.strip() else combined_text.strip()
                logger.info(f"Metadata extraction will use {len(metadata_text)} chars of plain text")
            
            if metadata_text:
                # Extract metadata using the formatted or plain text
                metadata_info, success = extract_paper_metadata(metadata_text)
                
                if success and metadata_info:
                    
                    # Update or create metadata record
                    try:
                        metadata_record = Metadata.get(Metadata.paper == paper)
                        
                        # Update with new extracted information
                        if metadata_info.get('title'):
                            metadata_record.title = metadata_info['title']
                        if metadata_info.get('authors'):
                            metadata_record.authors = metadata_info['authors']
                        if metadata_info.get('abstract'):
                            metadata_record.abstract = metadata_info['abstract']
                        if metadata_info.get('keywords'):
                            metadata_record.keywords = metadata_info['keywords']
                        if metadata_info.get('doi'):
                            metadata_record.doi = metadata_info['doi']
                        if metadata_info.get('journal'):
                            metadata_record.journal = metadata_info['journal']
                        if metadata_info.get('year'):
                            metadata_record.year = metadata_info['year']
                        if metadata_info.get('volume'):
                            metadata_record.volume = metadata_info['volume']
                        if metadata_info.get('issue'):
                            metadata_record.issue = metadata_info['issue']
                        if metadata_info.get('pages'):
                            metadata_record.pages = metadata_info['pages']
                        
                        # Update extraction info
                        metadata_record.extraction_method = 'tesseract_reocr'
                        metadata_record.confidence_score = metadata_info.get('confidence_score', 0.8)  # Default confidence for ReOCR
                        metadata_record.updated_at = datetime.now()
                        metadata_record.save()
                        
                        logger.info(f"Updated metadata for {paper.doc_id} with ReOCR results")
                        logger.info(f"Extracted title: {metadata_info.get('title', 'N/A')[:100]}")
                        logger.info(f"Extracted authors: {metadata_info.get('authors', 'N/A')[:100]}")
                        logger.info(f"Metadata extraction used {len(metadata_text)} chars from {'first 2 pages' if first_pages_text.strip() else 'all pages'}")
                        
                    except Metadata.DoesNotExist:
                        # Create new metadata record
                        Metadata.create(
                            paper=paper,
                            title=metadata_info.get('title', ''),
                            authors=metadata_info.get('authors', ''),
                            abstract=metadata_info.get('abstract', ''),
                            keywords=metadata_info.get('keywords', ''),
                            doi=metadata_info.get('doi', ''),
                            journal=metadata_info.get('journal', ''),
                            year=metadata_info.get('year'),
                            volume=metadata_info.get('volume', ''),
                            issue=metadata_info.get('issue', ''),
                            pages=metadata_info.get('pages', ''),
                            extraction_method='tesseract_reocr',
                            confidence_score=metadata_info.get('confidence_score', 0.8)  # Default confidence for ReOCR
                        )
                        logger.info(f"Created new metadata for {paper.doc_id} with ReOCR results")
                else:
                    logger.warning(f"Failed to extract metadata from ReOCR text for {paper.doc_id}")
                    logger.info(f"Metadata extraction used {len(metadata_text)} chars from {'first pages' if first_pages_text.strip() else 'all pages'}")
            else:
                logger.warning(f"No text available for metadata extraction for {paper.doc_id}")
                
        except Exception as meta_error:
            logger.error(f"Failed to re-extract metadata for {paper.doc_id}: {meta_error}")
        
        logger.info(f"Full document OCR completed for {paper.doc_id}")
        
        # Mark job as completed
        if processing_job:
            processing_job.status = 'completed'
            processing_job.current_step = 'Completed'
            processing_job.progress_percentage = 100
            processing_job.completed_at = datetime.now()
            processing_job.add_completed_step('full_document_ocr', {
                'pages_processed': successful_pages,
                'total_pages': total_pages,
                'success_rate': f"{success_rate:.2%}"
            })
            processing_job.save()
        
    except Exception as e:
        logger.error(f"Full document OCR task failed for {paper.doc_id}: {e}")
        
        # Mark job as failed
        if processing_job:
            processing_job.status = 'failed'
            processing_job.current_step = 'Failed'
            processing_job.error_message = str(e)
            processing_job.completed_at = datetime.now()
            processing_job.add_failed_step('full_document_ocr', str(e))
            processing_job.save()


@router.get("/ocr-status", response_class=HTMLResponse)
async def admin_ocr_status(
    request: Request,
    user: AdminUser = Depends(require_auth)
):
    """OCR processing status dashboard"""
    try:
        from models import Paper, PageEmbedding
        from peewee import fn
        
        # Get papers with processing notes
        papers_with_notes = (Paper
                           .select()
                           .where(Paper.processing_notes.is_null(False))
                           .order_by(Paper.updated_at.desc())
                           .limit(20))
        
        # Get OCR completion statistics
        total_papers = Paper.select().count()
        papers_with_text_layer = (Paper
                                .select()
                                .where(Paper.processing_notes.contains('Text layer regenerated'))
                                .count())
        
        # Get recent OCR activities
        recent_activities = []
        for paper in papers_with_notes:
            if paper.processing_notes:
                lines = paper.processing_notes.strip().split('\n')
                for line in lines:
                    if 'Text layer regenerated' in line:
                        recent_activities.append({
                            'paper': paper,
                            'activity': line.strip(),
                            'timestamp': paper.updated_at
                        })
        
        # Sort by timestamp
        recent_activities.sort(key=lambda x: x['timestamp'], reverse=True)
        recent_activities = recent_activities[:10]
        
        # Get page-level OCR statistics
        page_stats = (PageEmbedding
                     .select(PageEmbedding.model_name, fn.COUNT(PageEmbedding.id).alias('count'))
                     .group_by(PageEmbedding.model_name))
        
        ocr_stats = {
            'total_papers': total_papers,
            'papers_with_regenerated_text_layer': papers_with_text_layer,
            'regeneration_percentage': (papers_with_text_layer / total_papers * 100) if total_papers > 0 else 0,
            'page_model_distribution': {stat.model_name: stat.count for stat in page_stats}
        }
        
        return templates.TemplateResponse(
            "ocr_status.html",
            {
                "request": request,
                "user": user,
                "papers_with_notes": list(papers_with_notes),
                "recent_activities": recent_activities,
                "ocr_stats": ocr_stats,
                "version": get_version()
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to load OCR status dashboard: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load OCR status: {str(e)}")


@router.get("/download-original/{doc_id}")
async def download_original_pdf(
    doc_id: str,
    user: AdminUser = Depends(require_auth)
):
    """Download original PDF before OCR regeneration"""
    try:
        from models import Paper
        from fastapi.responses import FileResponse
        import os
        
        # Get paper info
        try:
            paper = Paper.get(Paper.doc_id == doc_id)
        except Paper.DoesNotExist:
            raise HTTPException(status_code=404, detail=f"Paper not found: {doc_id}")
        
        # Check if original file exists
        if not paper.original_file_path:
            raise HTTPException(status_code=404, detail="No original file backup available")
        
        if not os.path.exists(paper.original_file_path):
            raise HTTPException(status_code=404, detail="Original file not found on disk")
        
        # Return file
        return FileResponse(
            paper.original_file_path,
            media_type='application/pdf',
            filename=f"original_{paper.filename}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download original PDF for {doc_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to download original PDF: {str(e)}")






# Pending GPU Tasks Management
@router.get("/pending-tasks", response_class=HTMLResponse)
async def admin_pending_tasks(
    request: Request,
    user: AdminUser = Depends(require_auth)
):
    """Display pending GPU-intensive tasks"""
    try:
        # Check GPU mode status
        gpu_mode_enabled = os.environ.get('ENABLE_GPU_INTENSIVE_TASKS', 'true').lower() != 'false'
        
        # Check service availability
        from ocr_quality import is_quality_assessment_available
        from layout import is_layout_service_available
        from metadata import is_metadata_service_available
        from gpu_monitor import get_gpu_monitor
        
        services = {
            'llava': is_quality_assessment_available(),
            'layout': is_layout_service_available(),
            'llm': is_metadata_service_available()
        }
        
        # Get GPU and Ollama status
        gpu_monitor = get_gpu_monitor()
        gpu_status = gpu_monitor.get_comprehensive_status()
        
        # Count pending tasks
        pending_counts = {
            'ocr_quality': Paper.select().where(
                (Paper.ocr_quality_completed == False) | 
                (Paper.ocr_quality.is_null(True))
            ).count(),
            'layout': Paper.select().where(Paper.layout_completed == False).count(),
            'metadata_llm': Paper.select().where(
                (Paper.metadata_llm_completed == False) &
                (Paper.ocr_text.is_null(False)) &
                (Paper.ocr_text != '')
            ).count()
        }
        
        # Get papers with any pending tasks
        papers_with_pending = Paper.select().where(
            (Paper.ocr_quality_completed == False) |
            (Paper.layout_completed == False) |
            (Paper.metadata_llm_completed == False)
        ).order_by(Paper.created_at.desc()).limit(50)
        
        return templates.TemplateResponse("pending_tasks.html", {
            "request": request,
            "user": user,
            "gpu_mode_enabled": gpu_mode_enabled,
            "services": services,
            "pending_counts": pending_counts,
            "papers_with_pending": papers_with_pending,
            "gpu_status": gpu_status,
            "version": get_version()
        })
        
    except Exception as e:
        logger.error(f"Error displaying pending tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pending-tasks/process")
async def process_pending_tasks(
    request: Request,
    user: AdminUser = Depends(require_auth)
):
    """Process pending GPU tasks"""
    try:
        data = await request.json()
        task_type = data.get('task_type', 'all')
        
        # Import batch processing functions
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
        from batch_process_pending import (
            process_pending_ocr_quality,
            process_pending_layout,
            process_pending_metadata_llm,
            process_ollama_tasks,
            process_non_ollama_tasks,
            process_sequential
        )
        
        total_processed = 0
        total_failed = 0
        
        if task_type == 'sequential':
            # Smart sequential processing (recommended)
            total_processed, total_failed = process_sequential()
        elif task_type == 'ollama-tasks':
            # Process Ollama-dependent tasks
            total_processed, total_failed = process_ollama_tasks()
        elif task_type == 'non-ollama-tasks':
            # Process non-Ollama tasks
            total_processed, total_failed = process_non_ollama_tasks()
        elif task_type == 'ocr_quality':
            processed, failed = process_pending_ocr_quality()
            total_processed += processed
            total_failed += failed
        elif task_type == 'layout':
            processed, failed = process_pending_layout()
            total_processed += processed
            total_failed += failed
        elif task_type == 'metadata_llm':
            processed, failed = process_pending_metadata_llm()
            total_processed += processed
            total_failed += failed
        elif task_type == 'all':
            # Legacy all processing (may cause GPU memory issues)
            processed, failed = process_pending_ocr_quality()
            total_processed += processed
            total_failed += failed
            
            processed, failed = process_pending_layout()
            total_processed += processed
            total_failed += failed
            
            processed, failed = process_pending_metadata_llm()
            total_processed += processed
            total_failed += failed
        
        return {
            "success": True,
            "processed": total_processed,
            "failed": total_failed
        }
        
    except Exception as e:
        logger.error(f"Error processing pending tasks: {e}")
        return {"success": False, "error": str(e)}


@router.post("/pending-tasks/process-single")
async def process_single_paper_pending(
    request: Request,
    user: AdminUser = Depends(require_auth)
):
    """Process pending tasks for a single paper"""
    try:
        data = await request.json()
        doc_id = data.get('doc_id')
        
        if not doc_id:
            return {"success": False, "error": "No doc_id provided"}
        
        paper = Paper.get_or_none(Paper.doc_id == doc_id)
        if not paper:
            return {"success": False, "error": "Paper not found"}
        
        # Import processing functions
        from ocr_quality import assess_document_quality
        from layout import analyze_pdf_layout
        from metadata import extract_paper_metadata
        from db import save_layout_analysis, save_metadata
        from pdf2image import convert_from_path
        import tempfile
        
        tasks_processed = []
        
        # Process OCR quality if pending
        if not paper.ocr_quality_completed:
            try:
                with tempfile.TemporaryDirectory() as temp_dir:
                    images = convert_from_path(paper.file_path, first_page=1, last_page=1, dpi=200)
                    if images:
                        first_page_path = os.path.join(temp_dir, "first_page.png")
                        images[0].save(first_page_path, "PNG")
                        quality_summary, _ = assess_document_quality(first_page_path)
                        paper.ocr_quality = quality_summary
                        paper.ocr_quality_completed = True
                        paper.save()
                        tasks_processed.append("ocr_quality")
            except Exception as e:
                logger.error(f"Error processing OCR quality: {e}")
        
        # Process layout if pending
        if not paper.layout_completed:
            try:
                layout_data, layout_success = analyze_pdf_layout(paper.file_path)
                if layout_success:
                    page_count = layout_data.get('page_count', 0)
                    save_layout_analysis(paper.doc_id, layout_data, page_count)
                    paper.layout_completed = True
                    paper.save()
                    tasks_processed.append("layout")
            except Exception as e:
                logger.error(f"Error processing layout: {e}")
        
        # Process metadata if pending
        if not paper.metadata_llm_completed and paper.ocr_text:
            try:
                metadata, metadata_success = extract_paper_metadata(paper.ocr_text)
                if metadata_success and metadata.get('extraction_method') in ['structured_llm', 'simple_llm']:
                    save_metadata(
                        paper.doc_id,
                        title=metadata.get('title'),
                        authors=metadata.get('authors'),
                        journal=metadata.get('journal'),
                        year=metadata.get('year'),
                        doi=metadata.get('doi'),
                        abstract=metadata.get('abstract'),
                        keywords=metadata.get('keywords')
                    )
                    paper.metadata_llm_completed = True
                    paper.save()
                    tasks_processed.append("metadata_llm")
            except Exception as e:
                logger.error(f"Error processing metadata: {e}")
        
        return {
            "success": True,
            "tasks_processed": tasks_processed
        }
        
    except Exception as e:
        logger.error(f"Error processing single paper: {e}")
        return {"success": False, "error": str(e)}


@router.get("/gpu-status")
async def get_gpu_status(
    user: AdminUser = Depends(require_auth)
):
    """Get real-time GPU and Ollama status"""
    try:
        from gpu_monitor import get_gpu_monitor
        
        gpu_monitor = get_gpu_monitor()
        gpu_status = gpu_monitor.get_comprehensive_status()
        
        return {
            "success": True,
            "gpu_status": gpu_status,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting GPU status: {e}")
        return {"success": False, "error": str(e)}


# Root redirect
@router.get("/", response_class=HTMLResponse)
async def admin_root(request: Request):
    """Redirect to dashboard or login"""
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/admin/dashboard", status_code=302)
    else:
        return RedirectResponse(url="/admin/login", status_code=302)