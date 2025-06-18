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