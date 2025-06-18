import os
import logging
from fastapi import FastAPI
from fastapi_admin.app import app as admin_app
from fastapi_admin.providers.login import UsernamePasswordProvider
from fastapi_admin.resources import Model, Field, Display
from fastapi_admin.widgets import displays, filters, inputs
from starlette.middleware.sessions import SessionMiddleware

# Import models and auth
from models import Paper, PageEmbedding, Embedding, Metadata, LayoutAnalysis, AdminUser
from auth import AuthManager, get_current_user_from_session

logger = logging.getLogger(__name__)

# Admin configuration
ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "your-secret-key-change-in-production")

def setup_admin(app: FastAPI):
    """Setup FastAPI Admin for RefServer"""
    
    # Ensure default admin user exists
    AuthManager.ensure_default_admin()
    
    # Add session middleware for admin authentication
    app.add_middleware(SessionMiddleware, secret_key=ADMIN_SECRET_KEY)
    
    # Admin login provider
    admin_app.add_provider(
        UsernamePasswordProvider(
            admin_secret="admin",
            login_logo_url="https://preview.tabler.io/static/logo.svg",
        )
    )
    
    # Configure admin resources
    setup_admin_resources()
    
    # Mount admin app
    app.mount("/admin", admin_app)
    
    logger.info("FastAPI Admin mounted at /admin")
    logger.info("Default admin credentials: admin/admin123 (change after first login)")
    return app

