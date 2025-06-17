import os
import logging
import requests
import json
import re
from typing import Dict, List, Optional, Tuple
import time

logger = logging.getLogger(__name__)

class MetadataExtractor:
    """
    LLM-based bibliographic metadata extraction using Ollama API
    """
    
    def __init__(self, ollama_host: str = None, model_name: str = "llama3.2"):
        """
        Initialize metadata extractor
        
        Args:
            ollama_host: str, Ollama server host (default from env)
            model_name: str, LLM model name to use
        """
        self.ollama_host = ollama_host or os.getenv('OLLAMA_HOST', 'localhost:11434')
        if not self.ollama_host.startswith('http'):
            self.ollama_host = f"http://{self.ollama_host}"
        
        self.model_name = model_name
        self.api_url = f"{self.ollama_host}/api/generate"
        
        logger.info(f"Initialized metadata extractor with host: {self.ollama_host}")
        logger.info(f"Using model: {self.model_name}")
    
    def _create_extraction_prompt(self, text_content: str) -> str:
        """
        Create prompt for metadata extraction
        
        Args:
            text_content: str, paper text content
            
        Returns:
            str: extraction prompt
        """
        prompt = f"""Analyze the following academic paper text and extract bibliographic metadata. Focus on the first few pages which typically contain the title, authors, and publication information.

Text content:
{text_content[:4000]}...

Please extract the following information and format as JSON:

{{
    "title": "exact paper title",
    "authors": ["First Author", "Second Author", "Third Author"],
    "journal": "journal or conference name",
    "year": 2024,
    "doi": "10.xxxx/xxxxx",
    "abstract": "paper abstract text",
    "keywords": ["keyword1", "keyword2", "keyword3"],
    "volume": "volume number if available",
    "issue": "issue number if available",
    "pages": "page range like 123-145",
    "publisher": "publisher name if available",
    "institution": "primary author institution",
    "email": "corresponding author email if available"
}}

Guidelines:
1. Extract the exact title without modifications
2. List all authors in order of appearance
3. For journal name, use the full official name
4. Year should be the publication year (integer)
5. DOI should be the complete DOI string if found
6. Abstract should be the complete abstract text
7. Keywords should be extracted from the paper or inferred from content
8. If information is not available, use null for strings/arrays or 0 for numbers
9. Be precise and accurate - this is bibliographic data

Return only the JSON object, no additional text."""
        
        return prompt
    
    def _create_fallback_prompt(self, text_content: str) -> str:
        """
        Create simpler fallback prompt when main extraction fails
        
        Args:
            text_content: str, paper text content
            
        Returns:
            str: fallback prompt
        """
        prompt = f"""Extract basic information from this academic paper:

{text_content[:2000]}

Provide:
- Title: [exact title]
- Authors: [author names separated by semicolons]
- Year: [publication year]
- Journal: [journal/conference name]
- Abstract: [first sentence of abstract if found]

Be concise and accurate."""
        
        return prompt
    
    def extract_metadata_from_text(self, text_content: str, timeout: int = 120) -> Dict:
        """
        Extract metadata from paper text using LLM
        
        Args:
            text_content: str, extracted text from PDF
            timeout: int, request timeout in seconds
            
        Returns:
            Dict: extracted metadata
        """
        try:
            if not text_content or len(text_content.strip()) < 100:
                logger.warning("Text content too short for metadata extraction")
                return self._create_empty_metadata("Text too short")
            
            logger.info("Starting metadata extraction with LLM")
            
            # Try main extraction first
            result = self._extract_with_prompt(
                self._create_extraction_prompt(text_content), 
                timeout
            )
            
            if result.get('success', False):
                return result
            
            # Fallback to simpler extraction
            logger.info("Main extraction failed, trying fallback method")
            fallback_result = self._extract_with_fallback(text_content, timeout)
            
            return fallback_result
            
        except Exception as e:
            logger.error(f"Error in metadata extraction: {e}")
            return self._create_empty_metadata(f"Extraction error: {str(e)}")
    
    def _extract_with_prompt(self, prompt: str, timeout: int) -> Dict:
        """
        Extract metadata using main structured prompt
        
        Args:
            prompt: str, extraction prompt
            timeout: int, timeout in seconds
            
        Returns:
            Dict: extraction result
        """
        try:
            # Prepare request
            request_data = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,  # Low temperature for consistent results
                    "top_p": 0.9,
                    "max_tokens": 2000
                }
            }
            
            # Make API request
            logger.info("Sending metadata extraction request to LLM...")
            response = requests.post(
                self.api_url,
                json=request_data,
                timeout=timeout,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                response_data = response.json()
                response_text = response_data.get('response', '')
                
                logger.info("LLM metadata extraction completed")
                
                # Parse JSON response
                metadata = self._parse_llm_response(response_text)
                
                if metadata:
                    metadata['extraction_method'] = 'structured_llm'
                    metadata['model_used'] = self.model_name
                    metadata['success'] = True
                    return metadata
                else:
                    return {'success': False, 'error': 'Failed to parse LLM response'}
            else:
                logger.error(f"LLM API request failed: {response.status_code}")
                return {'success': False, 'error': f'API error: {response.status_code}'}
                
        except requests.Timeout:
            logger.error("LLM request timed out")
            return {'success': False, 'error': 'Request timeout'}
        except Exception as e:
            logger.error(f"Error in LLM extraction: {e}")
            return {'success': False, 'error': str(e)}
    
    def _extract_with_fallback(self, text_content: str, timeout: int) -> Dict:
        """
        Extract metadata using fallback method
        
        Args:
            text_content: str, paper text
            timeout: int, timeout in seconds
            
        Returns:
            Dict: extracted metadata
        """
        try:
            # Try LLM fallback first
            prompt = self._create_fallback_prompt(text_content)
            
            request_data = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "max_tokens": 800
                }
            }
            
            response = requests.post(
                self.api_url,
                json=request_data,
                timeout=timeout//2,  # Shorter timeout for fallback
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                response_data = response.json()
                response_text = response_data.get('response', '')
                
                # Parse fallback response
                metadata = self._parse_fallback_response(response_text)
                metadata['extraction_method'] = 'fallback_llm'
                metadata['model_used'] = self.model_name
                metadata['success'] = True
                return metadata
            
        except Exception as e:
            logger.warning(f"LLM fallback failed: {e}")
        
        # Final fallback: rule-based extraction
        logger.info("Using rule-based fallback extraction")
        metadata = self._rule_based_extraction(text_content)
        metadata['extraction_method'] = 'rule_based'
        metadata['success'] = True
        return metadata
    
    def _parse_llm_response(self, response_text: str) -> Optional[Dict]:
        """
        Parse structured JSON response from LLM
        
        Args:
            response_text: str, LLM response
            
        Returns:
            Optional[Dict]: parsed metadata or None
        """
        try:
            # Find JSON in response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(0)
                metadata = json.loads(json_str)
                
                # Validate and clean metadata
                cleaned_metadata = self._validate_and_clean_metadata(metadata)
                return cleaned_metadata
            else:
                logger.warning("No JSON found in LLM response")
                return None
                
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON from LLM: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            return None
    
    def _parse_fallback_response(self, response_text: str) -> Dict:
        """
        Parse fallback response from LLM
        
        Args:
            response_text: str, LLM response
            
        Returns:
            Dict: basic metadata
        """
        metadata = self._create_empty_metadata()
        
        try:
            lines = response_text.split('\n')
            
            for line in lines:
                line = line.strip()
                
                if line.startswith('Title:'):
                    title = line.replace('Title:', '').strip()
                    if title and title != '[exact title]':
                        metadata['title'] = title
                
                elif line.startswith('Authors:'):
                    authors_str = line.replace('Authors:', '').strip()
                    if authors_str and authors_str != '[author names separated by semicolons]':
                        authors = [auth.strip() for auth in authors_str.split(';')]
                        metadata['authors'] = [auth for auth in authors if auth]
                
                elif line.startswith('Year:'):
                    year_str = line.replace('Year:', '').strip()
                    try:
                        year = int(re.search(r'\d{4}', year_str).group())
                        metadata['year'] = year
                    except:
                        pass
                
                elif line.startswith('Journal:'):
                    journal = line.replace('Journal:', '').strip()
                    if journal and journal != '[journal/conference name]':
                        metadata['journal'] = journal
                
                elif line.startswith('Abstract:'):
                    abstract = line.replace('Abstract:', '').strip()
                    if abstract and abstract != '[first sentence of abstract if found]':
                        metadata['abstract'] = abstract
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error parsing fallback response: {e}")
            return metadata
    
    def _rule_based_extraction(self, text_content: str) -> Dict:
        """
        Rule-based metadata extraction as final fallback
        
        Args:
            text_content: str, paper text
            
        Returns:
            Dict: basic metadata
        """
        metadata = self._create_empty_metadata()
        
        try:
            lines = text_content.split('\n')[:50]  # First 50 lines
            
            # Extract title (usually first non-empty line or largest text)
            for line in lines:
                line = line.strip()
                if len(line) > 20 and not line.startswith(('Abstract', 'Keywords', '1.', 'I.')):
                    if not metadata.get('title'):
                        metadata['title'] = line
                        break
            
            # Extract year using regex
            year_matches = re.findall(r'\b(20\d{2})\b', text_content[:2000])
            if year_matches:
                metadata['year'] = int(year_matches[0])
            
            # Extract email addresses for potential author contact
            email_matches = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text_content[:3000])
            if email_matches:
                metadata['email'] = email_matches[0]
            
            # Extract DOI
            doi_match = re.search(r'10\.\d{4,}/[^\s]+', text_content[:2000])
            if doi_match:
                metadata['doi'] = doi_match.group(0)
            
            # Extract abstract
            abstract_match = re.search(r'Abstract[:\s]+(.+?)(?:\n\n|Keywords|1\.|Introduction)', text_content, re.DOTALL | re.IGNORECASE)
            if abstract_match:
                abstract = abstract_match.group(1).strip()
                if len(abstract) > 50:
                    metadata['abstract'] = abstract[:500]  # Limit length
            
            logger.info("Rule-based extraction completed")
            return metadata
            
        except Exception as e:
            logger.error(f"Error in rule-based extraction: {e}")
            return metadata
    
    def _validate_and_clean_metadata(self, metadata: Dict) -> Dict:
        """
        Validate and clean extracted metadata
        
        Args:
            metadata: Dict, raw metadata
            
        Returns:
            Dict: cleaned metadata
        """
        cleaned = self._create_empty_metadata()
        
        try:
            # Title
            if metadata.get('title') and isinstance(metadata['title'], str):
                title = metadata['title'].strip()
                if title and title.lower() not in ['null', 'none', 'n/a']:
                    cleaned['title'] = title
            
            # Authors
            if metadata.get('authors'):
                if isinstance(metadata['authors'], list):
                    authors = [str(auth).strip() for auth in metadata['authors'] if auth]
                    authors = [auth for auth in authors if auth.lower() not in ['null', 'none', 'n/a']]
                    if authors:
                        cleaned['authors'] = authors
                elif isinstance(metadata['authors'], str):
                    # Handle case where authors is a string
                    authors_str = metadata['authors'].strip()
                    if authors_str and authors_str.lower() not in ['null', 'none', 'n/a']:
                        authors = [auth.strip() for auth in re.split(r'[,;]|and', authors_str)]
                        cleaned['authors'] = [auth for auth in authors if auth]
            
            # Year
            if metadata.get('year'):
                try:
                    year = int(metadata['year'])
                    if 1900 <= year <= 2030:
                        cleaned['year'] = year
                except:
                    pass
            
            # Journal
            if metadata.get('journal') and isinstance(metadata['journal'], str):
                journal = metadata['journal'].strip()
                if journal and journal.lower() not in ['null', 'none', 'n/a']:
                    cleaned['journal'] = journal
            
            # DOI
            if metadata.get('doi') and isinstance(metadata['doi'], str):
                doi = metadata['doi'].strip()
                if doi and doi.lower() not in ['null', 'none', 'n/a'] and '10.' in doi:
                    cleaned['doi'] = doi
            
            # Abstract
            if metadata.get('abstract') and isinstance(metadata['abstract'], str):
                abstract = metadata['abstract'].strip()
                if abstract and len(abstract) > 20 and abstract.lower() not in ['null', 'none', 'n/a']:
                    cleaned['abstract'] = abstract
            
            # Keywords
            if metadata.get('keywords'):
                if isinstance(metadata['keywords'], list):
                    keywords = [str(kw).strip() for kw in metadata['keywords'] if kw]
                    keywords = [kw for kw in keywords if kw.lower() not in ['null', 'none', 'n/a']]
                    if keywords:
                        cleaned['keywords'] = keywords
            
            # Other fields
            for field in ['volume', 'issue', 'pages', 'publisher', 'institution', 'email']:
                if metadata.get(field) and isinstance(metadata[field], str):
                    value = metadata[field].strip()
                    if value and value.lower() not in ['null', 'none', 'n/a']:
                        cleaned[field] = value
            
            return cleaned
            
        except Exception as e:
            logger.error(f"Error validating metadata: {e}")
            return cleaned
    
    def _create_empty_metadata(self, error: str = None) -> Dict:
        """
        Create empty metadata structure
        
        Args:
            error: str, optional error message
            
        Returns:
            Dict: empty metadata
        """
        metadata = {
            'title': None,
            'authors': [],
            'journal': None,
            'year': 0,
            'doi': None,
            'abstract': None,
            'keywords': [],
            'volume': None,
            'issue': None,
            'pages': None,
            'publisher': None,
            'institution': None,
            'email': None,
            'extraction_method': 'none',
            'success': False
        }
        
        if error:
            metadata['error'] = error
        
        return metadata
    
    def check_ollama_connection(self) -> bool:
        """
        Check if Ollama server is accessible and model is available
        
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
                
                # Check if our model is available
                model_available = any(self.model_name in model for model in models)
                
                if model_available:
                    logger.info(f"Ollama connection successful, {self.model_name} model available")
                    return True
                else:
                    logger.error(f"{self.model_name} model not found. Available models: {models}")
                    return False
            else:
                logger.error(f"Ollama server not responding: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to Ollama: {e}")
            return False

# Global extractor instance
_metadata_extractor = None

def get_metadata_extractor() -> MetadataExtractor:
    """
    Get global metadata extractor instance (singleton)
    
    Returns:
        MetadataExtractor: extractor instance
    """
    global _metadata_extractor
    
    if _metadata_extractor is None:
        _metadata_extractor = MetadataExtractor()
    
    return _metadata_extractor

def extract_paper_metadata(text_content: str) -> Tuple[Dict, bool]:
    """
    Extract bibliographic metadata from paper text
    
    Args:
        text_content: str, extracted text from PDF
        
    Returns:
        Tuple[Dict, bool]: (metadata, success)
    """
    try:
        extractor = get_metadata_extractor()
        
        # Perform metadata extraction
        metadata = extractor.extract_metadata_from_text(text_content)
        
        success = metadata.get('success', False)
        
        if success:
            title = metadata.get('title', 'Unknown')
            authors_count = len(metadata.get('authors', []))
            year = metadata.get('year', 0)
            method = metadata.get('extraction_method', 'unknown')
            
            logger.info(f"Metadata extraction successful: '{title}' by {authors_count} authors ({year}) using {method}")
        else:
            error = metadata.get('error', 'Unknown error')
            logger.error(f"Metadata extraction failed: {error}")
        
        return metadata, success
        
    except Exception as e:
        logger.error(f"Error in paper metadata extraction: {e}")
        return {
            'success': False,
            'error': str(e),
            'title': None,
            'authors': [],
            'extraction_method': 'error'
        }, False

def is_metadata_service_available() -> bool:
    """
    Check if metadata extraction service is available
    
    Returns:
        bool: True if service is available
    """
    try:
        extractor = get_metadata_extractor()
        return extractor.check_ollama_connection()
    except Exception as e:
        logger.error(f"Error checking metadata service availability: {e}")
        return False

def get_metadata_summary(metadata: Dict) -> str:
    """
    Generate human-readable summary of extracted metadata
    
    Args:
        metadata: Dict, extracted metadata
        
    Returns:
        str: summary description
    """
    if not metadata.get('success', False):
        return f"Metadata extraction failed: {metadata.get('error', 'Unknown error')}"
    
    title = metadata.get('title', 'Unknown Title')
    authors = metadata.get('authors', [])
    year = metadata.get('year', 0)
    journal = metadata.get('journal', 'Unknown Journal')
    method = metadata.get('extraction_method', 'unknown')
    
    # Truncate long titles
    if len(title) > 60:
        title = title[:57] + "..."
    
    authors_str = f"{len(authors)} authors" if authors else "No authors"
    year_str = str(year) if year > 0 else "Unknown year"
    
    return f"'{title}' | {authors_str} | {year_str} | {journal} | Method: {method}"