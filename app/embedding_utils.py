"""
Embedding comparison utilities for OCR quality assessment
"""

import numpy as np
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


def calculate_cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Calculate cosine similarity between two vectors
    
    Args:
        vec1: First embedding vector
        vec2: Second embedding vector
    
    Returns:
        float: Cosine similarity score between -1 and 1
    """
    try:
        # Convert to numpy arrays
        v1 = np.array(vec1)
        v2 = np.array(vec2)
        
        # Check dimensions match
        if v1.shape != v2.shape:
            logger.error(f"Vector dimensions don't match: {v1.shape} vs {v2.shape}")
            return 0.0
        
        # Calculate cosine similarity
        dot_product = np.dot(v1, v2)
        norm_v1 = np.linalg.norm(v1)
        norm_v2 = np.linalg.norm(v2)
        
        if norm_v1 == 0 or norm_v2 == 0:
            return 0.0
        
        cosine_sim = dot_product / (norm_v1 * norm_v2)
        return float(cosine_sim)
        
    except Exception as e:
        logger.error(f"Error calculating cosine similarity: {e}")
        return 0.0


def calculate_euclidean_distance(vec1: List[float], vec2: List[float]) -> float:
    """
    Calculate Euclidean distance between two vectors
    
    Args:
        vec1: First embedding vector
        vec2: Second embedding vector
    
    Returns:
        float: Euclidean distance (lower is more similar)
    """
    try:
        v1 = np.array(vec1)
        v2 = np.array(vec2)
        
        if v1.shape != v2.shape:
            logger.error(f"Vector dimensions don't match: {v1.shape} vs {v2.shape}")
            return float('inf')
        
        distance = np.linalg.norm(v1 - v2)
        return float(distance)
        
    except Exception as e:
        logger.error(f"Error calculating Euclidean distance: {e}")
        return float('inf')


def calculate_manhattan_distance(vec1: List[float], vec2: List[float]) -> float:
    """
    Calculate Manhattan (L1) distance between two vectors
    
    Args:
        vec1: First embedding vector
        vec2: Second embedding vector
    
    Returns:
        float: Manhattan distance (lower is more similar)
    """
    try:
        v1 = np.array(vec1)
        v2 = np.array(vec2)
        
        if v1.shape != v2.shape:
            logger.error(f"Vector dimensions don't match: {v1.shape} vs {v2.shape}")
            return float('inf')
        
        distance = np.sum(np.abs(v1 - v2))
        return float(distance)
        
    except Exception as e:
        logger.error(f"Error calculating Manhattan distance: {e}")
        return float('inf')


def compare_embeddings(old_embedding: List[float], new_embedding: List[float]) -> Dict[str, float]:
    """
    Compare two embeddings using multiple metrics
    
    Args:
        old_embedding: Original embedding vector
        new_embedding: New embedding vector after OCR
    
    Returns:
        dict: Comparison metrics
    """
    try:
        # Calculate various similarity/distance metrics
        cosine_sim = calculate_cosine_similarity(old_embedding, new_embedding)
        euclidean_dist = calculate_euclidean_distance(old_embedding, new_embedding)
        manhattan_dist = calculate_manhattan_distance(old_embedding, new_embedding)
        
        # Calculate percentage change in magnitude
        old_magnitude = np.linalg.norm(np.array(old_embedding))
        new_magnitude = np.linalg.norm(np.array(new_embedding))
        magnitude_change = ((new_magnitude - old_magnitude) / old_magnitude * 100) if old_magnitude > 0 else 0
        
        # Calculate element-wise statistics
        old_arr = np.array(old_embedding)
        new_arr = np.array(new_embedding)
        element_wise_diff = np.abs(new_arr - old_arr)
        
        return {
            'cosine_similarity': cosine_sim,
            'euclidean_distance': euclidean_dist,
            'manhattan_distance': manhattan_dist,
            'magnitude_change_percent': magnitude_change,
            'max_element_diff': float(np.max(element_wise_diff)),
            'mean_element_diff': float(np.mean(element_wise_diff)),
            'std_element_diff': float(np.std(element_wise_diff)),
            'similarity_score': cosine_sim * 100,  # Percentage similarity
            'is_significant_change': cosine_sim < 0.95  # Threshold for significant change
        }
        
    except Exception as e:
        logger.error(f"Error comparing embeddings: {e}")
        return {
            'error': str(e),
            'cosine_similarity': 0.0,
            'similarity_score': 0.0,
            'is_significant_change': False
        }


def analyze_text_quality_change(old_text: str, new_text: str) -> Dict[str, any]:
    """
    Analyze text quality changes between old and new OCR results
    
    Args:
        old_text: Original OCR text
        new_text: New OCR text
    
    Returns:
        dict: Text quality metrics
    """
    try:
        # Basic statistics
        old_chars = len(old_text)
        new_chars = len(new_text)
        char_diff = new_chars - old_chars
        char_change_percent = (char_diff / old_chars * 100) if old_chars > 0 else 0
        
        # Word count
        old_words = len(old_text.split())
        new_words = len(new_text.split())
        word_diff = new_words - old_words
        word_change_percent = (word_diff / old_words * 100) if old_words > 0 else 0
        
        # Line count
        old_lines = len(old_text.splitlines())
        new_lines = len(new_text.splitlines())
        line_diff = new_lines - old_lines
        
        # Character diversity (unique characters)
        old_unique_chars = len(set(old_text))
        new_unique_chars = len(set(new_text))
        
        # Estimate readability improvement
        # Simple heuristic: more words and reasonable character count suggests better OCR
        quality_score = 0
        if new_words > old_words:
            quality_score += 30
        if 0.8 <= (new_chars / old_chars) <= 1.2:  # Similar length is good
            quality_score += 20
        if new_unique_chars > old_unique_chars:
            quality_score += 20
        if abs(word_change_percent) < 50:  # Not too dramatic change
            quality_score += 30
        
        return {
            'old_char_count': old_chars,
            'new_char_count': new_chars,
            'char_diff': char_diff,
            'char_change_percent': char_change_percent,
            'old_word_count': old_words,
            'new_word_count': new_words,
            'word_diff': word_diff,
            'word_change_percent': word_change_percent,
            'old_line_count': old_lines,
            'new_line_count': new_lines,
            'line_diff': line_diff,
            'old_unique_chars': old_unique_chars,
            'new_unique_chars': new_unique_chars,
            'quality_score': quality_score,
            'quality_assessment': 'improved' if quality_score >= 70 else 'similar' if quality_score >= 40 else 'degraded'
        }
        
    except Exception as e:
        logger.error(f"Error analyzing text quality: {e}")
        return {
            'error': str(e),
            'quality_assessment': 'unknown'
        }


def create_embedding_comparison_report(
    old_embedding: Optional[List[float]], 
    new_embedding: Optional[List[float]],
    old_text: str,
    new_text: str
) -> Dict[str, any]:
    """
    Create a comprehensive embedding comparison report
    
    Args:
        old_embedding: Original embedding (can be None)
        new_embedding: New embedding (can be None)
        old_text: Original text
        new_text: New text after OCR
    
    Returns:
        dict: Comprehensive comparison report
    """
    report = {
        'has_old_embedding': old_embedding is not None,
        'has_new_embedding': new_embedding is not None,
        'text_analysis': analyze_text_quality_change(old_text, new_text)
    }
    
    if old_embedding and new_embedding:
        report['embedding_comparison'] = compare_embeddings(old_embedding, new_embedding)
        
        # Overall assessment
        embedding_sim = report['embedding_comparison']['cosine_similarity']
        text_quality = report['text_analysis']['quality_assessment']
        
        if embedding_sim > 0.95 and text_quality == 'similar':
            report['overall_assessment'] = 'minimal_change'
            report['recommendation'] = 'OCR produced similar results'
        elif embedding_sim > 0.85 and text_quality == 'improved':
            report['overall_assessment'] = 'minor_improvement'
            report['recommendation'] = 'OCR slightly improved text quality'
        elif embedding_sim < 0.85 and text_quality == 'improved':
            report['overall_assessment'] = 'significant_improvement'
            report['recommendation'] = 'OCR significantly improved text quality'
        elif text_quality == 'degraded':
            report['overall_assessment'] = 'quality_degraded'
            report['recommendation'] = 'Consider keeping original text'
        else:
            report['overall_assessment'] = 'changed'
            report['recommendation'] = 'Review changes carefully'
    else:
        report['overall_assessment'] = 'embedding_unavailable'
        report['recommendation'] = 'Cannot compare embeddings'
    
    return report