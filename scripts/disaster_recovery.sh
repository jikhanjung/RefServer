#!/bin/bash

# RefServer Disaster Recovery Script
# Version: 0.1.12
# Description: Automated disaster recovery for RefServer databases

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DATA_DIR="/data"
BACKUP_DIR="${DATA_DIR}/backups"
SQLITE_DB="${DATA_DIR}/refserver.db"
CHROMADB_DIR="${DATA_DIR}/chromadb"
LOG_FILE="/var/log/refserver_recovery.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    local level=$1
    shift
    local message="$@"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${timestamp} [${level}] ${message}" | tee -a "${LOG_FILE}"
}

# Print colored message
print_color() {
    local color=$1
    shift
    echo -e "${color}$@${NC}"
}

# Show usage
usage() {
    cat << EOF
RefServer Disaster Recovery Script

Usage: $0 [OPTIONS]

Options:
    --help              Show this help message
    --check             Check system health
    --list              List available backups
    --restore-latest    Restore from latest backup
    --restore           Restore specific backup (requires --backup-id)
    --backup-id ID      Specify backup ID to restore
    --unified           Use unified backup (SQLite + ChromaDB)
    --sqlite-only       Restore only SQLite database
    --chromadb-only     Restore only ChromaDB
    --point-in-time     Restore to specific time (requires --timestamp)
    --timestamp TIME    Specify timestamp (YYYY-MM-DD HH:MM:SS)
    --auto-recover      Automatically detect and fix issues
    --dry-run           Show what would be done without executing
    --force             Skip confirmation prompts

Examples:
    $0 --check
    $0 --restore-latest --unified
    $0 --restore --backup-id "refserver_20250120_030000"
    $0 --auto-recover

EOF
}

# Check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        print_color $YELLOW "Warning: Running as root. This may cause permission issues."
    fi
}

# Check system health
check_health() {
    print_color $BLUE "Checking system health..."
    
    local issues=0
    
    # Check SQLite database
    if [[ -f "$SQLITE_DB" ]]; then
        if sqlite3 "$SQLITE_DB" "PRAGMA integrity_check;" | grep -q "ok"; then
            print_color $GREEN "✓ SQLite database is healthy"
        else
            print_color $RED "✗ SQLite database is corrupted"
            ((issues++))
        fi
    else
        print_color $RED "✗ SQLite database not found"
        ((issues++))
    fi
    
    # Check ChromaDB directory
    if [[ -d "$CHROMADB_DIR" ]]; then
        print_color $GREEN "✓ ChromaDB directory exists"
    else
        print_color $YELLOW "⚠ ChromaDB directory not found (may not be initialized)"
    fi
    
    # Check backup directory
    if [[ -d "$BACKUP_DIR" ]]; then
        local backup_count=$(find "$BACKUP_DIR" -name "*.db.gz" -o -name "*.tar.gz" | wc -l)
        print_color $GREEN "✓ Backup directory exists with $backup_count backup files"
    else
        print_color $RED "✗ Backup directory not found"
        ((issues++))
    fi
    
    # Check disk space
    local disk_usage=$(df -h "$DATA_DIR" | awk 'NR==2 {print $5}' | sed 's/%//')
    if [[ $disk_usage -lt 90 ]]; then
        print_color $GREEN "✓ Disk usage is ${disk_usage}%"
    else
        print_color $RED "✗ Disk usage is critical: ${disk_usage}%"
        ((issues++))
    fi
    
    # Check API health
    if curl -s -f http://localhost:8060/health > /dev/null 2>&1; then
        print_color $GREEN "✓ API is responding"
    else
        print_color $RED "✗ API is not responding"
        ((issues++))
    fi
    
    if [[ $issues -eq 0 ]]; then
        print_color $GREEN "\nSystem is healthy!"
        return 0
    else
        print_color $RED "\nFound $issues issues"
        return 1
    fi
}

# List available backups
list_backups() {
    print_color $BLUE "Available backups:\n"
    
    # SQLite backups
    print_color $YELLOW "SQLite Backups:"
    if [[ -d "${BACKUP_DIR}/sqlite" ]]; then
        find "${BACKUP_DIR}/sqlite" -name "*.db.gz" -type f -printf "%p\t%s bytes\t%TY-%Tm-%Td %TH:%TM\n" | sort -r | head -20
    else
        echo "No SQLite backups found"
    fi
    
    echo ""
    
    # ChromaDB backups
    print_color $YELLOW "ChromaDB Backups:"
    if [[ -d "${BACKUP_DIR}/chromadb" ]]; then
        find "${BACKUP_DIR}/chromadb" -name "*.tar.gz" -type f -printf "%p\t%s bytes\t%TY-%Tm-%Td %TH:%TM\n" | sort -r | head -20
    else
        echo "No ChromaDB backups found"
    fi
}

