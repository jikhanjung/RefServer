import os
import logging
import numpy as np
import torch
from sentence_transformers import SentenceTransformer
import re
from typing import List, Optional
import gc
from vector_db import get_vector_db

logger = logging.getLogger(__name__)

class BGEEmbedding:
    """
    BGE-M3 embedding model wrapper for multilingual text embedding
    """
    
    def __init__(self, model_path: str = None, device=None):
        """
        Initialize BGE-M3 embedding model
        
        Args:
            model_path: str, path to local model or HuggingFace model name
            device: str, device to run model on ('cuda', 'cpu', or None for auto)
        """
        # Use local model if available, otherwise fallback to HuggingFace
        if model_path is None:
            local_model_path = "/app/models/bge-m3-local"
            if os.path.exists(local_model_path):
                self.model_path = local_model_path
                logger.info("Using local BGE-M3 model")
            else:
                self.model_path = "BAAI/bge-m3"
                logger.info("Local model not found, will download from HuggingFace")
        else:
            self.model_path = model_path
        
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = None
        self.max_length = 8192  # BGE-M3 max sequence length
        
        logger.info(f"Initializing BGE-M3 embedding model on {self.device}")
        logger.info(f"Model path: {self.model_path}")
        self._load_model()
    
    def _load_model(self):
        """Load SentenceTransformer model"""
        try:
            self.model = SentenceTransformer(self.model_path, device=self.device)
            
            logger.info(f"BGE-M3 model loaded successfully on {self.device}")
            
        except Exception as e:
            logger.error(f"Failed to load BGE-M3 model: {e}")
            raise
    
    def _preprocess_text(self, text: str) -> str:
        """
        Preprocess text for better embedding quality
        
        Args:
            text: str, input text
            
        Returns:
            str: preprocessed text
        """
        if not text:
            return ""
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters that might interfere
        text = re.sub(r'[^\w\s\.\,\!\?\;\:\-\(\)]', ' ', text)
        
        # Normalize whitespace
        text = text.strip()
        
        return text
    
    def _chunk_text(self, text: str, max_chars: int = 4000) -> List[str]:
        """
        Split text into chunks for processing
        
        Args:
            text: str, input text
            max_chars: int, maximum characters per chunk
            
        Returns:
            List[str]: list of text chunks
        """
        # Split by sentences first
        sentences = re.split(r'[.!?]\s+', text)
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            test_chunk = current_chunk + " " + sentence if current_chunk else sentence
            
            if len(test_chunk) <= max_chars:
                current_chunk = test_chunk
            else:
                # Save current chunk if not empty
                if current_chunk:
                    chunks.append(current_chunk.strip())
                
                # Handle very long sentences
                if len(sentence) > max_chars:
                    # Split long sentence by words
                    words = sentence.split()
                    temp_chunk = ""
                    
                    for word in words:
                        test_word_chunk = temp_chunk + " " + word if temp_chunk else word
                        if len(test_word_chunk) <= max_chars:
                            temp_chunk = test_word_chunk
                        else:
                            if temp_chunk:
                                chunks.append(temp_chunk.strip())
                            temp_chunk = word
                    
                    if temp_chunk:
                        current_chunk = temp_chunk
                    else:
                        current_chunk = ""
                else:
                    current_chunk = sentence
        
        # Add final chunk
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        # Filter out empty chunks
        chunks = [chunk for chunk in chunks if chunk.strip()]
        
        if not chunks:
            chunks = [text[:max_chars]]  # Fallback
        
        logger.info(f"Text split into {len(chunks)} chunks")
        return chunks
    
    def encode_text(self, text: str, normalize: bool = True) -> np.ndarray:
        """
        Encode single text into embedding vector
        
        Args:
            text: str, input text
            normalize: bool, whether to normalize the embedding
            
        Returns:
            np.ndarray: embedding vector
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return np.zeros(1024, dtype=np.float32)  # BGE-M3 dimension
        
        try:
            # Preprocess text
            processed_text = self._preprocess_text(text)
            
            # Generate embedding using SentenceTransformer
            embedding = self.model.encode(
                processed_text,
                normalize_embeddings=normalize,
                convert_to_numpy=True
            )
            
            return embedding.astype(np.float32)
            
        except Exception as e:
            logger.error(f"Error encoding text: {e}")
            return np.zeros(1024, dtype=np.float32)
    
    def encode_chunks_and_average(self, text: str, normalize: bool = True) -> np.ndarray:
        """
        Encode long text by chunking and averaging embeddings
        
        Args:
            text: str, input text (can be very long)
            normalize: bool, whether to normalize the final embedding
            
        Returns:
            np.ndarray: averaged embedding vector
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for chunked embedding")
            return np.zeros(1024, dtype=np.float32)
        
        try:
            # Split text into chunks
            chunks = self._chunk_text(text)
            
            if not chunks:
                return np.zeros(1024, dtype=np.float32)
            
            # Encode all chunks at once for better performance
            valid_chunks = [chunk for chunk in chunks if chunk.strip()]
            
            if not valid_chunks:
                return np.zeros(1024, dtype=np.float32)
            
            # Batch encoding
            embeddings = self.model.encode(
                valid_chunks,
                normalize_embeddings=False,
                convert_to_numpy=True,
                show_progress_bar=len(valid_chunks) > 10
            )
            
            # Average embeddings
            averaged_embedding = np.mean(embeddings, axis=0)
            
            # Normalize if requested
            if normalize:
                norm = np.linalg.norm(averaged_embedding)
                if norm > 0:
                    averaged_embedding = averaged_embedding / norm
            
            logger.info(f"Generated averaged embedding from {len(valid_chunks)} chunks")
            return averaged_embedding.astype(np.float32)
            
        except Exception as e:
            logger.error(f"Error in chunked embedding: {e}")
            return np.zeros(1024, dtype=np.float32)
    
    def cleanup(self):
        """Clean up model resources"""
        try:
            if self.model is not None:
                del self.model
            
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            gc.collect()
            logger.info("BGE embedding model cleaned up")
            
        except Exception as e:
            logger.error(f"Error cleaning up model: {e}")

