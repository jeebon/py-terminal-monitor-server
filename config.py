import os
from pathlib import Path
from dotenv import load_dotenv

parent_dir = Path(__file__).resolve().parent
env_path = parent_dir / ".env"
load_dotenv(dotenv_path=env_path, override=True)

class Config:
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres@localhost:5432/postgres')
    SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL', '')
    
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 5001))
    DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 'yes', 'on')
    
    # Monitoring Configuration
    HEARTBEAT_CHECK_INTERVAL = int(os.getenv('HEARTBEAT_CHECK_INTERVAL', 300))  # 5 minutes
    STALE_INSTANCE_THRESHOLD = int(os.getenv('STALE_INSTANCE_THRESHOLD', 10))  # 10 minutes
    MAX_NOTIFICATION_COUNT = int(os.getenv('MAX_NOTIFICATION_COUNT', 3))
    
    @classmethod
    def validate(cls):
        """Validate configuration and print status"""
        print(f"📁 Config loaded from: {env_path}")
        print(f"🔗 Database URL: {cls.DATABASE_URL}")
        print(f"📢 Slack webhook configured: {'Yes' if cls.SLACK_WEBHOOK_URL else 'No'}")
        print(f"🌐 Server: {cls.HOST}:{cls.PORT}")
        print(f"🔧 Debug mode: {cls.DEBUG}")
        
        # Validate required configurations
        if not cls.DATABASE_URL:
            raise ValueError("DATABASE_URL is required")
            
        return True

# Initialize configuration on import
Config.validate()

# Export commonly used values for backward compatibility
DATABASE_URL = Config.DATABASE_URL
SLACK_WEBHOOK_URL = Config.SLACK_WEBHOOK_URL
HOST = Config.HOST
PORT = Config.PORT
DEBUG = Config.DEBUG
HEARTBEAT_CHECK_INTERVAL = Config.HEARTBEAT_CHECK_INTERVAL
STALE_INSTANCE_THRESHOLD = Config.STALE_INSTANCE_THRESHOLD
MAX_NOTIFICATION_COUNT = Config.MAX_NOTIFICATION_COUNT
