import os
import logging
from peewee_migrate import Router
from models import *
from embedding import save_paper_embedding_to_vectordb, save_page_embeddings_to_vectordb, get_paper_embedding_from_vectordb

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
    Save embedding vector for a paper to ChromaDB
    
    Args:
        doc_id: str, document ID
        embedding_vector: numpy array or list, embedding vector
        model_name: str, name of embedding model used
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get paper metadata for ChromaDB
        paper = Paper.get(Paper.doc_id == doc_id)
        
        metadata = {
            'filename': paper.filename,
            'content_id': paper.content_id,
            'model_name': model_name,
            'created_at': paper.created_at.isoformat() if paper.created_at else None
        }
        
        # Save to ChromaDB
        success = save_paper_embedding_to_vectordb(doc_id, embedding_vector, metadata)
        
        if success:
            # Also keep a record in SQLite for compatibility (without vector blob)
            try:
                # Delete existing embedding record if any
                Embedding.delete().where(Embedding.paper == paper).execute()
                
                # Create new embedding record (metadata only)
                embedding = Embedding.create(
                    paper=paper,
                    vector_blob=b'',  # Empty blob - actual vector is in ChromaDB
                    vector_dim=len(embedding_vector),
                    model_name=model_name
                )
                logger.info(f"✅ Embedding saved to ChromaDB and SQLite metadata for paper {doc_id}")
            except Exception as sqlite_error:
                logger.warning(f"Failed to save SQLite metadata for {doc_id}: {sqlite_error}")
                # ChromaDB save was successful, so continue
            
            return True
        else:
            logger.error(f"❌ Failed to save embedding to ChromaDB for {doc_id}")
            return False
        
    except Paper.DoesNotExist:
        logger.error(f"Paper {doc_id} not found for embedding")
        return False
    except Exception as e:
        logger.error(f"Error saving embedding for {doc_id}: {e}")
        return False

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
    Get embedding vector by document ID from ChromaDB
    
    Args:
        doc_id: str, document ID
    
    Returns:
        numpy.ndarray: Embedding vector or None if not found
    """
    try:
        # First try to get from ChromaDB
        embedding = get_paper_embedding_from_vectordb(doc_id)
        if embedding is not None:
            return embedding
        
        # Fallback to SQLite (for legacy compatibility)
        try:
            paper = Paper.get(Paper.doc_id == doc_id)
            embedding_record = Embedding.get(Embedding.paper == paper)
            
            # If SQLite has actual vector data (not empty blob)
            if embedding_record.vector_blob and len(embedding_record.vector_blob) > 0:
                logger.info(f"Retrieved embedding from SQLite fallback for {doc_id}")
                return deserialize_vector(embedding_record.vector_blob, embedding_record.vector_dim)
        except (Paper.DoesNotExist, Embedding.DoesNotExist):
            pass
        
        logger.warning(f"No embedding found for document {doc_id}")
        return None
        
    except Exception as e:
        logger.error(f"Error getting embedding for {doc_id}: {e}")
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

def save_page_embedding(doc_id, page_number, page_text, embedding_vector, model_name='bge-m3'):
    """
    Save page-level embedding to database
    
    Args:
        doc_id: str, document ID
        page_number: int, page number (1-based)
        page_text: str, extracted text from the page
        embedding_vector: numpy array, embedding vector
        model_name: str, name of the embedding model used
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get paper instance
        paper = Paper.get(Paper.doc_id == doc_id)
        
        # Delete existing page embedding if exists
        PageEmbedding.delete().where(
            (PageEmbedding.paper == paper) & 
            (PageEmbedding.page_number == page_number)
        ).execute()
        
        # Serialize vector
        vector_blob = serialize_vector(embedding_vector)
        vector_dim = len(embedding_vector)
        
        # Create new page embedding
        PageEmbedding.create(
            paper=paper,
            page_number=page_number,
            page_text=page_text,
            vector_blob=vector_blob,
            vector_dim=vector_dim,
            model_name=model_name
        )
        
        logger.info(f"Saved page {page_number} embedding for document {doc_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving page embedding: {e}")
        return False

