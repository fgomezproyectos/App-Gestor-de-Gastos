import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Configuration settings for the Flask app."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret')
    DATABASE_URL = os.environ.get('DATABASE_URL')
    
    if not DATABASE_URL:
        raise Exception("Error: DATABASE_URL environment variable is not set.")