def setup_admin_resources():
    """Configure admin resources for each model"""
    
    # Admin User Resource
    @admin_app.register
    class AdminUserResource(Model):
        label = "Admin Users"
        model = AdminUser
        icon = "fas fa-users-cog"
        page_size = 20
        
        fields = [
            Field(
                name="username",
                label="Username",
                display=Display(displays.InputOnly()),
                input_=inputs.Input(),
            ),
            Field(
                name="email",
                label="Email",
                display=Display(displays.InputOnly()),
                input_=inputs.Email(),
            ),
            Field(
                name="full_name",
                label="Full Name",
                display=Display(displays.InputOnly()),
                input_=inputs.Input(),
            ),
            Field(
                name="is_active",
                label="Active",
                display=Display(displays.Boolean()),
                input_=inputs.Switch(),
            ),
            Field(
                name="is_superuser",
                label="Superuser",
                display=Display(displays.Boolean()),
                input_=inputs.Switch(),
            ),
            Field(
                name="last_login",
                label="Last Login",
                display=Display(displays.DatetimeDisplay()),
                input_=inputs.DateTimeInput(readonly=True),
            ),
            Field(
                name="created_at",
                label="Created At",
                display=Display(displays.DatetimeDisplay()),
                input_=inputs.DateTimeInput(readonly=True),
            ),
        ]
        
        filters = [
            filters.Search(name="username", label="Username", search_mode="contains"),
            filters.Search(name="email", label="Email", search_mode="contains"),
            filters.Boolean(name="is_active", label="Active"),
            filters.Boolean(name="is_superuser", label="Superuser"),
        ]
    
    # Paper Resource
    @admin_app.register
    class PaperResource(Model):
        label = "Papers"
        model = Paper
        icon = "fas fa-file-pdf"
        page_size = 20
        page_size_options = [10, 20, 50, 100]
        
        # Fields configuration
        fields = [
            Field(
                name="doc_id",
                label="Document ID",
                display=Display(displays.InputOnly()),
                input_=inputs.Input(),
            ),
            Field(
                name="filename",
                label="Filename",
                display=Display(displays.InputOnly()),
                input_=inputs.Input(),
            ),
            Field(
                name="content_id",
                label="Content ID",
                display=Display(displays.InputOnly()),
                input_=inputs.Input(readonly=True),
            ),
            Field(
                name="ocr_quality",
                label="OCR Quality",
                display=Display(displays.InputOnly()),
                input_=inputs.Select(
                    options=[
                        ("good", "Good"),
                        ("fair", "Fair"), 
                        ("poor", "Poor"),
                        ("needs_ocr", "Needs OCR"),
                    ]
                ),
            ),
            Field(
                name="created_at",
                label="Created At",
                display=Display(displays.DatetimeDisplay()),
                input_=inputs.DateTimeInput(readonly=True),
            ),
            Field(
                name="updated_at", 
                label="Updated At",
                display=Display(displays.DatetimeDisplay()),
                input_=inputs.DateTimeInput(readonly=True),
            ),
        ]
        
        # Filters
        filters = [
            filters.Search(
                name="filename", 
                label="Filename",
                search_mode="contains",
            ),
            filters.Search(
                name="ocr_quality",
                label="OCR Quality", 
                search_mode="exact",
            ),
            filters.Date(name="created_at", label="Created Date"),
        ]
    
    # Metadata Resource  
    @admin_app.register
    class MetadataResource(Model):
        label = "Metadata"
        model = Metadata
        icon = "fas fa-tags"
        page_size = 20
        
        fields = [
            Field(
                name="paper",
                label="Paper",
                display=Display(displays.InputOnly()),
                input_=inputs.ForeignKey(Metadata.paper),
            ),
            Field(
                name="title",
                label="Title",
                display=Display(displays.InputOnly()),
                input_=inputs.TextArea(),
            ),
            Field(
                name="authors",
                label="Authors", 
                display=Display(displays.InputOnly()),
                input_=inputs.TextArea(),
            ),
            Field(
                name="journal",
                label="Journal",
                display=Display(displays.InputOnly()),
                input_=inputs.Input(),
            ),
            Field(
                name="year",
                label="Year",
                display=Display(displays.InputOnly()), 
                input_=inputs.Number(),
            ),
            Field(
                name="doi",
                label="DOI",
                display=Display(displays.InputOnly()),
                input_=inputs.Input(),
            ),
            Field(
                name="abstract",
                label="Abstract",
                display=Display(displays.InputOnly()),
                input_=inputs.TextArea(),
            ),
        ]
        
        filters = [
            filters.Search(name="title", label="Title", search_mode="contains"),
            filters.Search(name="journal", label="Journal", search_mode="contains"),
            filters.Search(name="year", label="Year", search_mode="exact"),
        ]
    
    # Page Embedding Resource
    @admin_app.register  
    class PageEmbeddingResource(Model):
        label = "Page Embeddings"
        model = PageEmbedding
        icon = "fas fa-vector-square"
        page_size = 50
        
        fields = [
            Field(
                name="paper",
                label="Paper",
                display=Display(displays.InputOnly()),
                input_=inputs.ForeignKey(PageEmbedding.paper),
            ),
            Field(
                name="page_number",
                label="Page Number",
                display=Display(displays.InputOnly()),
                input_=inputs.Number(),
            ),
            Field(
                name="vector_dim",
                label="Vector Dimension",
                display=Display(displays.InputOnly()),
                input_=inputs.Number(readonly=True),
            ),
            Field(
                name="model_name",
                label="Model Name", 
                display=Display(displays.InputOnly()),
                input_=inputs.Input(readonly=True),
            ),
            Field(
                name="created_at",
                label="Created At",
                display=Display(displays.DatetimeDisplay()),
                input_=inputs.DateTimeInput(readonly=True),
            ),
        ]
        
        filters = [
            filters.Search(name="model_name", label="Model", search_mode="exact"),
            filters.Search(name="page_number", label="Page Number", search_mode="exact"),
        ]
    
    # Document Embedding Resource
    @admin_app.register
    class EmbeddingResource(Model):
        label = "Document Embeddings" 
        model = Embedding
        icon = "fas fa-project-diagram"
        page_size = 20
        
        fields = [
            Field(
                name="paper",
                label="Paper", 
                display=Display(displays.InputOnly()),
                input_=inputs.ForeignKey(Embedding.paper),
            ),
            Field(
                name="vector_dim",
                label="Vector Dimension",
                display=Display(displays.InputOnly()),
                input_=inputs.Number(readonly=True),
            ),
            Field(
                name="model_name",
                label="Model Name",
                display=Display(displays.InputOnly()), 
                input_=inputs.Input(readonly=True),
            ),
            Field(
                name="created_at",
                label="Created At",
                display=Display(displays.DatetimeDisplay()),
                input_=inputs.DateTimeInput(readonly=True),
            ),
        ]
    
    # Layout Analysis Resource
    @admin_app.register
    class LayoutAnalysisResource(Model):
        label = "Layout Analysis"
        model = LayoutAnalysis  
        icon = "fas fa-th-large"
        page_size = 20
        
        fields = [
            Field(
                name="paper",
                label="Paper",
                display=Display(displays.InputOnly()),
                input_=inputs.ForeignKey(LayoutAnalysis.paper), 
            ),
            Field(
                name="page_count",
                label="Page Count",
                display=Display(displays.InputOnly()),
                input_=inputs.Number(readonly=True),
            ),
            Field(
                name="created_at", 
                label="Created At",
                display=Display(displays.DatetimeDisplay()),
                input_=inputs.DateTimeInput(readonly=True),
            ),
        ]

async def authenticate_admin(username: str, password: str):
    """DB-based admin authentication function"""
    user = AuthManager.authenticate_user(username, password)
    if user:
        return {
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "is_superuser": user.is_superuser
        }
    return None

# Configure admin login provider
@admin_app.post("/login")
async def login(request):
    """Admin login endpoint"""
    form = await request.form()
    username = form.get("username")
    password = form.get("password")
    
    user = await authenticate_admin(username, password)
    if user:
        request.session["user"] = user
        logger.info(f"Admin user {username} logged in successfully")
        return {"success": True}
    
    logger.warning(f"Failed login attempt for username: {username}")
    return {"success": False, "message": "Invalid username or password"}

@admin_app.post("/logout")
async def logout(request):
    """Admin logout endpoint"""
    user_data = request.session.get("user")
    if user_data:
        logger.info(f"Admin user {user_data.get('username')} logged out")
    request.session.pop("user", None)
    return {"success": True}