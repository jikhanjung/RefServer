#!/usr/bin/env python3
"""
Database initialization script for RefServer
Run this once during Docker container setup
"""

import os
import sys
import logging

# Import from current directory (app files are copied to /app)
from db import initialize_database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Initialize database with migrations"""
    try:
        logger.info("Starting database initialization...")
        
        success = initialize_database()
        
        if success:
            logger.info("Database initialization completed successfully")
            
            # Ensure default admin user exists
            try:
                from auth import AuthManager
                logger.info("Checking for default admin user...")
                
                if AuthManager.ensure_default_admin():
                    logger.info("✅ Default admin user ensured (username: admin, password: admin123)")
                else:
                    logger.warning("⚠️ Failed to create default admin user")
                    
            except Exception as e:
                logger.error(f"Error creating default admin user: {e}")
            
            sys.exit(0)
        else:
            logger.error("Database initialization failed")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()