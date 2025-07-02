import os
import logging
import requests
import json
from typing import Dict, List, Optional, Tuple
import time
from pathlib import Path

from retry_utils import async_retry, sync_retry, HURIDOCS_RETRY_CONFIG, RetryError
from service_circuit_breaker import get_circuit_breaker_manager, CircuitBreakerOpenError

logger = logging.getLogger(__name__)

class HuridocsLayoutAnalyzer:
    """
    Huridocs PDF layout analysis using external layout analysis service
    """
    
    def __init__(self, service_url: str = None):
        """
        Initialize Huridocs layout analyzer
        
        Args:
            service_url: str, Huridocs layout service URL (default from env)
        """
        self.service_url = service_url or os.getenv('HURIDOCS_LAYOUT_URL', 'http://huridocs-layout:5000')
        
        # Check if service is disabled
        if self.service_url.lower() in ['disabled', 'false', 'none', '']:
            self.enabled = False
            logger.info("Huridocs layout analysis disabled (CPU-only mode)")
            return
        
        self.enabled = True
        self.analyze_url = f"{self.service_url}/"  # Main endpoint is POST /
        self.status_url = f"{self.service_url}/info"  # Status endpoint is /info
        
        logger.info(f"Initialized Huridocs layout analyzer with URL: {self.service_url}")
    
    def check_service_health(self) -> bool:
        """
        Check if Huridocs layout service is available
        Uses circuit breaker to prevent repeated failed attempts
        
        Returns:
            bool: True if service is healthy
        """
        # Check if service is enabled
        if not getattr(self, 'enabled', True):
            logger.debug("Huridocs layout service is disabled")
            return False
        
        try:
            # Use circuit breaker to manage connection attempts
            circuit_manager = get_circuit_breaker_manager()
            breaker = circuit_manager.get_breaker("huridocs_layout")
            
            def check_health():
                response = sync_retry(
                    lambda: requests.get(self.status_url, timeout=10),
                    config=HURIDOCS_RETRY_CONFIG
                )
                
                if response.status_code == 200:
                    logger.debug("Huridocs layout service is healthy")
                    return True
                else:
                    raise Exception(f"Huridocs service returned status {response.status_code}")
            
            # Execute with circuit breaker protection
            return breaker.call(check_health)
            
        except CircuitBreakerOpenError as e:
            logger.debug(f"Huridocs layout service disabled by circuit breaker: {e}")
            return False
        except RetryError as e:
            logger.error(f"Huridocs health check failed after retries: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Huridocs service: {e}")
            return False
    
    def analyze_pdf_layout(self, pdf_path: str, timeout: int = 600) -> Dict:
        """
        Analyze PDF layout using Huridocs service
        
        Args:
            pdf_path: str, path to PDF file
            timeout: int, request timeout in seconds
            
        Returns:
            Dict: layout analysis results
        """
        # Check if service is enabled
        if not getattr(self, 'enabled', True):
            logger.info("Huridocs layout analysis skipped (disabled)")
            return self._create_disabled_result()
            
        try:
            if not os.path.exists(pdf_path):
                logger.error(f"PDF file not found: {pdf_path}")
                return self._create_error_result(f"File not found: {pdf_path}")
            
            # Check file size (skip files larger than 50MB to prevent OOM)
            file_size = os.path.getsize(pdf_path)
            file_size_mb = file_size / (1024 * 1024)
            max_size_mb = 50  # 50MB limit
            
            if file_size_mb > max_size_mb:
                logger.warning(f"PDF file too large for layout analysis: {file_size_mb:.1f}MB (max: {max_size_mb}MB)")
                return self._create_error_result(f"File too large: {file_size_mb:.1f}MB (max: {max_size_mb}MB)")
            
            logger.info(f"Starting layout analysis for: {pdf_path} ({file_size_mb:.1f}MB)")
            
            # Prepare file for upload and make request with retry
            logger.info("Sending PDF to Huridocs layout service...")
            
            def make_layout_request():
                with open(pdf_path, 'rb') as pdf_file:
                    files = {
                        'file': (os.path.basename(pdf_path), pdf_file, 'application/pdf')
                    }
                    return requests.post(
                        self.analyze_url,
                        files=files,
                        timeout=timeout
                    )
            
            try:
                response = sync_retry(make_layout_request, config=HURIDOCS_RETRY_CONFIG)
            except RetryError as e:
                logger.error(f"Huridocs layout request failed after retries: {e}")
                return self._create_error_result(f"Layout analysis failed after retries: {str(e)}")
            
            if response.status_code == 200:
                try:
                    layout_data = response.json()
                    logger.info("Layout analysis completed successfully")
                    
                    # Process and validate the response
                    processed_result = self._process_layout_response(layout_data)
                    return processed_result
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse layout analysis response: {e}")
                    return self._create_error_result("Invalid JSON response from layout service")
            else:
                logger.error(f"Layout analysis failed: {response.status_code} - {response.text}")
                return self._create_error_result(f"Service error: {response.status_code}")
                
        except requests.Timeout:
            logger.error("Layout analysis timed out")
            return self._create_error_result("Analysis timeout")
        except requests.RequestException as e:
            logger.error(f"Network error during layout analysis: {e}")
            return self._create_error_result(f"Network error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in layout analysis: {e}")
            return self._create_error_result(f"Unexpected error: {str(e)}")
    
    def _process_layout_response(self, raw_data: Dict) -> Dict:
        """
        Process and validate layout analysis response
        
        Args:
            raw_data: Dict, raw response from Huridocs service
            
        Returns:
            Dict: processed layout data
        """
        try:
            # Extract basic information
            pages = raw_data.get('pages', [])
            page_count = len(pages)
            
            # Process page elements
            processed_pages = []
            total_elements = 0
            
            for page_idx, page_data in enumerate(pages):
                page_info = {
                    'page_number': page_idx + 1,
                    'width': page_data.get('width', 0),
                    'height': page_data.get('height', 0),
                    'elements': []
                }
                
                # Process elements (text blocks, images, etc.)
                elements = page_data.get('elements', [])
                
                # Handle case where elements might be a dict instead of list
                if isinstance(elements, dict):
                    # Convert dict to list of values if needed
                    elements = list(elements.values()) if elements else []
                elif not isinstance(elements, list):
                    # If it's neither dict nor list, treat as empty
                    elements = []
                
                for element in elements:
                    element_info = {
                        'type': element.get('type', 'unknown'),
                        'bbox': element.get('bbox', [0, 0, 0, 0]),  # [x1, y1, x2, y2]
                        'confidence': element.get('confidence', 0.0),
                        'text': element.get('text', ''),
                        'properties': element.get('properties', {})
                    }
                    
                    page_info['elements'].append(element_info)
                    total_elements += 1
                
                processed_pages.append(page_info)
            
            # Create summary statistics
            element_types = {}
            for page in processed_pages:
                for element in page['elements']:
                    elem_type = element['type']
                    element_types[elem_type] = element_types.get(elem_type, 0) + 1
            
            # Build final result
            result = {
                'success': True,
                'page_count': page_count,
                'total_elements': total_elements,
                'element_types': element_types,
                'pages': processed_pages,
                'processing_info': {
                    'service': 'huridocs',
                    'timestamp': time.time(),
                    'version': raw_data.get('version', 'unknown')
                },
                'raw_data': raw_data  # Keep original for debugging
            }
            
            logger.info(f"Processed layout analysis: {page_count} pages, {total_elements} elements")
            logger.info(f"Element types found: {element_types}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing layout response: {e}")
            return self._create_error_result(f"Processing error: {str(e)}")
    
    def _create_error_result(self, error_message: str) -> Dict:
        """
        Create standardized error result
        
        Args:
            error_message: str, error description
            
        Returns:
            Dict: error result structure
        """
        return {
            'success': False,
            'error': error_message,
            'page_count': 0,
            'total_elements': 0,
            'element_types': {},
            'pages': [],
            'processing_info': {
                'service': 'huridocs',
                'timestamp': time.time(),
                'error': True
            }
        }
    
    def _create_disabled_result(self) -> Dict:
        """
        Create result when service is disabled
        
        Returns:
            Dict: disabled service result structure
        """
        return {
            'success': False,
            'error': 'Layout analysis service disabled (CPU-only mode)',
            'page_count': 0,
            'total_elements': 0,
            'element_types': {},
            'pages': [],
            'processing_info': {
                'service': 'huridocs',
                'timestamp': time.time(),
                'status': 'disabled',
                'reason': 'CPU-only mode - layout analysis requires GPU acceleration'
            }
        }
    
    def extract_text_blocks(self, layout_data: Dict) -> List[Dict]:
        """
        Extract text blocks from layout analysis
        
        Args:
            layout_data: Dict, processed layout data
            
        Returns:
            List[Dict]: text blocks with positions and content
        """
        text_blocks = []
        
        if not layout_data.get('success', False):
            return text_blocks
        
        try:
            for page in layout_data.get('pages', []):
                page_number = page.get('page_number', 0)
                
                for element in page.get('elements', []):
                    if element.get('type') in ['text', 'paragraph', 'heading', 'title']:
                        text_block = {
                            'page': page_number,
                            'type': element.get('type'),
                            'text': element.get('text', ''),
                            'bbox': element.get('bbox', [0, 0, 0, 0]),
                            'confidence': element.get('confidence', 0.0)
                        }
                        
                        if text_block['text'].strip():  # Only include non-empty text
                            text_blocks.append(text_block)
            
            logger.info(f"Extracted {len(text_blocks)} text blocks from layout")
            return text_blocks
            
        except Exception as e:
            logger.error(f"Error extracting text blocks: {e}")
            return []
    
    def extract_figures_and_tables(self, layout_data: Dict) -> List[Dict]:
        """
        Extract figures and tables from layout analysis
        
        Args:
            layout_data: Dict, processed layout data
            
        Returns:
            List[Dict]: figures and tables with positions
        """
        figures_tables = []
        
        if not layout_data.get('success', False):
            return figures_tables
        
        try:
            for page in layout_data.get('pages', []):
                page_number = page.get('page_number', 0)
                
                for element in page.get('elements', []):
                    element_type = element.get('type', '')
                    
                    if element_type in ['figure', 'image', 'table']:
                        item = {
                            'page': page_number,
                            'type': element_type,
                            'bbox': element.get('bbox', [0, 0, 0, 0]),
                            'confidence': element.get('confidence', 0.0),
                            'properties': element.get('properties', {})
                        }
                        
                        # Add caption if available
                        if 'caption' in element.get('properties', {}):
                            item['caption'] = element['properties']['caption']
                        
                        figures_tables.append(item)
            
            logger.info(f"Extracted {len(figures_tables)} figures/tables from layout")
            return figures_tables
            
        except Exception as e:
            logger.error(f"Error extracting figures/tables: {e}")
            return []

