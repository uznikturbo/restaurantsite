from flask import Flask

import models
from extensions import db, login_manager, migrate
from utils import Config


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    
    login_manager.init_app(app)
    login_manager.login_view = "main.login" 
    
    from main import main_bp
    app.register_blueprint(main_bp)

    return app