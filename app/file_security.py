"""
File upload security module for RefServer
Implements comprehensive file validation, size limits, and malicious file detection
"""

import os
import magic
import hashlib
import logging
import tempfile
import subprocess
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path
import mimetypes
import re
import zipfile
import tarfile
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class FileSecurityError(Exception):
    """Exception raised for file security violations"""
    pass


class FileSizeError(FileSecurityError):
    """Exception raised when file size exceeds limits"""
    pass


class FileTypeError(FileSecurityError):
    """Exception raised for invalid file types"""
    pass


class MaliciousFileError(FileSecurityError):
    """Exception raised when malicious content is detected"""
    pass


class FileQuarantineError(FileSecurityError):
    """Exception raised when file needs to be quarantined"""
    pass


class FileSecurityConfig:
    """Configuration for file security validation"""
    
    def __init__(self):
        # File size limits (in bytes)
        self.max_file_size = int(os.getenv('MAX_FILE_SIZE', 100 * 1024 * 1024))  # 100MB
        self.max_filename_length = int(os.getenv('MAX_FILENAME_LENGTH', 255))
        
        # Allowed file types and extensions
        self.allowed_extensions = {'.pdf'}
        self.allowed_mime_types = {
            'application/pdf',
            'application/x-pdf',
            'application/acrobat',
            'applications/vnd.pdf',
            'text/pdf',
            'text/x-pdf'
        }
        
        # Malicious content patterns
        self.suspicious_patterns = [
            b'javascript:',
            b'<script',
            b'eval(',
            b'document.write',
            b'window.open',
            b'XMLHttpRequest',
            b'ActiveXObject',
            b'<?php',
            b'<%',
            b'${',
            b'#{',
            b'/bin/sh',
            b'/bin/bash',
            b'cmd.exe',
            b'powershell',
            b'CreateObject',
            b'WScript.Shell'
        ]
        
        # PDF-specific security checks
        self.pdf_suspicious_keywords = [
            b'/JavaScript',
            b'/JS',
            b'/OpenAction',
            b'/AA',
            b'/Launch',
            b'/EmbeddedFile',
            b'/FileAttachment',
            b'/Encrypt',
            b'/U ',
            b'/O ',
            b'/P ',
            b'/URI',
            b'/SubmitForm'
        ]
        
        # File metadata limits
        self.max_embedded_files = 0  # No embedded files allowed
        self.max_pdf_pages = int(os.getenv('MAX_PDF_PAGES', 1000))
        
        # Rate limiting
        self.max_uploads_per_hour = int(os.getenv('MAX_UPLOADS_PER_HOUR', 50))
        self.max_uploads_per_day = int(os.getenv('MAX_UPLOADS_PER_DAY', 200))
        
        # Quarantine settings
        self.enable_quarantine = os.getenv('ENABLE_QUARANTINE', 'false').lower() == 'true'
        self.quarantine_dir = Path(os.getenv('QUARANTINE_DIR', '/tmp/refserver_quarantine'))


