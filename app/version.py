"""
Version management utility for RefServer
Reads version from VERSION file in project root
"""

import os
from pathlib import Path

def get_version():
    """
    Get version string from VERSION file
    
    Returns:
        str: Version string (e.g., 'v0.1.8')
    """
    try:
        # Get current directory (app directory)
        app_dir = Path(__file__).parent
        
        # Try Docker environment first (VERSION file in same directory as app code)
        version_file_docker = app_dir / 'VERSION'
        if version_file_docker.exists():
            version = version_file_docker.read_text().strip()
            return version
        
        # Try local development environment (VERSION file in parent directory)
        project_root = app_dir.parent
        version_file_local = project_root / 'VERSION'
        if version_file_local.exists():
            version = version_file_local.read_text().strip()
            return version
        
        # Fallback version if file not found in either location
        return 'v0.1.10'
            
    except Exception:
        # Fallback version on any error
        return 'v0.1.10'

def get_version_info():
    """
    Get detailed version information
    
    Returns:
        dict: Version information
    """
    version = get_version()
    return {
        'version': version,
        'version_numeric': version.lstrip('v'),
        'major': int(version.split('.')[0].lstrip('v')),
        'minor': int(version.split('.')[1]),
        'patch': int(version.split('.')[2]) if len(version.split('.')) > 2 else 0
    }

# Module level constants
__version__ = get_version()
VERSION = __version__