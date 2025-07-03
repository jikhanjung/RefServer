#!/usr/bin/env python3
"""
Migrate database to add GPU task tracking fields
"""

import os
import sys
import logging
from pathlib import Path

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app'))

from models import db, Paper, ProcessingJob
from peewee import BooleanField
from playhouse.migrate import migrate, SqliteMigrator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def add_gpu_task_fields():
    """Add GPU task tracking fields to Paper and ProcessingJob models"""
    
    # Create migrator
    migrator = SqliteMigrator(db)
    
    # Fields to add to Paper model
    paper_fields = [
        ('ocr_quality_completed', BooleanField(default=False)),
        ('layout_completed', BooleanField(default=False)),
        ('metadata_llm_completed', BooleanField(default=False))
    ]
    
    # Fields to add to ProcessingJob model
    job_fields = [
        ('ocr_quality_pending', BooleanField(default=False)),
        ('layout_pending', BooleanField(default=False)),
        ('metadata_llm_pending', BooleanField(default=False))
    ]
    
    # Connect to database
    if not db.is_closed():
        db.close()
    db.connect()
    
    try:
        # Check if fields already exist
        paper_columns = [column.name for column in db.get_columns('paper')]
        job_columns = [column.name for column in db.get_columns('processingjob')]
        
        # Add fields to Paper table
        for field_name, field_type in paper_fields:
            if field_name not in paper_columns:
                logger.info(f"Adding field {field_name} to Paper table")
                migrate(
                    migrator.add_column('paper', field_name, field_type)
                )
            else:
                logger.info(f"Field {field_name} already exists in Paper table")
        
        # Add fields to ProcessingJob table
        for field_name, field_type in job_fields:
            if field_name not in job_columns:
                logger.info(f"Adding field {field_name} to ProcessingJob table")
                migrate(
                    migrator.add_column('processingjob', field_name, field_type)
                )
            else:
                logger.info(f"Field {field_name} already exists in ProcessingJob table")
        
        # Update existing papers based on current state
        logger.info("Updating existing papers with completion status...")
        
        papers = Paper.select()
        updated = 0
        
        for paper in papers:
            changes = False
            
            # Check OCR quality
            if paper.ocr_quality and paper.ocr_quality != 'unknown':
                if not paper.ocr_quality_completed:
                    paper.ocr_quality_completed = True
                    changes = True
            
            # Check layout analysis
            layout = paper.layout_analyses.first()
            if layout and layout.page_count > 0:
                if not paper.layout_completed:
                    paper.layout_completed = True
                    changes = True
            
            # Check metadata
            metadata = paper.metadata_entries.first()
            if metadata and metadata.extraction_method in ['structured_llm', 'simple_llm']:
                if not paper.metadata_llm_completed:
                    paper.metadata_llm_completed = True
                    changes = True
            
            if changes:
                paper.save()
                updated += 1
        
        logger.info(f"Updated {updated} existing papers with completion status")
        
        logger.info("Migration completed successfully!")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    add_gpu_task_fields()