# Global model instance (singleton pattern)
_embedding_model = None

def get_embedding_model() -> BGEEmbedding:
    """
    Get global BGE embedding model instance (singleton)
    
    Returns:
        BGEEmbedding: model instance
    """
    global _embedding_model
    
    if _embedding_model is None:
        _embedding_model = BGEEmbedding()
    
    return _embedding_model

def cleanup_embedding_model():
    """Clean up global embedding model"""
    global _embedding_model
    
    if _embedding_model is not None:
        _embedding_model.cleanup()
        _embedding_model = None

def generate_text_embedding(text: str, use_chunking: bool = True) -> np.ndarray:
    """
    Generate embedding for text using BGE-M3 model
    
    Args:
        text: str, input text
        use_chunking: bool, whether to use chunking for long texts
        
    Returns:
        np.ndarray: embedding vector (1024 dimensions)
    """
    if not text or not text.strip():
        logger.warning("Empty text provided for embedding generation")
        return np.zeros(1024, dtype=np.float32)
    
    try:
        model = get_embedding_model()
        
        # Choose encoding method based on text length and user preference
        if use_chunking and len(text) > 4000:  # Use chunking for long texts
            embedding = model.encode_chunks_and_average(text)
        else:
            embedding = model.encode_text(text)
        
        logger.info(f"Generated embedding with shape {embedding.shape}")
        return embedding
        
    except Exception as e:
        logger.error(f"Error generating text embedding: {e}")
        return np.zeros(1024, dtype=np.float32)

def generate_page_embeddings(page_texts: List[str]) -> List[np.ndarray]:
    """
    Generate embeddings for multiple pages
    
    Args:
        page_texts: List[str], list of page texts
        
    Returns:
        List[np.ndarray]: list of embedding vectors (1024 dimensions each)
    """
    if not page_texts:
        logger.warning("Empty page texts provided for embedding generation")
        return []
    
    try:
        model = get_embedding_model()
        embeddings = []
        
        # Process each page text
        for i, page_text in enumerate(page_texts):
            if not page_text or not page_text.strip():
                logger.warning(f"Empty text for page {i+1}, using zero vector")
                embeddings.append(np.zeros(1024, dtype=np.float32))
                continue
            
            # Use single encoding for page-level text (no chunking needed)
            embedding = model.encode_text(page_text)
            embeddings.append(embedding)
        
        logger.info(f"Generated embeddings for {len(embeddings)} pages")
        return embeddings
        
    except Exception as e:
        logger.error(f"Error generating page embeddings: {e}")
        return [np.zeros(1024, dtype=np.float32) for _ in page_texts]

