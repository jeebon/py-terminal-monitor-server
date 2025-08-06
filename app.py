import os
from pathlib import Path
import uuid
import socket
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from flask import Flask, request, jsonify, render_template
from dataclasses import dataclass, asdict
import psycopg2
import psycopg2.extras
import threading
import time
import requests
import json
from dotenv import load_dotenv

## load dotenv current directory .env
parent_dir = Path(__file__).resolve().parent
env_path = parent_dir / ".env"
load_dotenv(dotenv_path=env_path, override=True)
print(f"env_path: {env_path}")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL', 'https://hooks.slack.com/services/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')
MONITORING_DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres@localhost:5432/credoiq_db')
PORT = int(os.getenv('PORT', 5001))
print(f"Using database URL: {MONITORING_DATABASE_URL}, {SLACK_WEBHOOK_URL}")

@dataclass
class InstanceInfo:
    instance_id: str
    scrapper_key: str
    hostname: str
    status: str  # 'running', 'crashed', 'stopped'
    created_at: str
    last_heartbeat: Optional[str] = None
    error_message: Optional[str] = None
    notification_count: int = 0

class DatabaseManager:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.init_database()
    
    def get_connection(self):
        """Get a database connection"""
        return psycopg2.connect(self.database_url)
    
    def init_database(self):
        """Initialize the database with required tables"""
        try:
            with self.get_connection() as conn:
                print("🔗 connected to PostgreSQL database...")
                with conn.cursor() as cursor:
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS monitoring_instances (
                            instance_id VARCHAR(255) PRIMARY KEY,
                            scrapper_key VARCHAR(255) UNIQUE NOT NULL,
                            hostname VARCHAR(255) NOT NULL,
                            status VARCHAR(50) NOT NULL,
                            created_at TIMESTAMP NOT NULL,
                            last_heartbeat TIMESTAMP,
                            error_message TEXT,
                            notification_count INTEGER DEFAULT 0
                        )
                    ''')
                    
                    # Create unique constraint on scrapper_key if it doesn't exist
                    cursor.execute('''
                        DO $$ 
                        BEGIN
                            ALTER TABLE monitoring_instances 
                            ADD CONSTRAINT unique_scrapper_key UNIQUE (scrapper_key);
                        EXCEPTION
                            WHEN duplicate_table THEN NULL;
                        END $$;
                    ''')
                    
                    conn.commit()
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise
    
    def create_instance(self, instance_info: InstanceInfo) -> bool:
        """Create a new instance record or reactivate existing one"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # Check if scrapper_key already exists
                    cursor.execute('''
                        SELECT instance_id, status FROM monitoring_instances 
                        WHERE scrapper_key = %s
                    ''', (instance_info.scrapper_key,))
                    
                    existing = cursor.fetchone()
                    
                    if existing:
                        existing_instance_id, existing_status = existing
                        
                        if existing_status == 'running':
                            logger.warning(f"Scrapper key {instance_info.scrapper_key} already running as {existing_instance_id}")
                            return False
                        else:
                            # Reactivate existing instance
                            cursor.execute('''
                                UPDATE monitoring_instances 
                                SET status = %s, last_heartbeat = %s, error_message = NULL, 
                                    notification_count = 0, instance_id = %s
                                WHERE scrapper_key = %s
                            ''', (
                                instance_info.status,
                                instance_info.last_heartbeat,
                                instance_info.instance_id,
                                instance_info.scrapper_key
                            ))
                            logger.info(f"Reactivated instance for scrapper key {instance_info.scrapper_key}")
                    else:
                        # Create new instance
                        cursor.execute('''
                            INSERT INTO monitoring_instances 
                            (instance_id, scrapper_key, hostname, status, created_at, last_heartbeat, error_message, notification_count)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ''', (
                            instance_info.instance_id,
                            instance_info.scrapper_key,
                            instance_info.hostname,
                            instance_info.status,
                            instance_info.created_at,
                            instance_info.last_heartbeat,
                            instance_info.error_message,
                            instance_info.notification_count
                        ))
                        logger.info(f"Created new instance for scrapper key {instance_info.scrapper_key}")
                    
                    conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error creating instance: {e}")
            return False
    
    def update_instance_status(self, instance_id: str, status: str, error_message: str = None) -> bool:
        """Update instance status"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('''
                        UPDATE monitoring_instances 
                        SET status = %s, last_heartbeat = %s, error_message = %s
                        WHERE instance_id = %s
                    ''', (status, datetime.now().isoformat(), error_message, instance_id))
                    conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating instance status: {e}")
            return False
    
    def update_heartbeat(self, instance_id: str) -> bool:
        """Update instance heartbeat"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('''
                        UPDATE monitoring_instances 
                        SET last_heartbeat = %s
                        WHERE instance_id = %s
                    ''', (datetime.now().isoformat(), instance_id))
                    conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating heartbeat: {e}")
            return False
    
    def get_stale_instances(self, minutes: int = 10) -> list:
        """Get instances that haven't sent heartbeat in specified minutes"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    cursor.execute('''
                        SELECT * FROM monitoring_instances 
                        WHERE status = 'running' 
                        AND last_heartbeat < %s 
                        AND notification_count < 3
                        ORDER BY last_heartbeat ASC
                    ''', (datetime.now() - timedelta(minutes=minutes),))
                    return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error fetching stale instances: {e}")
            return []
    
    def increment_notification_count(self, instance_id: str) -> bool:
        """Increment notification count for an instance"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('''
                        UPDATE monitoring_instances 
                        SET notification_count = notification_count + 1
                        WHERE instance_id = %s
                    ''', (instance_id,))
                    conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error incrementing notification count: {e}")
            return False
    
    def mark_as_crashed(self, instance_id: str) -> bool:
        """Mark instance as crashed after max notifications"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('''
                        UPDATE monitoring_instances 
                        SET status = 'crashed', error_message = 'No heartbeat received'
                        WHERE instance_id = %s
                    ''', (instance_id,))
                    conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error marking as crashed: {e}")
            return False
    
    def get_all_instances(self) -> list:
        """Get all instances"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    cursor.execute('SELECT * FROM monitoring_instances ORDER BY created_at DESC')
                    return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error fetching instances: {e}")
            return []

class SlackNotifier:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    def send_notification(self, message: str, color: str = "warning") -> bool:
        """Send notification to Slack"""
        if not self.webhook_url:
            logger.warning("Slack webhook URL not configured")
            return False
        
        payload = {
            "attachments": [
                {
                    "color": color,
                    "text": message,
                    "ts": int(datetime.now().timestamp())
                }
            ]
        }
        
        try:
            response = requests.post(
                self.webhook_url,
                data=json.dumps(payload),
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            response.raise_for_status()
            logger.info("Slack notification sent successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return False

class HeartbeatMonitor:
    """Background worker to monitor instance heartbeats"""
    
    def __init__(self, db_manager: DatabaseManager, slack_notifier: SlackNotifier):
        self.db_manager = db_manager
        self.slack_notifier = slack_notifier
        self.running = False
        self.thread = None
    
    def start(self):
        """Start the heartbeat monitoring thread"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.thread.start()
            logger.info("Heartbeat monitor started")
    
    def stop(self):
        """Stop the heartbeat monitoring thread"""
        self.running = False
        if self.thread:
            self.thread.join()
            logger.info("Heartbeat monitor stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                # Check for stale instances (no heartbeat in 10 minutes)
                stale_instances = self.db_manager.get_stale_instances(minutes=10)
                
                for instance in stale_instances:
                    instance_id = instance['instance_id']
                    scrapper_key = instance['scrapper_key']
                    hostname = instance['hostname']
                    notification_count = instance['notification_count']
                    
                    if notification_count < 3:
                        # Send notification and increment count
                        message = f"⚠️ Instance {instance_id} (scrapper: {scrapper_key}) on {hostname} has not sent heartbeat for 10+ minutes"
                        self.slack_notifier.send_notification(message, "warning")
                        self.db_manager.increment_notification_count(instance_id)
                        logger.warning(f"Sent heartbeat warning for {instance_id} (count: {notification_count + 1})")
                    
                    elif notification_count >= 3:
                        # Mark as crashed after 3 notifications
                        self.db_manager.mark_as_crashed(instance_id)
                        message = f"🔴 Instance {instance_id} (scrapper: {scrapper_key}) on {hostname} marked as crashed - no heartbeat received"
                        self.slack_notifier.send_notification(message, "danger")
                        logger.error(f"Marked {instance_id} as crashed after 3 notifications")
                
                # Sleep for 5 minutes before next check
                time.sleep(300)
                
            except Exception as e:
                logger.error(f"Error in heartbeat monitor: {e}")
                time.sleep(60)  # Sleep for 1 minute on error

# Initialize components
db_manager = DatabaseManager(MONITORING_DATABASE_URL)
slack_notifier = SlackNotifier(SLACK_WEBHOOK_URL)
heartbeat_monitor = HeartbeatMonitor(db_manager, slack_notifier)

@app.route('/instance/start', methods=['POST'])
def start_instance():
    """Register a new instance as started"""
    try:
        data = request.get_json() or {}
        hostname = data.get('hostname', socket.gethostname())
        scrapper_key = data.get('scrapper_key')
        
        if not scrapper_key:
            return jsonify({
                'status': 'error',
                'message': 'scrapper_key is required'
            }), 400
        
        # Generate unique instance ID
        instance_id = f"{hostname}_{scrapper_key}_{uuid.uuid4().hex[:8]}"
        
        instance_info = InstanceInfo(
            instance_id=instance_id,
            scrapper_key=scrapper_key,
            hostname=hostname,
            status='running',
            created_at=datetime.now().isoformat(),
            last_heartbeat=datetime.now().isoformat(),
            notification_count=0
        )
        
        success = db_manager.create_instance(instance_info)
        
        if success:
            # Send Slack notification
            message = f"🟢 New instance started: {instance_id} (scrapper: {scrapper_key}) on {hostname}"
            slack_notifier.send_notification(message, "good")
            
            return jsonify({
                'status': 'success',
                'instance_id': instance_id,
                'scrapper_key': scrapper_key,
                'message': 'Instance registered successfully'
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to register instance - scrapper key may already be running'
            }), 409
            
    except Exception as e:
        logger.error(f"Error in start_instance: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/instance/alive', methods=['POST'])
def instance_alive():
    """Update instance heartbeat"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No data provided'}), 400
        
        instance_id = data.get('instance_id')
        if not instance_id:
            return jsonify({'status': 'error', 'message': 'instance_id is required'}), 400
        
        success = db_manager.update_heartbeat(instance_id)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': 'Heartbeat updated successfully'
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to update heartbeat'
            }), 500
            
    except Exception as e:
        logger.error(f"Error in instance_alive: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/instance/crash', methods=['POST'])
def report_crash():
    """Report an instance crash"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No data provided'}), 400
        
        instance_id = data.get('instance_id')
        error_message = data.get('error_message', 'Unknown error')
        hostname = data.get('hostname', socket.gethostname())
        
        if not instance_id:
            return jsonify({'status': 'error', 'message': 'instance_id is required'}), 400
        
        # Update instance status in database
        success = db_manager.update_instance_status(instance_id, 'crashed', error_message)
        
        if success:
            # Send Slack notification
            message = f"🔴 Instance crashed: {instance_id} on {hostname}\nError: {error_message}"
            slack_notifier.send_notification(message, "danger")
            
            return jsonify({
                'status': 'success',
                'message': 'Crash reported successfully'
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to update instance status'
            }), 500
            
    except Exception as e:
        logger.error(f"Error in report_crash: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/instance/stop', methods=['POST'])
def report_stop():
    """Report an instance stop (graceful shutdown)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No data provided'}), 400
        
        instance_id = data.get('instance_id')
        hostname = data.get('hostname', socket.gethostname())
        
        if not instance_id:
            return jsonify({'status': 'error', 'message': 'instance_id is required'}), 400
        
        # Update instance status in database
        success = db_manager.update_instance_status(instance_id, 'stopped')
        
        if success:
            # Send Slack notification
            message = f"🟡 Instance stopped: {instance_id} on {hostname}"
            slack_notifier.send_notification(message, "warning")
            
            return jsonify({
                'status': 'success',
                'message': 'Stop reported successfully'
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to update instance status'
            }), 500
            
    except Exception as e:
        logger.error(f"Error in report_stop: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/instances', methods=['GET'])
def get_instances():
    """Get all instances in JSON format"""
    try:
        instances = db_manager.get_all_instances()
        return jsonify({
            'status': 'success',
            'instances': instances,
            'count': len(instances)
        }), 200
        
    except Exception as e:
        logger.error(f"Error in get_instances: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/')
def dashboard():
    """Web dashboard for viewing instances"""
    return render_template('dashboard.html')

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    }), 200


if __name__ == '__main__':
    # Start heartbeat monitor
    heartbeat_monitor.start()
    
    try:
        app.run(host='0.0.0.0', port=PORT, debug=True)
    finally:
        # Stop heartbeat monitor on exit
        heartbeat_monitor.stop()
