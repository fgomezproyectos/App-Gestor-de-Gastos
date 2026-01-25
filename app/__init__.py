from flask import Flask
from config import Config

def create_app():
    """Application factory."""
    app = Flask(__name__, 
                template_folder='../templates',
                static_folder='../static')
    
    app.config.from_object(Config)
    
    # Initialize database
    from app.models import inicializar_bd
    inicializar_bd()
    
    # Register blueprints
    from app.auth import auth_bp
    from app.gastos import gastos_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(gastos_bp)
    
    return app