def save_page_embeddings_batch(doc_id, page_embeddings_data, model_name='bge-m3'):
    """
    Save multiple page embeddings in batch to ChromaDB
    
    Args:
        doc_id: str, document ID
        page_embeddings_data: list of tuples (page_number, page_text, embedding_vector)
        model_name: str, name of the embedding model used
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get paper instance
        paper = Paper.get(Paper.doc_id == doc_id)
        
        # Save to ChromaDB
        success = save_page_embeddings_to_vectordb(doc_id, page_embeddings_data)
        
        if success:
            # Also save metadata to SQLite for compatibility
            try:
                # Delete all existing page embeddings for this document
                PageEmbedding.delete().where(PageEmbedding.paper == paper).execute()
                
                # Prepare batch data (metadata only, no vector blobs)
                batch_data = []
                for page_number, page_text, embedding_vector in page_embeddings_data:
                    batch_data.append({
                        'paper': paper,
                        'page_number': page_number,
                        'page_text': page_text,
                        'vector_blob': b'',  # Empty blob - actual vector is in ChromaDB
                        'vector_dim': len(embedding_vector),
                        'model_name': model_name
                    })
                
                # Batch insert metadata
                PageEmbedding.insert_many(batch_data).execute()
                
                logger.info(f"✅ Saved {len(batch_data)} page embeddings to ChromaDB and SQLite metadata for document {doc_id}")
            except Exception as sqlite_error:
                logger.warning(f"Failed to save SQLite page metadata for {doc_id}: {sqlite_error}")
                # ChromaDB save was successful, so continue
            
            return True
        else:
            logger.error(f"❌ Failed to save page embeddings to ChromaDB for {doc_id}")
            return False
        
    except Exception as e:
        logger.error(f"Error saving page embeddings batch: {e}")
        return False

def get_page_embeddings_by_id(doc_id):
    """
    Get all page embeddings for a document
    
    Args:
        doc_id: str, document ID
    
    Returns:
        list: List of tuples (page_number, page_text, embedding_vector) or None if not found
    """
    try:
        paper = Paper.get(Paper.doc_id == doc_id)
        page_embeddings = PageEmbedding.select().where(
            PageEmbedding.paper == paper
        ).order_by(PageEmbedding.page_number)
        
        result = []
        for page_emb in page_embeddings:
            embedding_vector = deserialize_vector(page_emb.vector_blob, page_emb.vector_dim)
            result.append((page_emb.page_number, page_emb.page_text, embedding_vector))
        
        return result
        
    except Paper.DoesNotExist:
        return None

def get_page_embedding_by_page(doc_id, page_number):
    """
    Get embedding for a specific page
    
    Args:
        doc_id: str, document ID
        page_number: int, page number (1-based)
    
    Returns:
        tuple: (page_text, embedding_vector) or None if not found
    """
    try:
        paper = Paper.get(Paper.doc_id == doc_id)
        page_emb = PageEmbedding.get(
            (PageEmbedding.paper == paper) & 
            (PageEmbedding.page_number == page_number)
        )
        
        embedding_vector = deserialize_vector(page_emb.vector_blob, page_emb.vector_dim)
        return page_emb.page_text, embedding_vector
        
    except (Paper.DoesNotExist, PageEmbedding.DoesNotExist):
        return None

def delete_page_embeddings(doc_id):
    """
    Delete all page embeddings for a document
    
    Args:
        doc_id: str, document ID
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        paper = Paper.get(Paper.doc_id == doc_id)
        deleted_count = PageEmbedding.delete().where(PageEmbedding.paper == paper).execute()
        
        logger.info(f"Deleted {deleted_count} page embeddings for document {doc_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error deleting page embeddings: {e}")
        return False