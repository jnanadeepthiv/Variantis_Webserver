import os

class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY")
    DEBUG = False
    SESSION_COOKIE_SECURE = True  # Secure cookies for production

class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False  # Allow insecure cookies for local testing

class ProductionConfig(Config):
    DEBUG = False  # Disable debugging in production
    