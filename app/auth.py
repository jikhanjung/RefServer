import bcrypt
import datetime
import logging
from typing import Optional
from models import AdminUser

logger = logging.getLogger(__name__)

class AuthManager:
    """Admin user authentication manager"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt"""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False
    
    @staticmethod
    def authenticate_user(username: str, password: str) -> Optional[AdminUser]:
        """Authenticate user with username and password"""
        try:
            user = AdminUser.get(
                (AdminUser.username == username) & 
                (AdminUser.is_active == True)
            )
            
            if AuthManager.verify_password(password, user.password_hash):
                # Update last login time
                user.last_login = datetime.datetime.now()
                user.save()
                logger.info(f"User {username} authenticated successfully")
                return user
            else:
                logger.warning(f"Invalid password for user {username}")
                return None
                
        except AdminUser.DoesNotExist:
            logger.warning(f"User {username} not found")
            return None
        except Exception as e:
            logger.error(f"Authentication error for user {username}: {e}")
            return None
    
    @staticmethod
    def create_user(username: str, password: str, email: str = None, 
                   full_name: str = None, is_superuser: bool = False) -> Optional[AdminUser]:
        """Create a new admin user"""
        try:
            # Check if username already exists
            if AdminUser.select().where(AdminUser.username == username).exists():
                logger.error(f"Username {username} already exists")
                return None
            
            # Check if email already exists (if provided)
            if email and AdminUser.select().where(AdminUser.email == email).exists():
                logger.error(f"Email {email} already exists")
                return None
            
            # Hash password
            password_hash = AuthManager.hash_password(password)
            
            # Create user
            user = AdminUser.create(
                username=username,
                password_hash=password_hash,
                email=email,
                full_name=full_name,
                is_superuser=is_superuser,
                is_active=True
            )
            
            logger.info(f"Admin user {username} created successfully")
            return user
            
        except Exception as e:
            logger.error(f"Error creating user {username}: {e}")
            return None
    
    @staticmethod
    def change_password(username: str, old_password: str, new_password: str) -> bool:
        """Change user password"""
        try:
            user = AdminUser.get(AdminUser.username == username)
            
            # Verify old password
            if not AuthManager.verify_password(old_password, user.password_hash):
                logger.warning(f"Invalid old password for user {username}")
                return False
            
            # Update password
            user.password_hash = AuthManager.hash_password(new_password)
            user.updated_at = datetime.datetime.now()
            user.save()
            
            logger.info(f"Password changed for user {username}")
            return True
            
        except AdminUser.DoesNotExist:
            logger.error(f"User {username} not found")
            return False
        except Exception as e:
            logger.error(f"Error changing password for user {username}: {e}")
            return False
    
    @staticmethod
    def deactivate_user(username: str) -> bool:
        """Deactivate a user account"""
        try:
            user = AdminUser.get(AdminUser.username == username)
            user.is_active = False
            user.updated_at = datetime.datetime.now()
            user.save()
            
            logger.info(f"User {username} deactivated")
            return True
            
        except AdminUser.DoesNotExist:
            logger.error(f"User {username} not found")
            return False
        except Exception as e:
            logger.error(f"Error deactivating user {username}: {e}")
            return False
    
    @staticmethod
    def get_user(username: str) -> Optional[AdminUser]:
        """Get user by username"""
        try:
            return AdminUser.get(AdminUser.username == username)
        except AdminUser.DoesNotExist:
            return None
    
    @staticmethod
    def list_users() -> list:
        """List all admin users"""
        try:
            return list(AdminUser.select().order_by(AdminUser.created_at))
        except Exception as e:
            logger.error(f"Error listing users: {e}")
            return []
    
    @staticmethod
    def ensure_default_admin():
        """Ensure default admin user exists"""
        try:
            # Check if any admin users exist
            if AdminUser.select().count() == 0:
                default_user = AuthManager.create_user(
                    username="admin",
                    password="admin123",
                    email="admin@refserver.local", 
                    full_name="Default Admin",
                    is_superuser=True
                )
                
                if default_user:
                    logger.info("Default admin user created: admin/admin123")
                    return True
                else:
                    logger.error("Failed to create default admin user")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error ensuring default admin: {e}")
            return False

def get_current_user_from_session(session: dict) -> Optional[AdminUser]:
    """Get current user from session data"""
    if not session or "user" not in session:
        return None
    
    user_data = session["user"]
    if "username" not in user_data:
        return None
    
    return AuthManager.get_user(user_data["username"])