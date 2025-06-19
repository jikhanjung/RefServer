from peewee import *
import datetime
import json
import hashlib
import numpy as np
import logging
import os

# Initialize logger
logger = logging.getLogger("RefServerModels")

# Database setup
DATABASE_PATH = os.path.join('/data', 'refserver.db')
db = SqliteDatabase(DATABASE_PATH, pragmas={'foreign_keys': 1})

class BaseModel(Model):
    class Meta:
        database = db

class Paper(BaseModel):
    """Model for storing PDF paper information"""
    doc_id = CharField(primary_key=True)  # UUID4 unique identifier
    content_id = CharField(unique=True, null=True)  # Content-based SHA-256 hash for deduplication
    filename = CharField()  # Original filename
    file_path = CharField()  # Stored file path
    ocr_text = TextField(null=True)  # Extracted text content
    ocr_quality = CharField(null=True)  # LLaVA quality assessment result
    created_at = DateTimeField(default=datetime.datetime.now)
    updated_at = DateTimeField(default=datetime.datetime.now)
    
    class Meta:
        indexes = (
            (('content_id',), False),
        )


class ProcessingJob(BaseModel):
    """Model for tracking PDF processing job status"""
    job_id = CharField(primary_key=True)  # UUID4 job identifier
    paper = ForeignKeyField(Paper, backref='processing_jobs', null=True, on_delete='CASCADE')
    filename = CharField()  # Original filename
    status = CharField(default='uploaded')  # uploaded, processing, completed, failed
    current_step = CharField(null=True)  # Current processing step
    progress_percentage = IntegerField(default=0)  # Progress 0-100
    steps_completed = TextField(default='[]')  # JSON array of completed steps
    steps_failed = TextField(default='[]')  # JSON array of failed steps
    error_message = TextField(null=True)  # Error details if failed
    result_summary = TextField(null=True)  # JSON summary of processing results
    created_at = DateTimeField(default=datetime.datetime.now)
    started_at = DateTimeField(null=True)  # When processing started
    completed_at = DateTimeField(null=True)  # When processing finished
    
    def get_steps_completed(self):
        """Get completed steps as list"""
        try:
            return json.loads(self.steps_completed)
        except:
            return []
    
    def add_completed_step(self, step_name, step_result=None):
        """Add a completed step"""
        steps = self.get_steps_completed()
        step_data = {
            'name': step_name,
            'completed_at': datetime.datetime.now().isoformat(),
            'result': step_result
        }
        steps.append(step_data)
        self.steps_completed = json.dumps(steps)
        self.save()
    
    def get_steps_failed(self):
        """Get failed steps as list"""
        try:
            return json.loads(self.steps_failed)
        except:
            return []
    
    def add_failed_step(self, step_name, error_message):
        """Add a failed step"""
        steps = self.get_steps_failed()
        step_data = {
            'name': step_name,
            'failed_at': datetime.datetime.now().isoformat(),
            'error': error_message
        }
        steps.append(step_data)
        self.steps_failed = json.dumps(steps)
        self.save()
    
    def get_result_summary(self):
        """Get result summary as dict"""
        try:
            return json.loads(self.result_summary) if self.result_summary else {}
        except:
            return {}
    
    def set_result_summary(self, summary_dict):
        """Set result summary"""
        self.result_summary = json.dumps(summary_dict)
        self.save()
    
    class Meta:
        indexes = (
            (('status',), False),
            (('created_at',), False),
        )

class PageEmbedding(BaseModel):
    """Model for storing page-level vector embeddings"""
    paper = ForeignKeyField(Paper, backref='page_embeddings', on_delete='CASCADE')
    page_number = IntegerField()  # Page number (1-based)
    page_text = TextField(null=True)  # Extracted text from this page
    vector_blob = BlobField()  # Serialized numpy array
    vector_dim = IntegerField()  # Vector dimension
    model_name = CharField(default='bge-m3')  # Embedding model used
    created_at = DateTimeField(default=datetime.datetime.now)
    
    class Meta:
        indexes = (
            (('paper', 'page_number'), True),  # Unique constraint on paper + page_number
        )

class Embedding(BaseModel):
    """Model for storing document-level vector embeddings (averaged from pages)"""
    paper = ForeignKeyField(Paper, backref='embeddings', on_delete='CASCADE')
    vector_blob = BlobField()  # Serialized numpy array
    vector_dim = IntegerField()  # Vector dimension
    model_name = CharField(default='bge-m3')  # Embedding model used
    created_at = DateTimeField(default=datetime.datetime.now)

class Metadata(BaseModel):
    """Model for storing bibliographic metadata"""
    paper = ForeignKeyField(Paper, backref='metadata', unique=True, on_delete='CASCADE')
    title = CharField(null=True)
    authors = TextField(null=True)  # JSON array of author names
    journal = CharField(null=True)
    year = IntegerField(null=True)
    doi = CharField(null=True)
    abstract = TextField(null=True)
    keywords = TextField(null=True)  # JSON array of keywords
    created_at = DateTimeField(default=datetime.datetime.now)
    
    def get_authors_list(self):
        """Return authors as Python list"""
        if self.authors:
            return json.loads(self.authors)
        return []
    
    def set_authors_list(self, authors_list):
        """Set authors from Python list"""
        self.authors = json.dumps(authors_list) if authors_list else None
    
    def get_keywords_list(self):
        """Return keywords as Python list"""
        if self.keywords:
            return json.loads(self.keywords)
        return []
    
    def set_keywords_list(self, keywords_list):
        """Set keywords from Python list"""
        self.keywords = json.dumps(keywords_list) if keywords_list else None

