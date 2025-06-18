#!/usr/bin/env python3
"""
Admin user management CLI for RefServer
"""

import sys
import argparse
import getpass
from pathlib import Path

# Add app directory to Python path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir))

from auth import AuthManager
from models import db, AdminUser

def init_db():
    """Initialize database connection"""
    try:
        # Override database path for local development (same as migrate.py)
        local_data_dir = Path(__file__).parent / 'data'
        if not local_data_dir.exists():
            local_data_dir.mkdir(parents=True, exist_ok=True)
            print(f"Created data directory: {local_data_dir}")
        
        # Use local database path instead of /data
        local_db_path = local_data_dir / 'refserver.db'
        
        print(f"Database path: {local_db_path}")
        
        # Override database path temporarily
        db.init(str(local_db_path))
        
        if db.is_closed():
            db.connect()
        
        # Create tables if they don't exist
        from models import Paper, PageEmbedding, Embedding, Metadata, LayoutAnalysis, AdminUser
        db.create_tables([Paper, PageEmbedding, Embedding, Metadata, LayoutAnalysis, AdminUser], safe=True)
        
        return True
    except Exception as e:
        print(f"Database connection error: {e}")
        return False

def create_user(args):
    """Create a new admin user"""
    if not init_db():
        return
    
    # Get password securely
    if not args.password:
        password = getpass.getpass("Enter password: ")
        confirm_password = getpass.getpass("Confirm password: ")
        
        if password != confirm_password:
            print("Passwords don't match!")
            return
    else:
        password = args.password
    
    # Create user
    user = AuthManager.create_user(
        username=args.username,
        password=password,
        email=args.email,
        full_name=args.full_name,
        is_superuser=args.superuser
    )
    
    if user:
        print(f"Admin user '{args.username}' created successfully!")
        print(f"Email: {user.email}")
        print(f"Full name: {user.full_name}")
        print(f"Superuser: {user.is_superuser}")
    else:
        print(f"Failed to create user '{args.username}'")

def list_users(args):
    """List all admin users"""
    if not init_db():
        return
    
    users = AuthManager.list_users()
    
    if not users:
        print("No admin users found.")
        return
    
    print(f"{'Username':<15} {'Email':<25} {'Full Name':<20} {'Active':<8} {'Super':<8} {'Last Login':<20}")
    print("-" * 100)
    
    for user in users:
        last_login = user.last_login.strftime("%Y-%m-%d %H:%M") if user.last_login else "Never"
        print(f"{user.username:<15} {user.email or 'N/A':<25} {user.full_name or 'N/A':<20} "
              f"{'Yes' if user.is_active else 'No':<8} {'Yes' if user.is_superuser else 'No':<8} {last_login:<20}")

def change_password(args):
    """Change user password"""
    if not init_db():
        return
    
    # Check if user exists
    user = AuthManager.get_user(args.username)
    if not user:
        print(f"User '{args.username}' not found!")
        return
    
    # Get passwords securely
    old_password = getpass.getpass("Enter current password: ")
    new_password = getpass.getpass("Enter new password: ")
    confirm_password = getpass.getpass("Confirm new password: ")
    
    if new_password != confirm_password:
        print("New passwords don't match!")
        return
    
    # Change password
    if AuthManager.change_password(args.username, old_password, new_password):
        print(f"Password changed successfully for user '{args.username}'")
    else:
        print(f"Failed to change password for user '{args.username}'")

def deactivate_user(args):
    """Deactivate a user"""
    if not init_db():
        return
    
    # Confirm action
    confirm = input(f"Are you sure you want to deactivate user '{args.username}'? (y/N): ")
    if confirm.lower() != 'y':
        print("Operation cancelled.")
        return
    
    if AuthManager.deactivate_user(args.username):
        print(f"User '{args.username}' deactivated successfully")
    else:
        print(f"Failed to deactivate user '{args.username}'")

def ensure_default_admin(args):
    """Ensure default admin user exists"""
    if not init_db():
        return
    
    if AuthManager.ensure_default_admin():
        print("Default admin user ensured (admin/admin123)")
    else:
        print("Failed to ensure default admin user")

def main():
    parser = argparse.ArgumentParser(description="RefServer Admin User Management")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Create user command
    create_parser = subparsers.add_parser("create", help="Create a new admin user")
    create_parser.add_argument("username", help="Username for the new user")
    create_parser.add_argument("--email", help="Email address")
    create_parser.add_argument("--full-name", help="Full name")
    create_parser.add_argument("--password", help="Password (will prompt if not provided)")
    create_parser.add_argument("--superuser", action="store_true", help="Grant superuser privileges")
    create_parser.set_defaults(func=create_user)
    
    # List users command
    list_parser = subparsers.add_parser("list", help="List all admin users")
    list_parser.set_defaults(func=list_users)
    
    # Change password command
    passwd_parser = subparsers.add_parser("passwd", help="Change user password")
    passwd_parser.add_argument("username", help="Username to change password for")
    passwd_parser.set_defaults(func=change_password)
    
    # Deactivate user command
    deactivate_parser = subparsers.add_parser("deactivate", help="Deactivate a user")
    deactivate_parser.add_argument("username", help="Username to deactivate")
    deactivate_parser.set_defaults(func=deactivate_user)
    
    # Ensure default admin command
    default_parser = subparsers.add_parser("ensure-default", help="Ensure default admin user exists")
    default_parser.set_defaults(func=ensure_default_admin)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    args.func(args)

if __name__ == "__main__":
    main()