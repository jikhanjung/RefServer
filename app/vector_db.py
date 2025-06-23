"""
ChromaDB Vector Database Client for RefServer
Handles vector storage, retrieval, and similarity search for embeddings
"""

import os
import logging
import time
from typing import List, Dict, Any, Optional, Tuple
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
import numpy as np

logger = logging.getLogger(__name__)

class ChromaVectorDB:
    """
    ChromaDB client for managing paper and page embeddings
    Uses embedded/persistent mode for simplicity and performance
    """
    
    def __init__(self, persist_dir: str = None):
        """
        Initialize ChromaDB client with persistent storage
        
        Args:
            persist_dir: str, directory for persistent storage (default: /refdata/chromadb)
        """
        # Set up persistent directory
        self.persist_dir = persist_dir or "/refdata/chromadb"
        os.makedirs(self.persist_dir, exist_ok=True)
        
        # Initialize persistent client
        try:
            self.client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=Settings(
                    allow_reset=False,
                    anonymized_telemetry=False
                )
            )
            
            logger.info(f"✅ ChromaDB initialized at {self.persist_dir}")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize ChromaDB at {self.persist_dir}: {e}")
            raise
        
        # Initialize collections
        self._init_collections()
    
    def _init_collections(self):
        """Initialize paper and page collections"""
        try:
            # Papers collection - document-level embeddings
            self.papers_collection = self.client.get_or_create_collection(
                name="papers",
                metadata={
                    "hnsw:space": "cosine",
                    "hnsw:M": 16,
                    "hnsw:construction_ef": 200,
                    "hnsw:search_ef": 10,
                    "description": "Document-level embeddings for academic papers"
                }
            )
            
            # Pages collection - page-level embeddings
            self.pages_collection = self.client.get_or_create_collection(
                name="pages",
                metadata={
                    "hnsw:space": "cosine", 
                    "hnsw:M": 16,
                    "hnsw:construction_ef": 200,
                    "hnsw:search_ef": 10,
                    "description": "Page-level embeddings for academic papers"
                }
            )
            
            logger.info("ChromaDB collections initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB collections: {e}")
            raise
    
    def add_paper_embedding(self, doc_id: str, embedding: List[float], metadata: Dict[str, Any] = None) -> bool:
        """
        Add document-level embedding to ChromaDB
        
        Args:
            doc_id: str, unique document identifier
            embedding: List[float], 1024-dimension embedding vector
            metadata: Dict, paper metadata (filename, content_id, etc.)
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Prepare metadata
            paper_metadata = metadata or {}
            paper_metadata.update({
                'doc_id': doc_id,
                'embedding_type': 'document',
                'created_at': time.time()
            })
            
            # Remove existing embedding if exists
            try:
                self.papers_collection.delete(ids=[doc_id])
            except:
                pass  # Collection might be empty
            
            # Add new embedding
            self.papers_collection.add(
                ids=[doc_id],
                embeddings=[embedding],
                metadatas=[paper_metadata]
            )
            
            logger.info(f"Added paper embedding for document {doc_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add paper embedding for {doc_id}: {e}")
            return False
    
    def add_page_embeddings(self, doc_id: str, page_embeddings: List[Dict[str, Any]]) -> bool:
        """
        Add page-level embeddings in batch
        
        Args:
            doc_id: str, document identifier
            page_embeddings: List of dicts with keys: page_number, embedding, text
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not page_embeddings:
                logger.warning(f"No page embeddings provided for document {doc_id}")
                return False
            
            # Remove existing page embeddings for this document
            try:
                existing_ids = [f"{doc_id}_page_{i+1}" for i in range(100)]  # Assume max 100 pages
                self.pages_collection.delete(ids=existing_ids)
            except:
                pass  # Collection might be empty
            
            # Prepare batch data
            ids = []
            embeddings = []
            metadatas = []
            
            for page_data in page_embeddings:
                page_id = f"{doc_id}_page_{page_data['page_number']}"
                ids.append(page_id)
                embeddings.append(page_data['embedding'])
                
                metadata = {
                    'doc_id': doc_id,
                    'page_number': page_data['page_number'],
                    'text_preview': page_data.get('text', '')[:500],  # First 500 chars
                    'embedding_type': 'page',
                    'created_at': time.time()
                }
                metadatas.append(metadata)
            
            # Batch insert
            self.pages_collection.add(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas
            )
            
            logger.info(f"Added {len(page_embeddings)} page embeddings for document {doc_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add page embeddings for {doc_id}: {e}")
            return False
    
    def find_similar_papers(self, query_embedding: List[float], n_results: int = 10, 
                           filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Find similar papers using cosine similarity
        
        Args:
            query_embedding: List[float], query embedding vector
            n_results: int, number of results to return
            filters: Dict, metadata filters (optional)
        
        Returns:
            Dict: ChromaDB query results with ids, distances, metadatas
        """
        try:
            # Prepare query parameters
            query_params = {
                'query_embeddings': [query_embedding],
                'n_results': min(n_results, 100),  # Cap at 100 results
                'include': ['metadatas', 'distances']
            }
            
            # Add filters if provided
            if filters:
                query_params['where'] = filters
            
            # Execute query
            results = self.papers_collection.query(**query_params)
            
            logger.info(f"Found {len(results['ids'][0])} similar papers")
            return results
            
        except Exception as e:
            logger.error(f"Failed to find similar papers: {e}")
            return {'ids': [[]], 'distances': [[]], 'metadatas': [[]]}
    
    def find_similar_pages(self, query_embedding: List[float], n_results: int = 20,
                          doc_filter: str = None) -> Dict[str, Any]:
        """
        Find similar pages using cosine similarity
        
        Args:
            query_embedding: List[float], query embedding vector  
            n_results: int, number of results to return
            doc_filter: str, filter by specific document ID (optional)
        
        Returns:
            Dict: ChromaDB query results
        """
        try:
            query_params = {
                'query_embeddings': [query_embedding],
                'n_results': min(n_results, 100),
                'include': ['metadatas', 'distances']
            }
            
            if doc_filter:
                query_params['where'] = {'doc_id': doc_filter}
            
            results = self.pages_collection.query(**query_params)
            
            logger.info(f"Found {len(results['ids'][0])} similar pages")
            return results
            
        except Exception as e:
            logger.error(f"Failed to find similar pages: {e}")
            return {'ids': [[]], 'distances': [[]], 'metadatas': [[]]}
    
    def get_paper_embedding(self, doc_id: str) -> Optional[List[float]]:
        """
        Get document embedding by ID
        
        Args:
            doc_id: str, document identifier
        
        Returns:
            List[float]: embedding vector or None if not found
        """
        try:
            results = self.papers_collection.get(
                ids=[doc_id],
                include=['embeddings']
            )
            
            if results['embeddings'] and len(results['embeddings']) > 0:
                return results['embeddings'][0]
            
            logger.warning(f"No embedding found for document {doc_id}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to get paper embedding for {doc_id}: {e}")
            return None
    
    def delete_paper_embeddings(self, doc_id: str) -> bool:
        """
        Delete all embeddings (paper + pages) for a document
        
        Args:
            doc_id: str, document identifier
        
        Returns:
            bool: True if successful
        """
        try:
            # Delete paper embedding
            try:
                self.papers_collection.delete(ids=[doc_id])
            except:
                pass
            
            # Delete page embeddings
            try:
                # Get all page IDs for this document
                page_results = self.pages_collection.get(
                    where={'doc_id': doc_id},
                    include=['metadatas']
                )
                
                if page_results['ids']:
                    self.pages_collection.delete(ids=page_results['ids'])
            except:
                pass
            
            logger.info(f"Deleted all embeddings for document {doc_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete embeddings for {doc_id}: {e}")
            return False
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get statistics about ChromaDB collections
        
        Returns:
            Dict: Collection statistics
        """
        try:
            papers_count = self.papers_collection.count()
            pages_count = self.pages_collection.count()
            
            return {
                'papers_count': papers_count,
                'pages_count': pages_count,
                'collections': ['papers', 'pages'],
                'status': 'healthy'
            }
            
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {
                'papers_count': 0,
                'pages_count': 0,
                'collections': [],
                'status': 'error',
                'error': str(e)
            }
    
    def health_check(self) -> bool:
        """
        Check if ChromaDB is healthy and responsive
        
        Returns:
            bool: True if healthy
        """
        try:
            # For PersistentClient, check if we can list collections
            collections = self.client.list_collections()
            return True
        except Exception as e:
            logger.error(f"ChromaDB health check failed: {e}")
            return False

# Global ChromaDB instance
_chroma_db_instance = None

def get_vector_db() -> ChromaVectorDB:
    """
    Get global ChromaDB instance (singleton pattern)
    
    Returns:
        ChromaVectorDB: Global instance
    """
    global _chroma_db_instance
    
    if _chroma_db_instance is None:
        _chroma_db_instance = ChromaVectorDB()
    
    return _chroma_db_instance

def initialize_vector_db() -> bool:
    """
    Initialize ChromaDB connection at startup
    
    Returns:
        bool: True if successful
    """
    try:
        vector_db = get_vector_db()
        if vector_db.health_check():
            logger.info("✅ ChromaDB initialized successfully")
            return True
        else:
            logger.error("❌ ChromaDB health check failed")
            return False
    except Exception as e:
        logger.error(f"❌ ChromaDB initialization failed: {e}")
        return False