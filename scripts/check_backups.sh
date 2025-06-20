#!/bin/bash

# RefServer Backup Health Check Script
# Version: 0.1.12
# Description: Monitor backup health and alert on issues

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DATA_DIR="/data"
BACKUP_DIR="${DATA_DIR}/backups"
LOG_FILE="/var/log/refserver_backup_check.log"

# Thresholds
MAX_BACKUP_AGE_HOURS=26  # 26 hours for daily backups
MIN_BACKUP_COUNT=3
MIN_FREE_SPACE_GB=5

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Logging function
log() {
    local level=$1
    shift
    local message="$@"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${timestamp} [${level}] ${message}" | tee -a "${LOG_FILE}"
}

# Check if backup directory exists and is accessible
check_backup_directory() {
    if [[ ! -d "$BACKUP_DIR" ]]; then
        log "ERROR" "Backup directory does not exist: $BACKUP_DIR"
        return 1
    fi
    
    if [[ ! -w "$BACKUP_DIR" ]]; then
        log "ERROR" "Backup directory is not writable: $BACKUP_DIR"
        return 1
    fi
    
    log "INFO" "Backup directory is accessible"
    return 0
}

# Check disk space
check_disk_space() {
    local available_gb=$(df -BG "$DATA_DIR" | awk 'NR==2 {print $4}' | sed 's/G//')
    
    if [[ $available_gb -lt $MIN_FREE_SPACE_GB ]]; then
        log "ERROR" "Low disk space: ${available_gb}GB available (minimum: ${MIN_FREE_SPACE_GB}GB)"
        return 1
    fi
    
    log "INFO" "Sufficient disk space: ${available_gb}GB available"
    return 0
}

# Check SQLite backup health
check_sqlite_backups() {
    local sqlite_backup_dir="${BACKUP_DIR}/sqlite"
    local issues=0
    
    log "INFO" "Checking SQLite backups..."
    
    if [[ ! -d "$sqlite_backup_dir" ]]; then
        log "ERROR" "SQLite backup directory not found"
        return 1
    fi
    
    # Check for recent backups
    local recent_backups=$(find "$sqlite_backup_dir" -name "*.db.gz" -type f -mtime -1 | wc -l)
    if [[ $recent_backups -eq 0 ]]; then
        log "ERROR" "No SQLite backups created in the last 24 hours"
        ((issues++))
    else
        log "INFO" "Found $recent_backups recent SQLite backups"
    fi
    
    # Check total backup count
    local total_backups=$(find "$sqlite_backup_dir" -name "*.db.gz" -type f | wc -l)
    if [[ $total_backups -lt $MIN_BACKUP_COUNT ]]; then
        log "WARNING" "Low SQLite backup count: $total_backups (minimum: $MIN_BACKUP_COUNT)"
        ((issues++))
    else
        log "INFO" "Total SQLite backups: $total_backups"
    fi
    
    # Check backup file integrity
    local corrupted_backups=0
    while IFS= read -r -d '' backup_file; do
        if ! gzip -t "$backup_file" 2>/dev/null; then
            log "ERROR" "Corrupted backup file: $backup_file"
            ((corrupted_backups++))
            ((issues++))
        fi
    done < <(find "$sqlite_backup_dir" -name "*.db.gz" -type f -print0)
    
    if [[ $corrupted_backups -eq 0 ]]; then
        log "INFO" "All SQLite backup files are valid"
    fi
    
    return $issues
}

# Check ChromaDB backup health
check_chromadb_backups() {
    local chromadb_backup_dir="${BACKUP_DIR}/chromadb"
    local issues=0
    
    log "INFO" "Checking ChromaDB backups..."
    
    if [[ ! -d "$chromadb_backup_dir" ]]; then
        log "WARNING" "ChromaDB backup directory not found (may not be initialized)"
        return 0
    fi
    
    # Check for recent backups
    local recent_backups=$(find "$chromadb_backup_dir" -name "*.tar.gz" -type f -mtime -1 | wc -l)
    if [[ $recent_backups -eq 0 ]]; then
        log "WARNING" "No ChromaDB backups created in the last 24 hours"
        ((issues++))
    else
        log "INFO" "Found $recent_backups recent ChromaDB backups"
    fi
    
    # Check backup file integrity
    local corrupted_backups=0
    while IFS= read -r -d '' backup_file; do
        if ! tar -tzf "$backup_file" >/dev/null 2>&1; then
            log "ERROR" "Corrupted backup file: $backup_file"
            ((corrupted_backups++))
            ((issues++))
        fi
    done < <(find "$chromadb_backup_dir" -name "*.tar.gz" -type f -print0)
    
    if [[ $corrupted_backups -eq 0 ]]; then
        log "INFO" "All ChromaDB backup files are valid"
    fi
    
    return $issues
}