def compute_document_embedding_from_pages(page_embeddings: List[np.ndarray]) -> np.ndarray:
    """
    Compute document-level embedding by averaging page embeddings
    
    Args:
        page_embeddings: List[np.ndarray], list of page embedding vectors
        
    Returns:
        np.ndarray: averaged document embedding vector (1024 dimensions)
    """
    logger.info(f"📄 Computing document embedding from {len(page_embeddings)} page embeddings")
    
    if not page_embeddings:
        logger.warning("Empty page embeddings provided")
        return np.zeros(1024, dtype=np.float32)
    
    try:
        # Log input details
        logger.debug(f"Input page embeddings count: {len(page_embeddings)}")
        logger.debug(f"First page embedding shape: {page_embeddings[0].shape if page_embeddings else 'N/A'}")
        logger.debug(f"First page embedding sample: {page_embeddings[0][:5] if page_embeddings else 'N/A'}")
        
        # Filter out zero vectors
        valid_embeddings = []
        zero_count = 0
        for i, emb in enumerate(page_embeddings):
            if np.any(emb):
                valid_embeddings.append(emb)
                logger.debug(f"Page {i+1}: Valid embedding (norm={np.linalg.norm(emb):.4f})")
            else:
                zero_count += 1
                logger.debug(f"Page {i+1}: Zero embedding (skipped)")
        
        logger.info(f"Valid embeddings: {len(valid_embeddings)}, Zero embeddings: {zero_count}")
        
        if not valid_embeddings:
            logger.warning("No valid page embeddings found - all were zero vectors")
            return np.zeros(1024, dtype=np.float32)
        
        # Compute average
        averaged_embedding = np.mean(valid_embeddings, axis=0)
        logger.debug(f"Raw averaged embedding shape: {averaged_embedding.shape}")
        logger.debug(f"Raw averaged embedding norm: {np.linalg.norm(averaged_embedding):.6f}")
        logger.debug(f"Raw averaged embedding sample: {averaged_embedding[:5]}")
        
        # Normalize
        norm = np.linalg.norm(averaged_embedding)
        if norm > 0:
            averaged_embedding = averaged_embedding / norm
            logger.info(f"✅ Normalized document embedding (norm was {norm:.6f})")
        else:
            logger.warning("Document embedding norm is zero - cannot normalize")
        
        final_embedding = averaged_embedding.astype(np.float32)
        logger.info(f"✅ Computed document embedding from {len(valid_embeddings)} page embeddings")
        logger.debug(f"Final embedding shape: {final_embedding.shape}, dtype: {final_embedding.dtype}")
        logger.debug(f"Final embedding sample: {final_embedding[:5]}")
        
        return final_embedding
        
    except Exception as e:
        logger.error(f"Error computing document embedding from pages: {e}", exc_info=True)
        return np.zeros(1024, dtype=np.float32)

def compute_similarity(embedding1: np.ndarray, embedding2: np.ndarray) -> float:
    """
    Compute cosine similarity between two embeddings
    
    Args:
        embedding1: np.ndarray, first embedding vector
        embedding2: np.ndarray, second embedding vector
        
    Returns:
        float: cosine similarity score (0-1)
    """
    try:
        # Ensure embeddings are normalized
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        embedding1_normalized = embedding1 / norm1
        embedding2_normalized = embedding2 / norm2
        
        # Compute cosine similarity
        similarity = np.dot(embedding1_normalized, embedding2_normalized)
        
        # Clamp to [0, 1] range
        similarity = max(0.0, min(1.0, float(similarity)))
        
        return similarity
    except Exception as e:
        logger.error(f"Error computing similarity: {e}")
        return 0.0