class FileValidator:
    """Comprehensive file validation and security scanner"""
    
    def __init__(self, config: FileSecurityConfig = None):
        self.config = config or FileSecurityConfig()
        self.upload_tracker = {}  # IP -> (uploads, reset_time)
        
        # Initialize quarantine directory
        if self.config.enable_quarantine:
            self.config.quarantine_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("File security validator initialized")
    
    def validate_file(self, file_path: str, filename: str, client_ip: str = None) -> Dict[str, Any]:
        """
        Comprehensive file validation
        
        Args:
            file_path: Path to the uploaded file
            filename: Original filename
            client_ip: Client IP address for rate limiting
            
        Returns:
            Dict containing validation results
            
        Raises:
            FileSecurityError: If file fails security checks
        """
        validation_result = {
            'filename': filename,
            'file_path': file_path,
            'timestamp': datetime.now().isoformat(),
            'checks_performed': [],
            'warnings': [],
            'threat_level': 'safe',
            'quarantined': False
        }
        
        try:
            # Rate limiting check
            if client_ip:
                self._check_rate_limits(client_ip)
                validation_result['checks_performed'].append('rate_limiting')
            
            # Basic file checks
            self._validate_filename(filename)
            validation_result['checks_performed'].append('filename_validation')
            
            self._validate_file_size(file_path)
            validation_result['checks_performed'].append('file_size_validation')
            
            # File type validation
            mime_type = self._validate_file_type(file_path, filename)
            validation_result['mime_type'] = mime_type
            validation_result['checks_performed'].append('file_type_validation')
            
            # Content analysis
            file_hash = self._calculate_file_hash(file_path)
            validation_result['file_hash'] = file_hash
            validation_result['checks_performed'].append('hash_calculation')
            
            # Malicious content detection
            threats = self._scan_for_malicious_content(file_path)
            if threats:
                validation_result['threats_detected'] = threats
                validation_result['threat_level'] = 'high' if len(threats) > 3 else 'medium'
                validation_result['warnings'].extend([f"Threat detected: {threat}" for threat in threats])
            
            validation_result['checks_performed'].append('malicious_content_scan')
            
            # PDF-specific validation
            if mime_type.startswith('application/pdf'):
                pdf_analysis = self._analyze_pdf_security(file_path)
                validation_result['pdf_analysis'] = pdf_analysis
                validation_result['checks_performed'].append('pdf_security_analysis')
                
                if pdf_analysis.get('suspicious_features'):
                    validation_result['threat_level'] = 'medium'
                    validation_result['warnings'].extend(pdf_analysis['suspicious_features'])
            
            # Structure validation
            structure_issues = self._validate_file_structure(file_path, mime_type)
            if structure_issues:
                validation_result['structure_issues'] = structure_issues
                validation_result['warnings'].extend(structure_issues)
            
            validation_result['checks_performed'].append('structure_validation')
            
            # Final threat assessment
            if validation_result['threat_level'] in ['high', 'critical']:
                # Log detailed threat information
                threat_details = []
                if 'threats_detected' in validation_result:
                    threat_details.extend([f"Malicious pattern: {threat}" for threat in validation_result['threats_detected']])
                if 'pdf_analysis' in validation_result and validation_result['pdf_analysis'].get('suspicious_features'):
                    threat_details.extend([f"PDF security issue: {feature}" for feature in validation_result['pdf_analysis']['suspicious_features']])
                if 'structure_issues' in validation_result:
                    threat_details.extend([f"Structure issue: {issue}" for issue in validation_result['structure_issues']])
                
                logger.warning(f"Security threats detected in '{filename}': {'; '.join(threat_details)}")
                
                if self.config.enable_quarantine:
                    self._quarantine_file(file_path, filename, validation_result)
                    validation_result['quarantined'] = True
                    
                    logger.error(f"File '{filename}' quarantined due to security threats: {'; '.join(threat_details)}")
                    raise MaliciousFileError(
                        f"File '{filename}' contains malicious content and has been quarantined"
                    )
                else:
                    # Quarantine disabled - log warning but allow processing
                    logger.warning(f"File '{filename}' contains suspicious content but quarantine is disabled. Threat details: {'; '.join(threat_details)}. Proceeding with processing.")
                    validation_result['quarantine_bypassed'] = True
            
            # Success
            validation_result['status'] = 'passed'
            logger.info(f"File validation passed for {filename}")
            
            return validation_result
            
        except FileSecurityError:
            validation_result['status'] = 'failed'
            raise
        except Exception as e:
            validation_result['status'] = 'error'
            validation_result['error'] = str(e)
            logger.error(f"Unexpected error during file validation: {e}")
            raise FileSecurityError(f"File validation failed: {str(e)}")
    
    def _check_rate_limits(self, client_ip: str):
        """Check upload rate limits per IP"""
        now = datetime.now()
        
        if client_ip not in self.upload_tracker:
            self.upload_tracker[client_ip] = {'hourly': [], 'daily': []}
        
        tracker = self.upload_tracker[client_ip]
        
        # Clean old entries
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)
        
        tracker['hourly'] = [t for t in tracker['hourly'] if t > hour_ago]
        tracker['daily'] = [t for t in tracker['daily'] if t > day_ago]
        
        # Check limits
        if len(tracker['hourly']) >= self.config.max_uploads_per_hour:
            raise FileSecurityError(f"Rate limit exceeded: max {self.config.max_uploads_per_hour} uploads per hour")
        
        if len(tracker['daily']) >= self.config.max_uploads_per_day:
            raise FileSecurityError(f"Rate limit exceeded: max {self.config.max_uploads_per_day} uploads per day")
        
        # Record this upload
        tracker['hourly'].append(now)
        tracker['daily'].append(now)
    
    def _validate_filename(self, filename: str):
        """Validate filename for security issues"""
        if not filename:
            raise FileTypeError("Filename cannot be empty")
        
        if len(filename) > self.config.max_filename_length:
            raise FileSecurityError(f"Filename too long (max {self.config.max_filename_length} characters)")
        
        # Check for path traversal attempts
        if '..' in filename or '/' in filename or '\\' in filename:
            raise FileSecurityError("Invalid filename: path traversal attempt detected")
        
        # Check for suspicious characters
        suspicious_chars = ['<', '>', ':', '"', '|', '?', '*', '\0', '\r', '\n']
        if any(char in filename for char in suspicious_chars):
            raise FileSecurityError("Invalid filename: contains suspicious characters")
        
        # Check extension
        file_ext = Path(filename).suffix.lower()
        if file_ext not in self.config.allowed_extensions:
            raise FileTypeError(f"File type not allowed. Allowed extensions: {self.config.allowed_extensions}")
    
    def _validate_file_size(self, file_path: str):
        """Validate file size"""
        try:
            file_size = os.path.getsize(file_path)
        except OSError as e:
            raise FileSecurityError(f"Cannot access file: {e}")
        
        if file_size == 0:
            raise FileSecurityError("File is empty")
        
        if file_size > self.config.max_file_size:
            size_mb = file_size / (1024 * 1024)
            max_mb = self.config.max_file_size / (1024 * 1024)
            raise FileSizeError(f"File too large: {size_mb:.1f}MB (max {max_mb:.1f}MB)")
    
    def _validate_file_type(self, file_path: str, filename: str) -> str:
        """Validate file type using multiple methods"""
        # Method 1: File extension
        file_ext = Path(filename).suffix.lower()
        if file_ext not in self.config.allowed_extensions:
            raise FileTypeError(f"File extension '{file_ext}' not allowed")
        
        # Method 2: MIME type detection
        try:
            mime_type = magic.from_file(file_path, mime=True)
        except Exception:
            # Fallback to mimetypes module
            mime_type, _ = mimetypes.guess_type(filename)
            if not mime_type:
                mime_type = 'application/octet-stream'
        
        if mime_type not in self.config.allowed_mime_types:
            raise FileTypeError(f"MIME type '{mime_type}' not allowed")
        
        # Method 3: File signature validation
        if not self._validate_file_signature(file_path, mime_type):
            raise FileTypeError("File signature does not match expected type")
        
        return mime_type
    
    def _validate_file_signature(self, file_path: str, expected_mime: str) -> bool:
        """Validate file signature (magic bytes)"""
        try:
            with open(file_path, 'rb') as f:
                header = f.read(8)
            
            # PDF signatures
            pdf_signatures = [
                b'%PDF-1.',  # Standard PDF
                b'%PDF-2.',  # PDF 2.0
            ]
            
            if expected_mime.startswith('application/pdf'):
                return any(header.startswith(sig) for sig in pdf_signatures)
            
            return True  # Allow other validated types
            
        except Exception as e:
            logger.error(f"Error validating file signature: {e}")
            return False
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of the file"""
        sha256_hash = hashlib.sha256()
        
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256_hash.update(chunk)
            
            return sha256_hash.hexdigest()
            
        except Exception as e:
            logger.error(f"Error calculating file hash: {e}")
            return "unknown"
    
    def _scan_for_malicious_content(self, file_path: str) -> List[str]:
        """Scan file for malicious content patterns"""
        threats = []
        
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            
            logger.debug(f"Scanning file {file_path} for malicious content (size: {len(content)} bytes)")
            
            # Check for suspicious patterns
            detected_patterns = []
            for pattern in self.config.suspicious_patterns:
                if pattern in content:
                    pattern_str = pattern.decode('utf-8', errors='ignore')
                    threats.append(f"Suspicious pattern: {pattern_str}")
                    detected_patterns.append(pattern_str)
            
            if detected_patterns:
                logger.warning(f"Detected suspicious patterns in {file_path}: {', '.join(detected_patterns)}")
            
            # Check for PDF-specific threats
            detected_pdf_threats = []
            for pattern in self.config.pdf_suspicious_keywords:
                if pattern in content:
                    pattern_str = pattern.decode('utf-8', errors='ignore')
                    threats.append(f"PDF threat: {pattern_str}")
                    detected_pdf_threats.append(pattern_str)
            
            if detected_pdf_threats:
                logger.warning(f"Detected PDF security threats in {file_path}: {', '.join(detected_pdf_threats)}")
            
            # Check for embedded executables
            if self._contains_embedded_executable(content):
                threats.append("Embedded executable detected")
                logger.warning(f"Embedded executable signature detected in {file_path}")
            
            # Check for suspicious URLs
            suspicious_urls = self._extract_suspicious_urls(content)
            if suspicious_urls:
                threats.extend([f"Suspicious URL: {url}" for url in suspicious_urls])
                logger.warning(f"Suspicious URLs detected in {file_path}: {', '.join(suspicious_urls)}")
            
            if threats:
                logger.warning(f"Total {len(threats)} security threats detected in {file_path}")
            else:
                logger.debug(f"No malicious content detected in {file_path}")
            
        except Exception as e:
            logger.error(f"Error scanning for malicious content: {e}")
            threats.append(f"Scan error: {str(e)}")
        
        return threats
    
    def _contains_embedded_executable(self, content: bytes) -> bool:
        """Check for embedded executable signatures"""
        executable_signatures = [
            b'MZ',      # Windows PE
            b'\x7fELF',  # Linux ELF
            b'\xfe\xed\xfa\xce',  # Mach-O (macOS)
            b'\xfe\xed\xfa\xcf',  # Mach-O 64-bit
            b'PK\x03\x04',  # ZIP (potential executable)
        ]
        
        return any(sig in content for sig in executable_signatures)
    
    def _extract_suspicious_urls(self, content: bytes) -> List[str]:
        """Extract and check for suspicious URLs"""
        suspicious_urls = []
        
        try:
            # Convert to text for URL extraction
            text = content.decode('utf-8', errors='ignore')
            
            # URL pattern
            url_pattern = r'https?://[^\s<>"\'()]+'
            urls = re.findall(url_pattern, text, re.IGNORECASE)
            
            # Check for suspicious domains/patterns
            suspicious_patterns = [
                'bit.ly',
                'tinyurl.com',
                'shorturl.at',
                'ow.ly',
                'is.gd',
                'malware',
                'phishing',
                'suspicious',
                'download.exe',
                'virus'
            ]
            
            for url in urls:
                if any(pattern in url.lower() for pattern in suspicious_patterns):
                    suspicious_urls.append(url)
                    
                # Check for suspicious ports
                if re.search(r':(4444|1234|8080|9999)', url):
                    suspicious_urls.append(url)
        
        except Exception:
            pass  # Ignore URL extraction errors
        
        return suspicious_urls[:10]  # Limit to 10 URLs
    
    def _analyze_pdf_security(self, file_path: str) -> Dict[str, Any]:
        """Perform PDF-specific security analysis"""
        analysis = {
            'page_count': 0,
            'has_javascript': False,
            'has_forms': False,
            'has_attachments': False,
            'is_encrypted': False,
            'suspicious_features': [],
            'metadata': {}
        }
        
        try:
            import PyPDF2
            
            with open(file_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                
                # Basic information
                analysis['page_count'] = len(pdf_reader.pages)
                analysis['is_encrypted'] = pdf_reader.is_encrypted
                
                # Check page limit
                if analysis['page_count'] > self.config.max_pdf_pages:
                    analysis['suspicious_features'].append(
                        f"Too many pages: {analysis['page_count']} (max {self.config.max_pdf_pages})"
                    )
                
                # Check for encryption
                if analysis['is_encrypted']:
                    analysis['suspicious_features'].append("PDF is encrypted")
                
                # Analyze document info
                if pdf_reader.metadata:
                    analysis['metadata'] = {
                        key: str(value) for key, value in pdf_reader.metadata.items()
                        if isinstance(value, (str, int, float))
                    }
                
                # Check each page for suspicious content
                for page_num, page in enumerate(pdf_reader.pages):
                    if '/JS' in str(page) or '/JavaScript' in str(page):
                        analysis['has_javascript'] = True
                        analysis['suspicious_features'].append(f"JavaScript on page {page_num + 1}")
                    
                    if '/AcroForm' in str(page) or '/XFA' in str(page):
                        analysis['has_forms'] = True
                        analysis['suspicious_features'].append(f"Interactive forms on page {page_num + 1}")
                    
                    if '/EmbeddedFile' in str(page) or '/FileAttachment' in str(page):
                        analysis['has_attachments'] = True
                        analysis['suspicious_features'].append(f"File attachment on page {page_num + 1}")
        
        except ImportError:
            # PyPDF2 not available, use basic checks
            with open(file_path, 'rb') as f:
                content = f.read()
            
            for pattern in self.config.pdf_suspicious_keywords:
                if pattern in content:
                    feature = pattern.decode('utf-8', errors='ignore')
                    analysis['suspicious_features'].append(f"Suspicious PDF feature: {feature}")
        
        except Exception as e:
            analysis['error'] = f"PDF analysis failed: {str(e)}"
        
        return analysis
    
    def _validate_file_structure(self, file_path: str, mime_type: str) -> List[str]:
        """Validate file structure integrity"""
        issues = []
        
        try:
            if mime_type.startswith('application/pdf'):
                issues.extend(self._validate_pdf_structure(file_path))
        
        except Exception as e:
            issues.append(f"Structure validation error: {str(e)}")
        
        return issues
    
    def _validate_pdf_structure(self, file_path: str) -> List[str]:
        """Validate PDF file structure"""
        issues = []
        
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            
            # Check for proper PDF structure
            if not content.startswith(b'%PDF-'):
                issues.append("Invalid PDF header")
            
            if b'%%EOF' not in content:
                issues.append("Missing PDF EOF marker")
            
            # Check for suspicious object count
            obj_count = content.count(b'obj')
            if obj_count > 10000:  # Arbitrary high limit
                issues.append(f"Excessive PDF objects: {obj_count}")
            
            # Check for suspicious stream count
            stream_count = content.count(b'stream')
            if stream_count > 1000:  # Arbitrary high limit
                issues.append(f"Excessive PDF streams: {stream_count}")
        
        except Exception as e:
            issues.append(f"PDF structure validation error: {str(e)}")
        
        return issues
    
    def _quarantine_file(self, file_path: str, filename: str, validation_result: Dict[str, Any]):
        """Move suspicious file to quarantine"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            quarantine_filename = f"{timestamp}_{filename}"
            quarantine_path = self.config.quarantine_dir / quarantine_filename
            
            # Copy file to quarantine
            import shutil
            shutil.copy2(file_path, quarantine_path)
            
            # Create metadata file
            metadata_path = quarantine_path.with_suffix('.json')
            with open(metadata_path, 'w') as f:
                import json
                json.dump(validation_result, f, indent=2, default=str)
            
            logger.warning(f"File quarantined: {filename} -> {quarantine_path}")
            
        except Exception as e:
            logger.error(f"Failed to quarantine file {filename}: {e}")
    
    def get_quarantine_info(self) -> Dict[str, Any]:
        """Get information about quarantined files"""
        if not self.config.enable_quarantine:
            return {'enabled': False}
        
        try:
            quarantine_files = []
            for file_path in self.config.quarantine_dir.glob('*'):
                if file_path.suffix == '.json':
                    continue
                
                quarantine_files.append({
                    'filename': file_path.name,
                    'size': file_path.stat().st_size,
                    'quarantined_at': datetime.fromtimestamp(file_path.stat().st_ctime).isoformat(),
                    'metadata_available': file_path.with_suffix('.json').exists()
                })
            
            return {
                'enabled': True,
                'quarantine_dir': str(self.config.quarantine_dir),
                'quarantined_files': quarantine_files,
                'total_files': len(quarantine_files)
            }
            
        except Exception as e:
            logger.error(f"Error getting quarantine info: {e}")
            return {'enabled': True, 'error': str(e)}