class LayoutAnalysis(BaseModel):
    """Model for storing layout analysis results from Huridocs"""
    paper = ForeignKeyField(Paper, backref='layout', unique=True, on_delete='CASCADE')
    layout_json = TextField()  # Raw Huridocs layout analysis JSON
    page_count = IntegerField()
    created_at = DateTimeField(default=datetime.datetime.now)
    
    def get_layout_data(self):
        """Return layout data as Python dict"""
        return json.loads(self.layout_json)
    
    def set_layout_data(self, layout_dict):
        """Set layout data from Python dict"""
        self.layout_json = json.dumps(layout_dict)

class AdminUser(BaseModel):
    """Model for admin user authentication"""
    username = CharField(unique=True, max_length=50)
    email = CharField(unique=True, max_length=100, null=True)
    password_hash = CharField(max_length=255)  # bcrypt hashed password
    full_name = CharField(max_length=100, null=True)
    is_active = BooleanField(default=True)
    is_superuser = BooleanField(default=False)
    last_login = DateTimeField(null=True)
    created_at = DateTimeField(default=datetime.datetime.now)
    updated_at = DateTimeField(default=datetime.datetime.now)
    
    class Meta:
        indexes = (
            (('username',), True),  # Unique index on username
            (('email',), False),    # Index on email
        )


class FileHash(BaseModel):
    """Model for Level 0 duplicate prevention: MD5 file hash"""
    file_md5 = CharField(primary_key=True)  # MD5 hash of file content
    file_size = BigIntegerField()  # File size in bytes
    original_filename = CharField()  # First uploaded filename
    paper = ForeignKeyField(Paper, backref='file_hashes', on_delete='CASCADE')
    created_at = DateTimeField(default=datetime.datetime.now)
    
    class Meta:
        indexes = (
            (('file_size',), False),
        )


class ContentHash(BaseModel):
    """Model for Level 1 duplicate prevention: Quick content hash"""
    content_hash = CharField(primary_key=True)  # SHA-256 of PDF metadata + first 3 pages text
    pdf_title = CharField(null=True)  # PDF metadata title
    pdf_author = CharField(null=True)  # PDF metadata author
    pdf_creator = CharField(null=True)  # PDF creator
    first_three_pages_text = TextField(null=True)  # First 3 pages text (truncated)
    page_count = IntegerField()  # Total pages
    paper = ForeignKeyField(Paper, backref='content_hashes', on_delete='CASCADE')
    created_at = DateTimeField(default=datetime.datetime.now)
    
    class Meta:
        indexes = (
            (('page_count',), False),
        )


class SampleEmbeddingHash(BaseModel):
    """Model for Level 2 duplicate prevention: Sample embedding hash"""
    embedding_hash = CharField(primary_key=True)  # SHA-256 of sample embedding vector
    sample_strategy = CharField()  # 'first_last_middle' or 'random_pages'
    sample_text = TextField(null=True)  # Representative text sample
    embedding_vector = BlobField()  # Serialized sample embedding vector
    vector_dim = IntegerField()  # Vector dimension
    model_name = CharField(default='bge-m3')  # Embedding model used
    paper = ForeignKeyField(Paper, backref='sample_embeddings', on_delete='CASCADE')
    created_at = DateTimeField(default=datetime.datetime.now)
    
    class Meta:
        indexes = (
            (('sample_strategy',), False),
        )


class DuplicateDetectionLog(BaseModel):
    """Model for tracking duplicate detection performance metrics"""
    detection_id = CharField(primary_key=True)  # UUID4 detection identifier
    filename = CharField()  # Original filename being checked
    file_size = BigIntegerField()  # File size in bytes
    detection_result = CharField()  # 'duplicate_found' or 'no_duplicate' or 'error'
    detection_layer = CharField(null=True)  # 'Level_0_File_Hash', 'Level_1_Content_Hash', 'Level_2_Sample_Embedding', 'No_Duplicate', 'Error'
    duplicate_paper_id = CharField(null=True)  # Document ID of duplicate paper if found
    total_processing_time = FloatField()  # Total time for all layers checked (seconds)
    layer_0_time = FloatField(null=True)  # Time for Level 0 (file hash)
    layer_1_time = FloatField(null=True)  # Time for Level 1 (content hash)
    layer_2_time = FloatField(null=True)  # Time for Level 2 (sample embedding)
    time_saved = FloatField(null=True)  # Estimated time saved by duplicate detection (seconds)
    error_message = TextField(null=True)  # Error details if detection failed
    created_at = DateTimeField(default=datetime.datetime.now)
    
    class Meta:
        indexes = (
            (('detection_layer',), False),
            (('detection_result',), False),
            (('created_at',), False),
        )


def compute_content_id(embedding_vector):
    """
    Compute SHA-256 hash from embedding vector for content-based deduplication
    
    Args:
        embedding_vector: numpy array or list of floats
    
    Returns:
        str: SHA-256 hash string
    """
    if isinstance(embedding_vector, list):
        embedding_vector = np.array(embedding_vector, dtype=np.float32)
    
    byte_vec = embedding_vector.tobytes()
    return hashlib.sha256(byte_vec).hexdigest()

def serialize_vector(vector):
    """
    Serialize numpy array to bytes for storage
    
    Args:
        vector: numpy array
    
    Returns:
        bytes: Serialized vector data
    """
    if isinstance(vector, list):
        vector = np.array(vector, dtype=np.float32)
    
    return vector.tobytes()

def deserialize_vector(vector_blob, vector_dim):
    """
    Deserialize bytes back to numpy array
    
    Args:
        vector_blob: bytes data
        vector_dim: int, vector dimension
    
    Returns:
        numpy.ndarray: Deserialized vector
    """
    return np.frombuffer(vector_blob, dtype=np.float32).reshape(vector_dim)