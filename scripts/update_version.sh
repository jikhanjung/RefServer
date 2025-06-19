#!/bin/bash
# RefServer Version Update Script
# Updates VERSION file and optionally commits the change

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VERSION_FILE="$PROJECT_ROOT/VERSION"

echo -e "${BLUE}🏷️  RefServer Version Update Script${NC}"
echo -e "${BLUE}====================================${NC}"
echo ""

# Check if version argument is provided
if [ -z "$1" ]; then
    if [ -f "$VERSION_FILE" ]; then
        CURRENT_VERSION=$(cat "$VERSION_FILE" | tr -d '\n\r ')
        echo -e "${YELLOW}Current version: ${CURRENT_VERSION}${NC}"
    else
        echo -e "${YELLOW}No VERSION file found${NC}"
    fi
    echo ""
    echo -e "${RED}Usage: $0 <new_version> [--commit]${NC}"
    echo -e "Examples:"
    echo -e "  $0 v0.1.9"
    echo -e "  $0 v0.2.0 --commit"
    exit 1
fi

NEW_VERSION="$1"
COMMIT_FLAG="$2"

# Validate version format (should start with 'v' and contain dots)
if [[ ! "$NEW_VERSION" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo -e "${YELLOW}⚠️  Warning: Version format should be 'vX.Y.Z' (e.g., v0.1.9)${NC}"
    echo -e "${YELLOW}   Proceeding with: ${NEW_VERSION}${NC}"
    echo ""
fi

# Show current version if exists
if [ -f "$VERSION_FILE" ]; then
    CURRENT_VERSION=$(cat "$VERSION_FILE" | tr -d '\n\r ')
    echo -e "${YELLOW}Current version: ${CURRENT_VERSION}${NC}"
fi

echo -e "${YELLOW}New version: ${NEW_VERSION}${NC}"
echo ""

# Update VERSION file
echo "$NEW_VERSION" > "$VERSION_FILE"
echo -e "${GREEN}✅ Updated VERSION file${NC}"

# Update README.md title
README_FILE="$PROJECT_ROOT/README.md"
if [ -f "$README_FILE" ]; then
    # Use different delimiters to avoid conflicts with version dots
    sed -i.bak "s|^# RefServer v[0-9]\+\.[0-9]\+\.[0-9]\+|# RefServer $NEW_VERSION|" "$README_FILE"
    rm -f "$README_FILE.bak" 2>/dev/null || true
    echo -e "${GREEN}✅ Updated README.md title${NC}"
fi

# Commit changes if requested
if [ "$COMMIT_FLAG" = "--commit" ]; then
    cd "$PROJECT_ROOT"
    
    # Check if git repo
    if [ -d ".git" ]; then
        echo ""
        echo -e "${BLUE}📝 Committing version update...${NC}"
        
        git add VERSION README.md
        git commit -m "Update version to $NEW_VERSION

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>"
        
        echo -e "${GREEN}✅ Version update committed${NC}"
        
        # Suggest creating a tag
        echo ""
        echo -e "${BLUE}💡 Suggestion: Create a git tag${NC}"
        echo -e "   git tag $NEW_VERSION"
        echo -e "   git push origin $NEW_VERSION"
    else
        echo -e "${YELLOW}⚠️  Not a git repository, skipping commit${NC}"
    fi
fi

echo ""
echo -e "${GREEN}🎉 Version updated successfully!${NC}"
echo ""
echo -e "${BLUE}📋 Next steps:${NC}"
echo -e "   • Build new Docker image: ./scripts/build_and_push.sh"
echo -e "   • Create git tag: git tag $NEW_VERSION"
echo -e "   • Push changes: git push && git push --tags"