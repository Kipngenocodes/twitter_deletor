import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///twitter_manager.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Twitter API credentials - replace with your own
    TWITTER_API_KEY = os.environ.get('TWITTER_API_KEY')
    TWITTER_API_SECRET = os.environ.get('TWITTER_API_SECRET')
    TWITTER_CALLBACK_URL = 'http://127.0.0.1:5000/callback'