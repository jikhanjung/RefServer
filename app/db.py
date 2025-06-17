import os
import logging
from peewee_migrate import Router
from models import *

logger = logging.getLogger(__name__)

def initialize_database():
    """
    Initialize database by running migrations
    This should be called at application startup
    """
    try:
        # Ensure data directory exists
        data_dir = '/data'
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            logger.info(f"Created data directory: {data_dir}")
        
        # Ensure migrations directory exists
        migrations_path = '/app/migrations'
        if not os.path.exists(migrations_path):
            os.makedirs(migrations_path)
            logger.info(f"Created migrations directory: {migrations_path}")
        
        # Connect to database if not already connected
        if db.is_closed():
            db.connect()
            logger.info(f"Connected to database: {DATABASE_PATH}")
        else:
            logger.info(f"Database already connected: {DATABASE_PATH}")
        
        # Initialize migration router
        router = Router(db, migrate_dir=migrations_path)
        
        # Run all pending migrations
        router.run()
        logger.info("Database migrations completed successfully")
        
        return True
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        return False

def get_db_connection():
    """Get database connection"""
    if db.is_closed():
        db.connect()
    return db

def close_db_connection():
    """Close database connection"""
    if not db.is_closed():
        db.close()

# CRUD Operations

def save_paper(doc_id, filename, file_path, content_id=None):
    """
    Save or update paper record
    
    Args:
        doc_id: str, unique document ID
        filename: str, original filename
        file_path: str, stored file path
        content_id: str, optional content-based hash
    
    Returns:
        Paper: Created or updated paper instance
    """
    try:
        paper, created = Paper.get_or_create(
            doc_id=doc_id,
            defaults={
                'filename': filename,
                'file_path': file_path,
                'content_id': content_id
            }
        )
        
        if not created:
            # Update existing record
            paper.filename = filename
            paper.file_path = file_path
            if content_id:
                paper.content_id = content_id
            paper.updated_at = datetime.datetime.now()
            paper.save()
        
        logger.info(f"Paper {'created' if created else 'updated'}: {doc_id}")
        return paper
        
    except Exception as e:
        logger.error(f"Error saving paper {doc_id}: {e}")
        raise

def save_embedding(doc_id, embedding_vector, model_name='bge-m3'):
    """
    Save embedding vector for a paper
    
    Args:
        doc_id: str, document ID
        embedding_vector: numpy array or list, embedding vector
        model_name: str, name of embedding model used
    
    Returns:
        Embedding: Created embedding instance
    """
    try:
        paper = Paper.get(Paper.doc_id == doc_id)
        
        # Serialize vector
        vector_blob = serialize_vector(embedding_vector)
        vector_dim = len(embedding_vector)
        
        # Delete existing embedding if any
        Embedding.delete().where(Embedding.paper == paper).execute()
        
        # Create new embedding
        embedding = Embedding.create(
            paper=paper,
            vector_blob=vector_blob,
            vector_dim=vector_dim,
            model_name=model_name
        )
        
        logger.info(f"Embedding saved for paper {doc_id}")
        return embedding
        
    except Paper.DoesNotExist:
        logger.error(f"Paper {doc_id} not found for embedding")
        raise
    except Exception as e:
        logger.error(f"Error saving embedding for {doc_id}: {e}")
        raise

def save_metadata(doc_id, title=None, authors=None, journal=None, 
                 year=None, doi=None, abstract=None, keywords=None):
    """
    Save bibliographic metadata for a paper
    
    Args:
        doc_id: str, document ID
        title: str, paper title
        authors: list, list of author names
        journal: str, journal name
        year: int, publication year
        doi: str, DOI
        abstract: str, abstract text
        keywords: list, list of keywords
    
    Returns:
        Metadata: Created or updated metadata instance
    """
    try:
        paper = Paper.get(Paper.doc_id == doc_id)
        
        metadata, created = Metadata.get_or_create(
            paper=paper,
            defaults={
                'title': title,
                'journal': journal,
                'year': year,
                'doi': doi,
                'abstract': abstract
            }
        )
        
        if not created:
            # Update existing metadata
            if title is not None:
                metadata.title = title
            if journal is not None:
                metadata.journal = journal
            if year is not None:
                metadata.year = year
            if doi is not None:
                metadata.doi = doi
            if abstract is not None:
                metadata.abstract = abstract
        
        # Set authors and keywords using helper methods
        if authors is not None:
            metadata.set_authors_list(authors)
        if keywords is not None:
            metadata.set_keywords_list(keywords)
        
        metadata.save()
        
        logger.info(f"Metadata {'created' if created else 'updated'} for paper {doc_id}")
        return metadata
        
    except Paper.DoesNotExist:
        logger.error(f"Paper {doc_id} not found for metadata")
        raise
    except Exception as e:
        logger.error(f"Error saving metadata for {doc_id}: {e}")
        raise