# ChromaDB Integration Functions
def save_paper_embedding_to_vectordb(doc_id: str, embedding: np.ndarray, metadata: dict = None) -> bool:
    """
    Save document-level embedding to ChromaDB
    
    Args:
        doc_id: str, document identifier
        embedding: np.ndarray, embedding vector
        metadata: dict, additional metadata
    
    Returns:
        bool: True if successful
    """
    logger.info(f"💾 Saving document embedding to ChromaDB for doc_id: {doc_id}")
    
    try:
        # Validate embedding
        if embedding is None or len(embedding) == 0:
            logger.error(f"Invalid embedding for {doc_id}: None or empty")
            return False
        
        logger.debug(f"Embedding shape: {embedding.shape}, dtype: {embedding.dtype}")
        logger.debug(f"Embedding norm: {np.linalg.norm(embedding):.6f}")
        logger.debug(f"Embedding sample: {embedding[:5]}")
        
        vector_db = get_vector_db()
        
        # Prepare metadata
        paper_metadata = metadata or {}
        if 'embedding_type' not in paper_metadata:
            paper_metadata['embedding_type'] = 'document'
        
        logger.debug(f"Metadata for ChromaDB: {paper_metadata}")
        
        # Convert to list for ChromaDB
        embedding_list = embedding.tolist()
        logger.debug(f"Converted to list, length: {len(embedding_list)}")
        
        success = vector_db.add_paper_embedding(
            doc_id=doc_id,
            embedding=embedding_list,
            metadata=paper_metadata
        )
        
        if success:
            logger.info(f"✅ Paper embedding saved to ChromaDB successfully: {doc_id}")
            logger.debug(f"ChromaDB save operation completed for {doc_id}")
        else:
            logger.error(f"❌ Failed to save paper embedding to ChromaDB: {doc_id}")
            logger.error(f"ChromaDB add_paper_embedding returned False for {doc_id}")
        
        return success
        
    except Exception as e:
        logger.error(f"Error saving paper embedding to ChromaDB for {doc_id}: {e}", exc_info=True)
        return False

def save_page_embeddings_to_vectordb(doc_id: str, page_embeddings_data: List[tuple]) -> bool:
    """
    Save page-level embeddings to ChromaDB
    
    Args:
        doc_id: str, document identifier
        page_embeddings_data: List of tuples (page_number, page_text, embedding_vector)
    
    Returns:
        bool: True if successful
    """
    logger.info(f"🔄 Starting ChromaDB page embeddings save for doc_id: {doc_id}")
    logger.info(f"📊 Input data: {len(page_embeddings_data)} page embeddings")
    
    try:
        vector_db = get_vector_db()
        logger.debug(f"🔌 ChromaDB connection obtained: {type(vector_db)}")
        
        # Validate input data
        if not page_embeddings_data:
            logger.error(f"❌ Empty page embeddings data for {doc_id}")
            return False
        
        # Prepare page embeddings for ChromaDB
        page_data = []
        for i, (page_number, page_text, embedding_vector) in enumerate(page_embeddings_data):
            logger.debug(f"📄 Processing page {page_number}: text length={len(page_text) if page_text else 0}, embedding shape={embedding_vector.shape if hasattr(embedding_vector, 'shape') else type(embedding_vector)}")
            
            # Validate embedding
            if embedding_vector is None:
                logger.error(f"❌ None embedding for page {page_number} in {doc_id}")
                continue
                
            if hasattr(embedding_vector, 'tolist'):
                embedding_list = embedding_vector.tolist()
            else:
                embedding_list = list(embedding_vector)
                
            logger.debug(f"📄 Page {page_number}: embedding converted to list, length={len(embedding_list)}")
            
            page_data.append({
                'page_number': page_number,
                'text': page_text[:500] if page_text else '',  # Truncate text for metadata
                'embedding': embedding_list
            })
        
        logger.info(f"📊 Prepared {len(page_data)} valid page data entries for ChromaDB")
        
        if not page_data:
            logger.error(f"❌ No valid page data prepared for {doc_id}")
            return False
        
        # Call ChromaDB save
        logger.info(f"💾 Calling ChromaDB add_page_embeddings for {doc_id}")
        success = vector_db.add_page_embeddings(doc_id, page_data)
        
        if success:
            logger.info(f"✅ {len(page_data)} page embeddings saved to ChromaDB: {doc_id}")
            
            # Verify the save by checking count
            try:
                stats = vector_db.get_collection_stats()
                logger.info(f"📊 ChromaDB stats after save: {stats}")
            except Exception as stats_error:
                logger.warning(f"⚠️ Failed to get ChromaDB stats: {stats_error}")
                
        else:
            logger.error(f"❌ Failed to save page embeddings to ChromaDB: {doc_id}")
            logger.error(f"❌ ChromaDB add_page_embeddings returned False")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ Exception in save_page_embeddings_to_vectordb for {doc_id}: {e}", exc_info=True)
        return False

