#!/bin/bash

# RefServer Full Test Suite
# This script runs comprehensive tests including PDF generation and batch upload

set -e

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
SERVER_URL="http://localhost:8000"
CLEANUP=false
SKIP_GENERATION=false

# Function to print colored output
print_status() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --url URL          RefServer base URL (default: http://localhost:8000)"
    echo "  --cleanup          Clean up test files after completion"
    echo "  --skip-generation  Skip PDF generation (use existing files)"
    echo "  --help             Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Run with defaults"
    echo "  $0 --url http://localhost:8060       # Use different port"
    echo "  $0 --cleanup                         # Clean up after test"
    echo "  $0 --skip-generation --cleanup       # Use existing PDFs and cleanup"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --url)
            SERVER_URL="$2"
            shift 2
            ;;
        --cleanup)
            CLEANUP=true
            shift
            ;;
        --skip-generation)
            SKIP_GENERATION=true
            shift
            ;;
        --help)
            show_usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

print_status $BLUE "╔════════════════════════════════════════════════════════════╗"
print_status $BLUE "║                    RefServer Full Test Suite               ║"
print_status $BLUE "╚════════════════════════════════════════════════════════════╝"

print_status $YELLOW "\nTest Configuration:"
print_status $NC "  Server URL: $SERVER_URL"
print_status $NC "  Cleanup after test: $CLEANUP"
print_status $NC "  Skip PDF generation: $SKIP_GENERATION"

# Check if server is running
print_status $YELLOW "\n1. Checking server health..."
if curl -s -f "$SERVER_URL/health" > /dev/null; then
    print_status $GREEN "✓ Server is responding"
else
    print_status $RED "✗ Cannot reach server at $SERVER_URL"
    print_status $YELLOW "Make sure RefServer is running with:"
    print_status $NC "  docker-compose up"
    print_status $NC "  or"
    print_status $NC "  docker-compose -f docker-compose.cpu.yml up"
    exit 1
fi

# Check Python dependencies
print_status $YELLOW "\n2. Checking Python dependencies..."
if python3 -c "import requests, subprocess, pathlib" 2>/dev/null; then
    print_status $GREEN "✓ Python dependencies available"
else
    print_status $RED "✗ Missing Python dependencies"
    print_status $YELLOW "Install with: pip install requests"
    exit 1
fi

# Run PDF generation test if not skipped
if [ "$SKIP_GENERATION" = false ]; then
    print_status $YELLOW "\n3. Testing PDF generation..."
    if [ -f "create_test_pdfs.py" ]; then
        if python3 create_test_pdfs.py --multiple --output test_papers; then
            print_status $GREEN "✓ PDF generation completed"
        else
            print_status $RED "✗ PDF generation failed"
            exit 1
        fi
    else
        print_status $RED "✗ create_test_pdfs.py not found"
        exit 1
    fi
else
    print_status $YELLOW "\n3. Skipping PDF generation (using existing files)"
fi

# Run batch upload test
print_status $YELLOW "\n4. Running batch upload test..."
BATCH_ARGS=""
if [ "$CLEANUP" = true ]; then
    BATCH_ARGS="--cleanup"
fi

if python3 test_batch_upload.py --url "$SERVER_URL" $BATCH_ARGS; then
    print_status $GREEN "\n✓ Batch upload test completed successfully!"
else
    print_status $RED "\n✗ Batch upload test failed"
    exit 1
fi

# Additional API tests
print_status $YELLOW "\n5. Running additional API tests..."
if [ -f "test_api.py" ]; then
    if python3 test_api.py; then
        print_status $GREEN "✓ Additional API tests passed"
    else
        print_status $YELLOW "⚠ Some additional API tests failed (check logs)"
    fi
else
    print_status $YELLOW "⚠ test_api.py not found, skipping additional API tests"
fi

# Final summary
print_status $GREEN "\n╔════════════════════════════════════════════════════════════╗"
print_status $GREEN "║                     Test Suite Complete!                   ║"
print_status $GREEN "╚════════════════════════════════════════════════════════════╝"

print_status $YELLOW "\nTest files location: $SCRIPT_DIR/test_papers/"
print_status $YELLOW "Test results saved in: $SCRIPT_DIR/test_results_*.json"

if [ "$CLEANUP" = false ]; then
    print_status $NC "\nTo clean up test files, run:"
    print_status $NC "  rm -rf test_papers/"
    print_status $NC "  rm -f test_results_*.json"
fi

print_status $GREEN "\nYou can now access the RefServer admin interface to view uploaded papers:"
print_status $NC "  ${SERVER_URL}/admin"