# RefServer Admin Interface
# Jinja2-based administration panel for managing PDF papers

from fastapi import APIRouter, Request, Form, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import os

from models import Paper, Metadata, Embedding, LayoutAnalysis, AdminUser, PageEmbedding
from auth import AuthManager
from db import get_paper_by_id, db


# Initialize router and templates
router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")
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
        total_papers = Paper.select().count()
        papers_with_metadata = Paper.select().join(Metadata, join_type='INNER').count()
        papers_with_embeddings = Paper.select().join(Embedding, join_type='INNER').count()
        papers_with_layout = Paper.select().join(LayoutAnalysis, join_type='INNER').count()
        
        # Calculate processing rates
        metadata_rate = (papers_with_metadata / total_papers * 100) if total_papers > 0 else 0
        embedding_rate = (papers_with_embeddings / total_papers * 100) if total_papers > 0 else 0
        layout_rate = (papers_with_layout / total_papers * 100) if total_papers > 0 else 0
        
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
            "processing_rates": {
                "metadata_rate": metadata_rate,
                "embedding_rate": embedding_rate,
                "layout_rate": layout_rate
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
            "processing_rates": {
                "metadata_rate": 0,
                "embedding_rate": 0,
                "layout_rate": 0
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


# Root redirect
@router.get("/", response_class=HTMLResponse)
async def admin_root(request: Request):
    """Redirect to dashboard or login"""
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/admin/dashboard", status_code=302)
    else:
        return RedirectResponse(url="/admin/login", status_code=302)