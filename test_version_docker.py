#!/usr/bin/env python3
"""
Test script to verify version loading in different environments
"""

import sys
from pathlib import Path

# Add app directory to path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir))

from version import get_version, get_version_info

def test_version_loading():
    """Test version loading in current environment"""
    
    print("🧪 Testing Version Loading")
    print("=" * 30)
    
    # Test paths
    current_dir = Path(__file__).parent
    app_dir = current_dir / "app"
    
    print(f"📁 Current directory: {current_dir}")
    print(f"📁 App directory: {app_dir}")
    
    # Check VERSION file locations
    version_file_root = current_dir / "VERSION"
    version_file_app = app_dir / "VERSION"
    
    print(f"\n📋 VERSION file locations:")
    print(f"   Root: {version_file_root} {'✅' if version_file_root.exists() else '❌'}")
    print(f"   App:  {version_file_app} {'✅' if version_file_app.exists() else '❌'}")
    
    # Test version functions
    print(f"\n🏷️  Version functions:")
    try:
        version = get_version()
        print(f"   get_version(): {version}")
        
        version_info = get_version_info()
        print(f"   get_version_info(): {version_info}")
        
        print(f"\n✅ Version loading successful!")
        
    except Exception as e:
        print(f"❌ Error loading version: {e}")
    
    # Test environment detection
    print(f"\n🔍 Environment detection:")
    if version_file_app.exists():
        print("   📦 Docker environment (VERSION in app directory)")
    elif version_file_root.exists():
        print("   🖥️  Local environment (VERSION in project root)")
    else:
        print("   ⚠️  No VERSION file found, using fallback")

if __name__ == "__main__":
    test_version_loading()