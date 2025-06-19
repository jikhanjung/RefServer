#!/usr/bin/env python3
"""
Quick test script to check version information in API endpoints
"""

import requests
import json

def test_version_endpoints():
    """Test version information in various API endpoints"""
    
    base_url = "http://localhost:8060"
    
    print("🧪 Testing Version Information in API Endpoints")
    print("=" * 50)
    
    # Test /status endpoint
    try:
        print("\n📋 Testing /status endpoint...")
        response = requests.get(f"{base_url}/status", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Status: {response.status_code}")
            print(f"📦 Version: {data.get('version', 'N/A')}")
            print(f"🖥️  Deployment Mode: {data.get('deployment_mode', 'N/A')}")
            print(f"💾 Database: {'✅' if data.get('database') else '❌'}")
            print(f"🎯 Quality Assessment: {'✅' if data.get('quality_assessment') else '❌'}")
            print(f"📐 Layout Analysis: {'✅' if data.get('layout_analysis') else '❌'}")
            print(f"📚 Metadata Extraction: {'✅' if data.get('metadata_extraction') else '❌'}")
        else:
            print(f"❌ Failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test /health endpoint
    try:
        print("\n💚 Testing /health endpoint...")
        response = requests.get(f"{base_url}/health", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health: {response.status_code}")
            print(f"📋 Status: {data.get('status', 'N/A')}")
            print(f"🏷️  Service: {data.get('service', 'N/A')}")
        else:
            print(f"❌ Failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test API docs (OpenAPI schema)
    try:
        print("\n📖 Testing API docs version...")
        response = requests.get(f"{base_url}/openapi.json", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ OpenAPI: {response.status_code}")
            print(f"📦 API Version: {data.get('info', {}).get('version', 'N/A')}")
            print(f"📝 Title: {data.get('info', {}).get('title', 'N/A')}")
        else:
            print(f"❌ Failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 Version test completed!")

if __name__ == "__main__":
    test_version_endpoints()