# Global analyzer instance
_layout_analyzer = None

def get_layout_analyzer() -> HuridocsLayoutAnalyzer:
    """
    Get global layout analyzer instance (singleton)
    
    Returns:
        HuridocsLayoutAnalyzer: analyzer instance
    """
    global _layout_analyzer
    
    if _layout_analyzer is None:
        _layout_analyzer = HuridocsLayoutAnalyzer()
    
    return _layout_analyzer

def analyze_pdf_layout(pdf_path: str) -> Tuple[Dict, bool]:
    """
    Analyze PDF layout structure
    
    Args:
        pdf_path: str, path to PDF file
        
    Returns:
        Tuple[Dict, bool]: (layout_data, success)
    """
    try:
        analyzer = get_layout_analyzer()
        
        # Perform layout analysis
        layout_data = analyzer.analyze_pdf_layout(pdf_path)
        
        success = layout_data.get('success', False)
        
        if success:
            page_count = layout_data.get('page_count', 0)
            total_elements = layout_data.get('total_elements', 0)
            logger.info(f"Layout analysis successful: {page_count} pages, {total_elements} elements")
        else:
            error = layout_data.get('error', 'Unknown error')
            logger.error(f"Layout analysis failed: {error}")
        
        return layout_data, success
        
    except Exception as e:
        logger.error(f"Error in PDF layout analysis: {e}")
        return {
            'success': False,
            'error': str(e),
            'page_count': 0,
            'total_elements': 0,
            'element_types': {},
            'pages': []
        }, False

def is_layout_service_available() -> bool:
    """
    Check if layout analysis service is available
    
    Returns:
        bool: True if service is available
    """
    try:
        analyzer = get_layout_analyzer()
        return analyzer.check_service_health()
    except Exception as e:
        logger.error(f"Error checking layout service availability: {e}")
        return False

def get_layout_summary(layout_data: Dict) -> str:
    """
    Generate human-readable summary of layout analysis
    
    Args:
        layout_data: Dict, layout analysis results
        
    Returns:
        str: summary description
    """
    if not layout_data.get('success', False):
        return f"Layout analysis failed: {layout_data.get('error', 'Unknown error')}"
    
    page_count = layout_data.get('page_count', 0)
    total_elements = layout_data.get('total_elements', 0)
    element_types = layout_data.get('element_types', {})
    
    summary_parts = [f"{page_count} pages", f"{total_elements} elements"]
    
    if element_types:
        type_summary = []
        for elem_type, count in element_types.items():
            type_summary.append(f"{count} {elem_type}")
        summary_parts.append(f"({', '.join(type_summary)})")
    
    return " | ".join(summary_parts)