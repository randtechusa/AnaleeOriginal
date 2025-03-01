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
    """Initialize all Flask extensions with enhanced monitoring"""
    from sqlalchemy import event, text
    from sqlalchemy.engine import Engine
    import logging
    import time
    import os
    
    logger = logging.getLogger('database')
    
    # Make sure the SQLALCHEMY_ENGINE_OPTIONS is properly initialized
    if 'SQLALCHEMY_ENGINE_OPTIONS' not in app.config:
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {}
    
    # Only configure event listeners for PostgreSQL connections
    # SQLite connections can cause issues with these listeners
    if 'sqlite' not in app.config['SQLALCHEMY_DATABASE_URI'].lower():
        try:
            from utils.db_health import DatabaseHealth
            db_health = DatabaseHealth.get_instance()
            
            @event.listens_for(Engine, "engine_connect")
            def engine_connect(conn, branch):
                if not branch:
                    try:
                        conn.execute(text('SELECT 1'))
                    except Exception as e:
                        logger.error(f"Connection test failed: {e}")
                        raise

            @event.listens_for(Engine, "before_cursor_execute")
            def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
                conn.info.setdefault('query_start_time', []).append(time.time())
                logger.debug("Starting Query: %s", statement)

            @event.listens_for(Engine, "after_cursor_execute")
            def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
                total = time.time() - conn.info['query_start_time'].pop()
                logger.debug("Query Complete! Time: %f", total)
                if total > 1.0:  # Log slow queries
                    logger.warning("Slow Query Detected: %s", statement)
        except Exception as e:
            logger.warning(f"Failed to set up database monitoring: {e}")
    else:
        logger.info("Using SQLite backend - database monitoring reduced")
        # Make sure SQLite engine options don't include PostgreSQL-specific options
        if 'SQLALCHEMY_ENGINE_OPTIONS' in app.config:
            sqlite_compatible_options = {}
            for key, value in app.config['SQLALCHEMY_ENGINE_OPTIONS'].items():
                if key not in ['pool_size', 'max_overflow']:
                    sqlite_compatible_options[key] = value
            app.config['SQLALCHEMY_ENGINE_OPTIONS'] = sqlite_compatible_options

    # Initialize SQLAlchemy with monitoring
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