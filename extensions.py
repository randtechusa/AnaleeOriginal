"""Flask extensions initialization"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect

# Initialize Flask extensions
db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
migrate = Migrate()

def init_extensions(app):
    """Initialize all Flask extensions"""
    # Initialize SQLAlchemy first
    db.init_app(app)

    # Then initialize other extensions
    login_manager.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)

    # Configure login
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'

    @login_manager.user_loader
    def load_user(user_id):
        from models import User
        return User.query.get(int(user_id))