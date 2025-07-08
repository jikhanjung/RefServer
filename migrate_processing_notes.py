#!/usr/bin/env python3
"""
Database migration script to add processing_notes field to Paper model
"""

import os
import sys
import logging

# Add the app directory to Python path
sys.path.insert(0, '/refserver/app')

from models import db, Paper
from playhouse.migrate import migrate, SqliteMigrator
from peewee import TextField

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_processing_notes():
    """Add processing_notes field to Paper table"""
    try:
        # Create migrator
        migrator = SqliteMigrator(db)
        
        # Check if field already exists
        cursor = db.execute_sql("PRAGMA table_info(paper)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'processing_notes' in columns:
            logger.info("processing_notes field already exists in Paper table")
            return True
        
        # Add processing_notes field
        logger.info("Adding processing_notes field to Paper table...")
        
        processing_notes_field = TextField(null=True)
        
        migrate(
            migrator.add_column('paper', 'processing_notes', processing_notes_field)
        )
        
        logger.info("Successfully added processing_notes field to Paper table")
        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False

if __name__ == "__main__":
    logger.info("Starting database migration for processing_notes field...")
    
    # Connect to database
    try:
        db.connect()
        logger.info("Connected to database")
        
        # Run migration
        success = migrate_processing_notes()
        
        if success:
            logger.info("Migration completed successfully")
            sys.exit(0)
        else:
            logger.error("Migration failed")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        sys.exit(1)
    finally:
        if not db.is_closed():
            db.close()