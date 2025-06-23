# RefServer Admin Interface
# Jinja2-based administration panel for managing PDF papers

from fastapi import APIRouter, Request, Form, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import os

from models import Paper, Metadata, Embedding, LayoutAnalysis, AdminUser, PageEmbedding
from auth import AuthManager
from db import get_paper_by_id, get_page_embeddings_by_id, db
from vector_db import get_vector_db
from duplicate_detector import get_duplicate_detector


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
        
        # Convert to list and add metadata
        papers_list = []
        for paper in papers:
            try:
                metadata = Metadata.get_or_none(Metadata.paper == paper)
                paper.metadata = metadata
                papers_list.append(paper)
            except Exception:
                paper.metadata = None
                papers_list.append(paper)
        
        return templates.TemplateResponse(
            "papers.html", 
            {
                "request": request, 
                "user": user, 
                "papers": papers_list
            }
        )
        
    except Exception as e:
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


@router.get("/page-embeddings", response_class=HTMLResponse)
async def page_embeddings_list(request: Request, search: Optional[str] = None):
    """Page embeddings management page"""
    user = require_auth(request)
    
    try:
        # Get statistics
        stats = get_stats()
        
        # Get papers with page embeddings
        if search:
            papers_query = (Paper
                          .select()
                          .where(
                              Paper.filename.contains(search) &
                              Paper.id.in_(PageEmbedding.select(PageEmbedding.paper))
                          )
                          .order_by(Paper.created_at.desc()))
        else:
            papers_query = (Paper
                          .select()
                          .where(Paper.id.in_(PageEmbedding.select(PageEmbedding.paper)))
                          .order_by(Paper.created_at.desc()))
        
        papers_list = []
        for paper in papers_query:
            # Get page embedding statistics for this paper
            page_embs = list(PageEmbedding.select().where(PageEmbedding.paper == paper))
            if page_embs:
                avg_vector_dim = page_embs[0].vector_dim  # All should be same
                model_name = page_embs[0].model_name
                paper.page_count = len(page_embs)
                paper.avg_vector_dim = avg_vector_dim
                paper.model_name = model_name
                papers_list.append(paper)
        
        return templates.TemplateResponse(
            "page_embeddings.html", 
            {
                "request": request, 
                "user": user, 
                "papers": papers_list,
                "stats": stats
            }
        )
        
    except Exception as e:
        return templates.TemplateResponse(
            "page_embeddings.html", 
            {
                "request": request, 
                "user": user, 
                "papers": [],
                "stats": get_stats(),
                "error": f"Error loading page embeddings: {str(e)}"
            }
        )


@router.get("/page-embeddings/{doc_id}", response_class=HTMLResponse)
async def page_embedding_detail(request: Request, doc_id: str):
    """Page embedding detail page"""
    user = require_auth(request)
    
    try:
        paper = get_paper_by_id(doc_id)
        if not paper:
            raise HTTPException(status_code=404, detail="Paper not found")
        
        # Get page embeddings for this paper
        page_embeddings = list(
            PageEmbedding
            .select()
            .where(PageEmbedding.paper == paper)
            .order_by(PageEmbedding.page_number)
        )
        
        return templates.TemplateResponse(
            "page_embedding_detail.html", 
            {
                "request": request, 
                "user": user, 
                "paper": paper,
                "page_embeddings": page_embeddings
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading page embedding detail: {str(e)}")


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
        papers_with_embeddings = (Paper
                                .select(Paper.id)
                                .join(Embedding, on=(Paper.id == Embedding.paper))
                                .group_by(Paper.id)
                                .count())
        papers_with_page_embeddings = (Paper
                                     .select(Paper.id)
                                     .join(PageEmbedding, on=(Paper.id == PageEmbedding.paper))
                                     .group_by(Paper.id)
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
                "version": "v0.1.10"
            }
        )
        
    except Exception as e:
        return templates.TemplateResponse(
            "vector_db_monitoring.html", 
            {
                "request": request, 
                "user": user,
                "error": f"Error loading ChromaDB statistics: {str(e)}",
                "version": "v0.1.10"
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
                "version": "v0.1.10"
            }
        )
        
    except Exception as e:
        return templates.TemplateResponse(
            "duplicate_prevention_monitoring.html",
            {
                "request": request,
                "user": user,
                "error": f"Error loading duplicate prevention statistics: {str(e)}",
                "version": "v0.1.10"
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
                "version": "v0.1.10"
            }
        )
        
    except Exception as e:
        return templates.TemplateResponse(
            "scheduler_management.html",
            {
                "request": request,
                "user": user,
                "error": f"Error loading scheduler management: {str(e)}",
                "version": "v0.1.10"
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
                "version": "v0.1.12"
            }
        )
        
    except Exception as e:
        return templates.TemplateResponse(
            "backup_management.html",
            {
                "request": request,
                "user": user,
                "error": f"Error loading backup management: {str(e)}",
                "version": "v0.1.12"
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
                "version": "v0.1.12"
            }
        )
        
    except Exception as e:
        return templates.TemplateResponse(
            "consistency_management.html",
            {
                "request": request,
                "user": user,
                "error": f"Error loading consistency management: {str(e)}",
                "version": "v0.1.12"
            }
        )


# Root redirect
@router.get("/", response_class=HTMLResponse)
async def admin_root(request: Request):
    """Redirect to dashboard or login"""
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/admin/dashboard", status_code=302)
    else:
        return RedirectResponse(url="/admin/login", status_code=302)