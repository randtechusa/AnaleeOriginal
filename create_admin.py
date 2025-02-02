"""Create admin user script"""
from app import create_app, db
from models import User
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_admin_user():
    """Create admin user if it doesn't exist"""
    app = create_app()
    with app.app_context():
        try:
            # Check if admin exists
            admin = User.query.filter_by(email='admin@example.com').first()
            if not admin:
                admin = User(
                    username='admin',
                    email='admin@example.com',
                    is_admin=True,
                    is_active=True,
                    created_at=datetime.utcnow()
                )
                admin.set_password('admin123')
                db.session.add(admin)
                db.session.commit()
                logger.info("Admin user created successfully")
                return True
            else:
                logger.info("Admin user already exists")
                return True
        except Exception as e:
            logger.error(f"Error creating admin user: {str(e)}")
            db.session.rollback()
            return False

if __name__ == '__main__':
    create_admin_user()