def save_layout_analysis(doc_id, layout_data, page_count):
    """
    Save layout analysis results for a paper
    
    Args:
        doc_id: str, document ID
        layout_data: dict, layout analysis results from Huridocs
        page_count: int, number of pages
    
    Returns:
        LayoutAnalysis: Created or updated layout analysis instance
    """
    try:
        paper = Paper.get(Paper.doc_id == doc_id)
        
        layout, created = LayoutAnalysis.get_or_create(
            paper=paper,
            defaults={
                'page_count': page_count
            }
        )
        
        # Set layout data using helper method
        layout.set_layout_data(layout_data)
        layout.page_count = page_count
        layout.save()
        
        logger.info(f"Layout analysis {'created' if created else 'updated'} for paper {doc_id}")
        return layout
        
    except Paper.DoesNotExist:
        logger.error(f"Paper {doc_id} not found for layout analysis")
        raise
    except Exception as e:
        logger.error(f"Error saving layout analysis for {doc_id}: {e}")
        raise

def update_ocr_quality(doc_id, ocr_text, ocr_quality):
    """
    Update OCR text and quality assessment for a paper
    
    Args:
        doc_id: str, document ID
        ocr_text: str, extracted text
        ocr_quality: str, quality assessment result
    
    Returns:
        Paper: Updated paper instance
    """
    try:
        paper = Paper.get(Paper.doc_id == doc_id)
        paper.ocr_text = ocr_text
        paper.ocr_quality = ocr_quality
        paper.updated_at = datetime.datetime.now()
        paper.save()
        
        logger.info(f"OCR data updated for paper {doc_id}")
        return paper
        
    except Paper.DoesNotExist:
        logger.error(f"Paper {doc_id} not found for OCR update")
        raise
    except Exception as e:
        logger.error(f"Error updating OCR data for {doc_id}: {e}")
        raise

def get_paper_by_id(doc_id):
    """
    Get paper by document ID
    
    Args:
        doc_id: str, document ID
    
    Returns:
        Paper: Paper instance or None if not found
    """
    try:
        return Paper.get(Paper.doc_id == doc_id)
    except Paper.DoesNotExist:
        return None

def get_paper_by_content_id(content_id):
    """
    Get paper by content ID (for deduplication)
    
    Args:
        content_id: str, content-based hash
    
    Returns:
        Paper: Paper instance or None if not found
    """
    try:
        return Paper.get(Paper.content_id == content_id)
    except Paper.DoesNotExist:
        return None

def get_embedding_by_id(doc_id):
    """
    Get embedding vector by document ID
    
    Args:
        doc_id: str, document ID
    
    Returns:
        numpy.ndarray: Embedding vector or None if not found
    """
    try:
        paper = Paper.get(Paper.doc_id == doc_id)
        embedding = Embedding.get(Embedding.paper == paper)
        return deserialize_vector(embedding.vector_blob, embedding.vector_dim)
    except (Paper.DoesNotExist, Embedding.DoesNotExist):
        return None

def get_metadata_by_id(doc_id):
    """
    Get metadata by document ID
    
    Args:
        doc_id: str, document ID
    
    Returns:
        Metadata: Metadata instance or None if not found
    """
    try:
        paper = Paper.get(Paper.doc_id == doc_id)
        return Metadata.get(Metadata.paper == paper)
    except (Paper.DoesNotExist, Metadata.DoesNotExist):
        return None

def get_layout_by_id(doc_id):
    """
    Get layout analysis by document ID
    
    Args:
        doc_id: str, document ID
    
    Returns:
        dict: Layout analysis data or None if not found
    """
    try:
        paper = Paper.get(Paper.doc_id == doc_id)
        layout = LayoutAnalysis.get(LayoutAnalysis.paper == paper)
        return layout.get_layout_data()
    except (Paper.DoesNotExist, LayoutAnalysis.DoesNotExist):
        return None