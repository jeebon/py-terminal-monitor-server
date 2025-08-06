# Terminal Monitor Server

A Flask-based monitoring server for tracking terminal/script instances with Slack notifications and PostgreSQL storage.

## 🚀 Quick Start

### Prerequisites
- Python 3.7+
- PostgreSQL database
- Slack webhook URL (optional)

### Installation
```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env  # Edit with your configuration
```

### Running the Server

#### Development Mode (Flask built-in server)
```bash
python main.py
```
- Best for development and debugging
- Auto-reloading disabled to prevent threading issues
- Debug mode enabled by default

#### Production Mode (Waitress WSGI server)
```bash
python waitress_server.py    # Foreground
pythonw waitress_server.py   # Background (macOS/Windows)
```
- Production-optimized performance
- Better stability and concurrency
- Recommended for deployment

## 📁 Project Structure

```
├── app.py                  # Main Flask application with API endpoints
├── config.py               # Centralized configuration management
├── main.py                 # Development server entry point
├── waitress_server.py      # Production server entry point
├── server_utils.py         # Shared utilities for both servers
├── requirements.txt        # Python dependencies
├── .env.example            # Environment configuration template
├── templates/
│   └── dashboard.html      # Web dashboard template
└── .env                    # Environment configuration (create from .env.example)
```

## 🔧 Environment Variables

Create a `.env` file from the template:

```bash
cp .env.example .env  # Then edit with your values
```

Configuration options:

```env
# Database Configuration (Required)
DATABASE_URL=postgresql://postgres@localhost:5432/credoiq_db

# Slack Integration (Optional)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK

# Server Configuration
HOST=0.0.0.0
PORT=5001
DEBUG=True

# Monitoring Configuration (Optional)
HEARTBEAT_CHECK_INTERVAL=300      # Seconds between heartbeat checks
STALE_INSTANCE_THRESHOLD=10       # Minutes before instance considered stale
MAX_NOTIFICATION_COUNT=3          # Max notifications before marking as crashed
```

## 🔌 API Endpoints

### Instance Management
- `POST /instance/start` - Register new instance
- `POST /instance/alive` - Send heartbeat
- `POST /instance/crash` - Report crash
- `POST /instance/stop` - Report graceful stop
- `GET /instances` - List all instances (JSON)

### Monitoring
- `GET /` - Web dashboard
- `GET /health` - Health check

## 📊 Features

- **Real-time Monitoring**: Track instance heartbeats and status
- **Slack Notifications**: Automatic alerts for crashes and stale instances
- **Web Dashboard**: Visual interface for monitoring instances
- **PostgreSQL Storage**: Persistent instance data storage
- **Background Monitoring**: Automatic detection of stale instances
- **Graceful Shutdown**: Proper cleanup on server stop

## 🏗️ Architecture

The server consists of:

1. **Flask App** (`app.py`): Core API and web interface
2. **Database Manager**: PostgreSQL connection and operations
3. **Slack Notifier**: Webhook-based notifications
4. **Heartbeat Monitor**: Background thread for stale instance detection
5. **Server Runners**: Development (Flask) and production (Waitress) entry points

## 📱 Usage Example

```python
import requests

# Register instance
response = requests.post('http://localhost:5001/instance/start', json={
    'scrapper_key': 'my-script-v1',
    'hostname': 'server-01'
})
instance_id = response.json()['instance_id']

# Send heartbeat
requests.post('http://localhost:5001/instance/alive', json={
    'instance_id': instance_id
})

# Report crash
requests.post('http://localhost:5001/instance/crash', json={
    'instance_id': instance_id,
    'error_message': 'Connection timeout'
})
```

## 🔄 Development

The project uses a modular design with shared utilities to minimize code duplication:

- `server_utils.py` contains common functionality
- `main.py` and `waitress_server.py` are thin wrappers
- Easy to extend with new server types or configurations