def get_paper_embedding_from_vectordb(doc_id: str) -> Optional[np.ndarray]:
    """
    Get document embedding from ChromaDB
    
    Args:
        doc_id: str, document identifier
    
    Returns:
        np.ndarray: embedding vector or None if not found
    """
    try:
        vector_db = get_vector_db()
        embedding_list = vector_db.get_paper_embedding(doc_id)
        
        if embedding_list:
            embedding = np.array(embedding_list, dtype=np.float32)
            logger.info(f"✅ Retrieved paper embedding from ChromaDB: {doc_id}")
            return embedding
        else:
            logger.warning(f"No paper embedding found in ChromaDB: {doc_id}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting paper embedding from ChromaDB for {doc_id}: {e}")
        return None

def find_similar_papers_vectordb(query_embedding: np.ndarray, n_results: int = 10, 
                                filters: dict = None) -> List[dict]:
    """
    Find similar papers using ChromaDB vector search
    
    Args:
        query_embedding: np.ndarray, query embedding vector
        n_results: int, number of results to return
        filters: dict, metadata filters
    
    Returns:
        List[dict]: similar papers with metadata and similarity scores
    """
    try:
        vector_db = get_vector_db()
        
        results = vector_db.find_similar_papers(
            query_embedding.tolist(),
            n_results=n_results,
            filters=filters
        )
        
        # Format results
        similar_papers = []
        if results['ids'] and len(results['ids'][0]) > 0:
            for i in range(len(results['ids'][0])):
                paper_data = {
                    'doc_id': results['ids'][0][i],
                    'similarity': 1.0 - results['distances'][0][i],  # Convert distance to similarity
                    'metadata': results['metadatas'][0][i] if results['metadatas'] else {}
                }
                similar_papers.append(paper_data)
        
        logger.info(f"✅ Found {len(similar_papers)} similar papers in ChromaDB")
        return similar_papers
        
    except Exception as e:
        logger.error(f"Error finding similar papers in ChromaDB: {e}")
        return []

def check_duplicate_by_similarity(embedding: np.ndarray, similarity_threshold: float = 0.95) -> Optional[str]:
    """
    Check for duplicate papers using embedding similarity
    
    Args:
        embedding: np.ndarray, query embedding
        similarity_threshold: float, threshold for considering papers as duplicates
    
    Returns:
        str: existing document ID if duplicate found, None otherwise
    """
    try:
        similar_papers = find_similar_papers_vectordb(embedding, n_results=1)
        
        if similar_papers and similar_papers[0]['similarity'] >= similarity_threshold:
            duplicate_doc_id = similar_papers[0]['doc_id']
            similarity_score = similar_papers[0]['similarity']
            
            logger.warning(f"🔍 Duplicate paper detected: {duplicate_doc_id} (similarity: {similarity_score:.3f})")
            return duplicate_doc_id
        
        return None
        
    except Exception as e:
        logger.error(f"Error checking for duplicates: {e}")
        return None

def process_text_for_embedding(text: str, max_length: int = 50000) -> str:
    """
    Preprocess and truncate text for embedding generation
    
    Args:
        text: str, input text
        max_length: int, maximum text length to process
        
    Returns:
        str: processed text ready for embedding
    """
    if not text:
        return ""
    
    # Basic cleaning
    text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
    text = text.strip()
    
    # Truncate if too long
    if len(text) > max_length:
        text = text[:max_length]
        logger.info(f"Text truncated to {max_length} characters")
    
    return text