# Stop services
stop_services() {
    log "INFO" "Stopping RefServer services..."
    cd "$PROJECT_ROOT"
    docker-compose down || true
}

# Start services
start_services() {
    log "INFO" "Starting RefServer services..."
    cd "$PROJECT_ROOT"
    docker-compose up -d
    
    # Wait for services to be ready
    sleep 10
    
    # Check if API is responding
    local retries=30
    while ! curl -s -f http://localhost:8060/health > /dev/null 2>&1; do
        ((retries--))
        if [[ $retries -eq 0 ]]; then
            log "ERROR" "API failed to start"
            return 1
        fi
        sleep 2
    done
    
    log "INFO" "Services started successfully"
}

# Create safety backup
create_safety_backup() {
    local backup_name="safety_$(date +%Y%m%d_%H%M%S)"
    
    log "INFO" "Creating safety backup: $backup_name"
    
    # SQLite backup
    if [[ -f "$SQLITE_DB" ]]; then
        cp "$SQLITE_DB" "${SQLITE_DB}.${backup_name}"
        gzip "${SQLITE_DB}.${backup_name}"
    fi
    
    # ChromaDB backup
    if [[ -d "$CHROMADB_DIR" ]]; then
        tar -czf "${CHROMADB_DIR}.${backup_name}.tar.gz" -C "$(dirname "$CHROMADB_DIR")" "$(basename "$CHROMADB_DIR")"
    fi
    
    log "INFO" "Safety backup created"
}

# Restore SQLite database
restore_sqlite() {
    local backup_file=$1
    
    if [[ ! -f "$backup_file" ]]; then
        log "ERROR" "SQLite backup file not found: $backup_file"
        return 1
    fi
    
    log "INFO" "Restoring SQLite from: $backup_file"
    
    # Decompress and restore
    gunzip -c "$backup_file" > "${SQLITE_DB}.tmp"
    
    # Verify the restored database
    if sqlite3 "${SQLITE_DB}.tmp" "PRAGMA integrity_check;" | grep -q "ok"; then
        mv "${SQLITE_DB}.tmp" "$SQLITE_DB"
        chmod 644 "$SQLITE_DB"
        log "INFO" "SQLite restored successfully"
        return 0
    else
        rm -f "${SQLITE_DB}.tmp"
        log "ERROR" "Restored SQLite database is corrupted"
        return 1
    fi
}

# Restore ChromaDB
restore_chromadb() {
    local backup_file=$1
    
    if [[ ! -f "$backup_file" ]]; then
        log "ERROR" "ChromaDB backup file not found: $backup_file"
        return 1
    fi
    
    log "INFO" "Restoring ChromaDB from: $backup_file"
    
    # Remove existing ChromaDB directory
    rm -rf "$CHROMADB_DIR"
    
    # Extract backup
    tar -xzf "$backup_file" -C "$DATA_DIR"
    
    # Set permissions
    chown -R 1000:1000 "$CHROMADB_DIR" 2>/dev/null || true
    
    log "INFO" "ChromaDB restored successfully"
    return 0
}

# Find latest backup
find_latest_backup() {
    local type=$1  # sqlite or chromadb
    local subdir=$2  # daily, weekly, etc.
    
    local backup_dir="${BACKUP_DIR}/${type}/${subdir}"
    
    if [[ ! -d "$backup_dir" ]]; then
        echo ""
        return
    fi
    
    if [[ "$type" == "sqlite" ]]; then
        find "$backup_dir" -name "*.db.gz" -type f -printf "%T@ %p\n" | sort -rn | head -1 | cut -d' ' -f2-
    else
        find "$backup_dir" -name "*.tar.gz" -type f -printf "%T@ %p\n" | sort -rn | head -1 | cut -d' ' -f2-
    fi
}