# Global validator instance
_file_validator = None


def get_file_validator() -> FileValidator:
    """Get global file validator instance (singleton)"""
    global _file_validator
    
    if _file_validator is None:
        _file_validator = FileValidator()
    
    return _file_validator


def validate_uploaded_file(file_path: str, filename: str, client_ip: str = None) -> Dict[str, Any]:
    """Validate an uploaded file"""
    validator = get_file_validator()
    return validator.validate_file(file_path, filename, client_ip)


def check_file_security(file_path: str, filename: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Quick security check for a file
    
    Returns:
        Tuple[bool, Dict]: (is_safe, validation_details)
    """
    try:
        result = validate_uploaded_file(file_path, filename)
        return True, result
    except FileSecurityError as e:
        return False, {'error': str(e), 'type': type(e).__name__}
    except Exception as e:
        return False, {'error': f"Validation failed: {str(e)}", 'type': 'UnknownError'}


def get_security_status() -> Dict[str, Any]:
    """Get current security system status"""
    validator = get_file_validator()
    config = validator.config
    
    return {
        'enabled': True,
        'max_file_size_mb': config.max_file_size / (1024 * 1024),
        'allowed_extensions': list(config.allowed_extensions),
        'allowed_mime_types': list(config.allowed_mime_types),
        'rate_limits': {
            'max_uploads_per_hour': config.max_uploads_per_hour,
            'max_uploads_per_day': config.max_uploads_per_day
        },
        'quarantine': validator.get_quarantine_info(),
        'active_trackers': len(validator.upload_tracker)
    }