# Check backup scheduler status
check_scheduler_status() {
    log "INFO" "Checking backup scheduler status..."
    
    # Try to get scheduler status via API
    if curl -s -f http://localhost:8060/admin/backup/status >/dev/null 2>&1; then
        log "INFO" "Backup scheduler API is accessible"
        return 0
    else
        log "ERROR" "Cannot access backup scheduler API"
        return 1
    fi
}

# Check database integrity
check_database_integrity() {
    local sqlite_db="${DATA_DIR}/refserver.db"
    
    log "INFO" "Checking database integrity..."
    
    if [[ ! -f "$sqlite_db" ]]; then
        log "ERROR" "SQLite database not found: $sqlite_db"
        return 1
    fi
    
    # Check SQLite integrity
    if sqlite3 "$sqlite_db" "PRAGMA integrity_check;" | grep -q "ok"; then
        log "INFO" "SQLite database integrity is OK"
        return 0
    else
        log "ERROR" "SQLite database integrity check failed"
        return 1
    fi
}

# Send alert notification
send_alert() {
    local subject="$1"
    local message="$2"
    local urgency="$3"  # low, normal, high
    
    # Log the alert
    log "ALERT" "$subject: $message"
    
    # Send email if mail command is available
    if command -v mail >/dev/null 2>&1; then
        echo "$message" | mail -s "$subject" admin@example.com
    fi
    
    # Write alert to file for external monitoring
    local alert_file="/var/log/refserver_alerts.log"
    echo "$(date '+%Y-%m-%d %H:%M:%S') [$urgency] $subject: $message" >> "$alert_file"
}

# Main check function
main() {
    local total_issues=0
    local critical_issues=0
    
    log "INFO" "Starting backup health check..."
    
    # Create log directory if needed
    mkdir -p "$(dirname "$LOG_FILE")"
    
    # Run all checks
    if ! check_backup_directory; then
        ((critical_issues++))
        send_alert "RefServer Backup Critical" "Backup directory is not accessible" "high"
    fi
    
    if ! check_disk_space; then
        ((critical_issues++))
        send_alert "RefServer Backup Critical" "Low disk space detected" "high"
    fi
    
    if ! check_sqlite_backups; then
        local sqlite_issues=$?
        ((total_issues += sqlite_issues))
        if [[ $sqlite_issues -gt 0 ]]; then
            send_alert "RefServer Backup Warning" "SQLite backup issues detected ($sqlite_issues issues)" "normal"
        fi
    fi
    
    if ! check_chromadb_backups; then
        local chromadb_issues=$?
        ((total_issues += chromadb_issues))
        if [[ $chromadb_issues -gt 0 ]]; then
            send_alert "RefServer Backup Warning" "ChromaDB backup issues detected ($chromadb_issues issues)" "normal"
        fi
    fi
    
    if ! check_scheduler_status; then
        ((critical_issues++))
        send_alert "RefServer Backup Critical" "Backup scheduler is not responding" "high"
    fi
    
    if ! check_database_integrity; then
        ((critical_issues++))
        send_alert "RefServer Database Critical" "Database integrity check failed" "high"
    fi
    
    # Summary
    if [[ $critical_issues -eq 0 && $total_issues -eq 0 ]]; then
        log "INFO" "All backup health checks passed"
        echo -e "${GREEN}✓ All backup systems are healthy${NC}"
        exit 0
    elif [[ $critical_issues -eq 0 ]]; then
        log "WARNING" "Backup health check completed with $total_issues warnings"
        echo -e "${YELLOW}⚠ Backup systems have $total_issues warnings${NC}"
        exit 1
    else
        log "ERROR" "Backup health check failed with $critical_issues critical issues and $total_issues total issues"
        echo -e "${RED}✗ Backup systems have critical issues${NC}"
        exit 2
    fi
}

# Show usage
usage() {
    cat << EOF
RefServer Backup Health Check Script

Usage: $0 [OPTIONS]

Options:
    --help          Show this help message
    --quiet         Suppress normal output, only show errors
    --verbose       Show detailed output

Examples:
    $0              Run standard health check
    $0 --quiet      Run quietly for cron jobs
    $0 --verbose    Run with detailed logging

Exit codes:
    0   All checks passed
    1   Warnings found
    2   Critical issues found

EOF
}

# Parse command line arguments
QUIET=false
VERBOSE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --help)
            usage
            exit 0
            ;;
        --quiet)
            QUIET=true
            ;;
        --verbose)
            VERBOSE=true
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
    shift
done

# Adjust logging based on flags
if [[ "$QUIET" == true ]]; then
    exec 1>/dev/null  # Suppress stdout
elif [[ "$VERBOSE" == true ]]; then
    set -x  # Enable debug output
fi

# Run main function
main