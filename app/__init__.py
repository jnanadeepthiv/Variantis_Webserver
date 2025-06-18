# Copyright (C) 2025 SharmaG-omics
#
# Variantis Production is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.


from flask import Flask
import os  # Import os for environment variables
from app.config import DevelopmentConfig, ProductionConfig  # Import configuration classes
from app.models import session_manager
from app.models import init_session_manager
import logging
from logging.handlers import RotatingFileHandler
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix


# Import blueprints
from app.routes.auth import auth_bp
from app.routes.main import main_bp
from app.routes.results import results_bp
from app.routes.uploads import uploads_bp


from dotenv import load_dotenv

def create_app():
    """
    Application factory function to create and configure the Flask app.
    """
    
    # Load environment variables
    load_dotenv()
    
    # Create the Flask app instance
    basedir = os.path.abspath(os.path.dirname(__file__))
    app = Flask(__name__,
                static_folder=os.path.join(basedir, 'static'),
                static_url_path='/sharmaglab/variantis/static'
                # template_folder=os.path.join(basedir, 'app', 'templates')
                )
    # print(os.path.join(basedir, 'static')) #DEBUG

    # Trust the first proxy in the chain
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    # Determine the environment (Development or Production)
    env = os.getenv("FLASK_ENV", "development")  # Default to "development"
    
    if env == "production":
        app.config.from_object(ProductionConfig)
    else:
        app.config.from_object(DevelopmentConfig)
        
    # Set secret key from environment
    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY")

    if not app.config["SECRET_KEY"]:
        raise ValueError("FLASK_SECRET_KEY environment variable is missing or invalid.")
    csrf = CSRFProtect(app)
    
    log_directory = "logs"
    if not os.path.exists(log_directory):
        os.makedirs(log_directory)
    
    # Configure logging
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    # Configure log rotation (store logs in `app.log`, max size 10KB, keep 3 backups)
    log_path_file = os.path.join(log_directory,  "app.log")
    log_handler = RotatingFileHandler(log_path_file, maxBytes=10000, backupCount=2)
    log_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    log_handler.setFormatter(formatter)

    # Add handler to both Flask app logger and module logger
    logger.addHandler(log_handler) 

    app.logger.addHandler(log_handler)  # Ensures Flask logs are also written to the file

    # Prevent duplicate logs
    logger.propagate = False
    
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    PRODUCT_ROOT = os.path.dirname(BASE_DIR)
    
    app.config["UPLOADS_FOLDER"] = os.path.join(PRODUCT_ROOT,"uploads")
    app.config["RESULTS_FOLDER"] = os.path.join(PRODUCT_ROOT,"results")
    
    os.makedirs(app.config["UPLOADS_FOLDER"], exist_ok =True)   
    os.makedirs(app.config["RESULTS_FOLDER"], exist_ok =True)
    
    db_path = os.path.join(app.config["RESULTS_FOLDER"], 'user_sessions.db')

    
    # Initialize the session manager and attach it to the app
    app.session_manager = init_session_manager(app, db_path, session_timeout_minutes=20)

    # If SQLiteSessionManager supports init_app(), call it
    if hasattr(session_manager, 'init_app'):
        session_manager.init_app(app)

    # Register all Blueprints under /variantis
    app.register_blueprint(auth_bp, url_prefix='/sharmaglab/variantis')
    app.register_blueprint(main_bp, url_prefix='/sharmaglab/variantis')
    app.register_blueprint(results_bp, url_prefix='/sharmaglab/variantis')
    app.register_blueprint(uploads_bp, url_prefix='/sharmaglab/variantis')

    
    # Initialize and start APScheduler
    from app.utils.file_handlers import cleanup_job  # Import the cleanup function

    scheduler = BackgroundScheduler()
    scheduler.add_job(cleanup_job, "interval", minutes=15, args=[app])
    scheduler.start()

    # Ensure scheduler shuts down when Flask stops
    atexit.register(lambda: scheduler.shutdown())

    # Return the configured app
    return app