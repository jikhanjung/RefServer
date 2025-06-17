import os
import logging
import requests
import json
import base64
from typing import Dict, Optional, Tuple
from PIL import Image
import io

logger = logging.getLogger(__name__)

class LLaVAQualityAssessor:
    """
    LLaVA-based OCR quality assessment using Ollama API
    """
    
    def __init__(self, ollama_host: str = None):
        """
        Initialize LLaVA quality assessor
        
        Args:
            ollama_host: str, Ollama server host (default from env)
        """
        self.ollama_host = ollama_host or os.getenv('OLLAMA_HOST', 'localhost:11434')
        if not self.ollama_host.startswith('http'):
            self.ollama_host = f"http://{self.ollama_host}"
        
        self.model_name = "llava"
        self.api_url = f"{self.ollama_host}/api/generate"
        
        logger.info(f"Initialized LLaVA assessor with host: {self.ollama_host}")
    
    def _encode_image_to_base64(self, image_path: str) -> str:
        """
        Encode image to base64 string for API request
        
        Args:
            image_path: str, path to image file
            
        Returns:
            str: base64 encoded image
        """
        try:
            # Open and potentially resize image
            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Resize if too large (max 1024x1024 for performance)
                max_size = 1024
                if img.width > max_size or img.height > max_size:
                    img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                    logger.info(f"Resized image to {img.size}")
                
                # Convert to bytes
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=95)
                buffer.seek(0)
                
                # Encode to base64
                image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                
                return image_base64
                
        except Exception as e:
            logger.error(f"Error encoding image {image_path}: {e}")
            raise
    
    def _create_quality_prompt(self) -> str:
        """
        Create prompt for OCR quality assessment
        
        Returns:
            str: assessment prompt
        """
        prompt = """Analyze this document page image and assess the OCR quality and readability. 

Please evaluate:
1. Text clarity and sharpness
2. Image resolution and quality
3. Presence of scan artifacts, noise, or distortion
4. Text orientation and alignment
5. Overall readability for OCR processing

Provide your assessment in the following JSON format:
{
    "overall_quality": "excellent|good|fair|poor",
    "text_clarity": "excellent|good|fair|poor",
    "image_quality": "excellent|good|fair|poor", 
    "scan_artifacts": "none|minimal|moderate|severe",
    "readability_score": 0-100,
    "issues": ["list", "of", "identified", "issues"],
    "recommendations": ["list", "of", "improvement", "suggestions"],
    "confidence": 0-100
}

Be specific about any issues you observe and provide actionable recommendations."""
        
        return prompt
    
    def _parse_llava_response(self, response_text: str) -> Dict:
        """
        Parse LLaVA response and extract structured assessment
        
        Args:
            response_text: str, raw response from LLaVA
            
        Returns:
            Dict: parsed assessment data
        """
        try:
            # Try to find JSON in the response
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(0)
                assessment = json.loads(json_str)
                
                # Validate required fields
                required_fields = ['overall_quality', 'readability_score', 'confidence']
                for field in required_fields:
                    if field not in assessment:
                        assessment[field] = 'unknown' if field == 'overall_quality' else 50
                
                return assessment
            else:
                # Fallback parsing
                logger.warning("Could not find JSON in LLaVA response, using fallback parsing")
                return self._fallback_parse_response(response_text)
                
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parsing failed: {e}, using fallback parsing")
            return self._fallback_parse_response(response_text)
        except Exception as e:
            logger.error(f"Error parsing LLaVA response: {e}")
            return self._create_default_assessment()
    
    def _fallback_parse_response(self, response_text: str) -> Dict:
        """
        Fallback parsing when JSON extraction fails
        
        Args:
            response_text: str, raw response text
            
        Returns:
            Dict: basic assessment data
        """
        response_lower = response_text.lower()
        
        # Determine overall quality based on keywords
        if any(word in response_lower for word in ['excellent', 'very good', 'high quality']):
            quality = 'excellent'
            score = 85
        elif any(word in response_lower for word in ['good', 'clear', 'readable']):
            quality = 'good'
            score = 70
        elif any(word in response_lower for word in ['fair', 'okay', 'moderate']):
            quality = 'fair'
            score = 55
        elif any(word in response_lower for word in ['poor', 'bad', 'low quality', 'blurry']):
            quality = 'poor'
            score = 30
        else:
            quality = 'fair'
            score = 50
        
        # Extract issues
        issues = []
        if 'blur' in response_lower:
            issues.append('blurry_text')
        if 'noise' in response_lower:
            issues.append('image_noise')
        if 'dark' in response_lower or 'low contrast' in response_lower:
            issues.append('low_contrast')
        if 'skew' in response_lower or 'rotated' in response_lower:
            issues.append('text_skew')
        
        return {
            'overall_quality': quality,
            'text_clarity': quality,
            'image_quality': quality,
            'scan_artifacts': 'moderate' if issues else 'minimal',
            'readability_score': score,
            'issues': issues,
            'recommendations': ['Consider rescanning at higher resolution'] if score < 60 else [],
            'confidence': 70,
            'raw_response': response_text
        }
    
    def _create_default_assessment(self) -> Dict:
        """
        Create default assessment when analysis fails
        
        Returns:
            Dict: default assessment data
        """
        return {
            'overall_quality': 'unknown',
            'text_clarity': 'unknown',
            'image_quality': 'unknown',
            'scan_artifacts': 'unknown',
            'readability_score': 50,
            'issues': ['analysis_failed'],
            'recommendations': ['Manual review recommended'],
            'confidence': 0,
            'error': 'Assessment failed'
        }
    
    def assess_image_quality(self, image_path: str, timeout: int = 60) -> Dict:
        """
        Assess OCR quality of document image using LLaVA
        
        Args:
            image_path: str, path to document image
            timeout: int, request timeout in seconds
            
        Returns:
            Dict: quality assessment results
        """
        try:
            if not os.path.exists(image_path):
                logger.error(f"Image file not found: {image_path}")
                return self._create_default_assessment()
            
            logger.info(f"Starting quality assessment for: {image_path}")
            
            # Encode image
            image_base64 = self._encode_image_to_base64(image_path)
            
            # Prepare request
            request_data = {
                "model": self.model_name,
                "prompt": self._create_quality_prompt(),
                "images": [image_base64],
                "stream": False,
                "options": {
                    "temperature": 0.1,  # Low temperature for consistent results
                    "top_p": 0.9,
                    "max_tokens": 1000
                }
            }
            
            # Make API request
            logger.info("Sending request to LLaVA...")
            response = requests.post(
                self.api_url,
                json=request_data,
                timeout=timeout,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                response_data = response.json()
                response_text = response_data.get('response', '')
                
                logger.info("LLaVA analysis completed successfully")
                
                # Parse response
                assessment = self._parse_llava_response(response_text)
                assessment['analysis_time'] = response_data.get('total_duration', 0) / 1e9  # Convert to seconds
                assessment['model_used'] = self.model_name
                
                return assessment
            else:
                logger.error(f"LLaVA API request failed: {response.status_code} - {response.text}")
                return self._create_default_assessment()
                
        except requests.RequestException as e:
            logger.error(f"Network error during LLaVA request: {e}")
            return self._create_default_assessment()
        except Exception as e:
            logger.error(f"Unexpected error in quality assessment: {e}")
            return self._create_default_assessment()
    
    def check_ollama_connection(self) -> bool:
        """
        Check if Ollama server is accessible and LLaVA model is available
        
        Returns:
            bool: True if connection is successful
        """
        try:
            # Check server health
            health_url = f"{self.ollama_host}/api/tags"
            response = requests.get(health_url, timeout=10)
            
            if response.status_code == 200:
                models_data = response.json()
                models = [model.get('name', '') for model in models_data.get('models', [])]
                
                # Check if LLaVA model is available
                llava_available = any('llava' in model.lower() for model in models)
                
                if llava_available:
                    logger.info("Ollama connection successful, LLaVA model available")
                    return True
                else:
                    logger.error(f"LLaVA model not found. Available models: {models}")
                    return False
            else:
                logger.error(f"Ollama server not responding: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to Ollama: {e}")
            return False

# Global assessor instance
_quality_assessor = None

def get_quality_assessor() -> LLaVAQualityAssessor:
    """
    Get global quality assessor instance (singleton)
    
    Returns:
        LLaVAQualityAssessor: assessor instance
    """
    global _quality_assessor
    
    if _quality_assessor is None:
        _quality_assessor = LLaVAQualityAssessor()
    
    return _quality_assessor

def assess_document_quality(image_path: str) -> Tuple[str, Dict]:
    """
    Assess document image quality for OCR processing
    
    Args:
        image_path: str, path to document image
        
    Returns:
        Tuple[str, Dict]: (quality_summary, detailed_assessment)
    """
    try:
        assessor = get_quality_assessor()
        
        # Perform assessment
        assessment = assessor.assess_image_quality(image_path)
        
        # Create summary
        overall_quality = assessment.get('overall_quality', 'unknown')
        readability_score = assessment.get('readability_score', 50)
        confidence = assessment.get('confidence', 0)
        
        quality_summary = f"{overall_quality}|score:{readability_score}|confidence:{confidence}"
        
        logger.info(f"Quality assessment completed: {quality_summary}")
        
        return quality_summary, assessment
        
    except Exception as e:
        logger.error(f"Error in document quality assessment: {e}")
        return "error|score:0|confidence:0", {'error': str(e)}

def is_quality_assessment_available() -> bool:
    """
    Check if quality assessment service is available
    
    Returns:
        bool: True if service is available
    """
    try:
        assessor = get_quality_assessor()
        return assessor.check_ollama_connection()
    except Exception as e:
        logger.error(f"Error checking quality assessment availability: {e}")
        return False

def get_quality_score_interpretation(score: int) -> str:
    """
    Interpret quality score and provide recommendation
    
    Args:
        score: int, quality score (0-100)
        
    Returns:
        str: interpretation and recommendation
    """
    if score >= 80:
        return "Excellent quality - optimal for OCR processing"
    elif score >= 65:
        return "Good quality - suitable for OCR with high accuracy"
    elif score >= 50:
        return "Fair quality - OCR possible but may have some errors"
    elif score >= 30:
        return "Poor quality - OCR results may be unreliable"
    else:
        return "Very poor quality - consider rescanning or preprocessing"