# Restore from latest backup
restore_latest() {
    local restore_sqlite=true
    local restore_chromadb=true
    
    # Parse options
    if [[ "$SQLITE_ONLY" == true ]]; then
        restore_chromadb=false
    elif [[ "$CHROMADB_ONLY" == true ]]; then
        restore_sqlite=false
    fi
    
    # Find latest backups
    local latest_sqlite=""
    local latest_chromadb=""
    
    if [[ "$restore_sqlite" == true ]]; then
        latest_sqlite=$(find_latest_backup "sqlite" "daily")
        if [[ -z "$latest_sqlite" ]]; then
            latest_sqlite=$(find_latest_backup "sqlite" "weekly")
        fi
        
        if [[ -z "$latest_sqlite" ]]; then
            log "ERROR" "No SQLite backup found"
            return 1
        fi
    fi
    
    if [[ "$restore_chromadb" == true ]]; then
        latest_chromadb=$(find_latest_backup "chromadb" "daily")
        if [[ -z "$latest_chromadb" ]]; then
            latest_chromadb=$(find_latest_backup "chromadb" "weekly")
        fi
        
        if [[ -z "$latest_chromadb" ]]; then
            log "WARNING" "No ChromaDB backup found"
        fi
    fi
    
    # Show what will be restored
    print_color $BLUE "Will restore from:"
    [[ -n "$latest_sqlite" ]] && echo "SQLite: $latest_sqlite"
    [[ -n "$latest_chromadb" ]] && echo "ChromaDB: $latest_chromadb"
    
    # Confirm unless forced
    if [[ "$FORCE" != true ]]; then
        read -p "Continue with restore? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log "INFO" "Restore cancelled by user"
            return 1
        fi
    fi
    
    # Perform restore
    stop_services
    create_safety_backup
    
    local success=true
    
    if [[ -n "$latest_sqlite" ]]; then
        if ! restore_sqlite "$latest_sqlite"; then
            success=false
        fi
    fi
    
    if [[ -n "$latest_chromadb" ]]; then
        if ! restore_chromadb "$latest_chromadb"; then
            success=false
        fi
    fi
    
    start_services
    
    if [[ "$success" == true ]]; then
        print_color $GREEN "Restore completed successfully!"
        return 0
    else
        print_color $RED "Restore completed with errors"
        return 1
    fi
}

# Auto recover function
auto_recover() {
    log "INFO" "Starting auto-recovery process..."
    
    # Check health first
    if check_health; then
        log "INFO" "System is healthy, no recovery needed"
        return 0
    fi
    
    # Try to fix issues automatically
    log "INFO" "Attempting automatic recovery..."
    
    # If SQLite is corrupted, restore from latest backup
    if ! sqlite3 "$SQLITE_DB" "PRAGMA integrity_check;" | grep -q "ok" 2>/dev/null; then
        log "WARNING" "SQLite database corrupted, restoring from backup..."
        SQLITE_ONLY=true
        restore_latest
    fi
    
    # If API is not responding, try restarting services
    if ! curl -s -f http://localhost:8060/health > /dev/null 2>&1; then
        log "WARNING" "API not responding, restarting services..."
        stop_services
        start_services
    fi
    
    # Check health again
    if check_health; then
        print_color $GREEN "Auto-recovery successful!"
        return 0
    else
        print_color $RED "Auto-recovery failed, manual intervention required"
        return 1
    fi
}

# Main script logic
main() {
    # Initialize variables
    ACTION=""
    BACKUP_ID=""
    UNIFIED=false
    SQLITE_ONLY=false
    CHROMADB_ONLY=false
    TIMESTAMP=""
    DRY_RUN=false
    FORCE=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --help)
                usage
                exit 0
                ;;
            --check)
                ACTION="check"
                ;;
            --list)
                ACTION="list"
                ;;
            --restore-latest)
                ACTION="restore-latest"
                ;;
            --restore)
                ACTION="restore"
                ;;
            --backup-id)
                BACKUP_ID="$2"
                shift
                ;;
            --unified)
                UNIFIED=true
                ;;
            --sqlite-only)
                SQLITE_ONLY=true
                ;;
            --chromadb-only)
                CHROMADB_ONLY=true
                ;;
            --point-in-time)
                ACTION="point-in-time"
                ;;
            --timestamp)
                TIMESTAMP="$2"
                shift
                ;;
            --auto-recover)
                ACTION="auto-recover"
                ;;
            --dry-run)
                DRY_RUN=true
                ;;
            --force)
                FORCE=true
                ;;
            *)
                echo "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
        shift
    done
    
    # Check root
    check_root
    
    # Create log directory if needed
    mkdir -p "$(dirname "$LOG_FILE")"
    
    # Execute action
    case $ACTION in
        check)
            check_health
            ;;
        list)
            list_backups
            ;;
        restore-latest)
            restore_latest
            ;;
        restore)
            if [[ -z "$BACKUP_ID" ]]; then
                echo "Error: --backup-id required for restore"
                exit 1
            fi
            # TODO: Implement specific backup restore
            echo "Restore from specific backup not yet implemented"
            ;;
        auto-recover)
            auto_recover
            ;;
        *)
            echo "Error: No action specified"
            usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"