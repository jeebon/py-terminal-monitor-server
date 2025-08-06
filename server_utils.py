import socket
import requests
from config import Config, HOST, PORT, DEBUG

def get_local_ip():
    """Get the local IP address of this machine"""
    try:
        # Connect to a remote address to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        # Fallback to hostname resolution
        try:
            hostname = socket.gethostname()
            return socket.gethostbyname(hostname)
        except Exception:
            return "127.0.0.1"

def get_public_ip():
    """Get the public IP address (if accessible)"""
    try:
        response = requests.get('https://api.ipify.org', timeout=5)
        return response.text.strip()
    except Exception:
        return "Unknown"

def print_server_info(host, port, server_type="Flask Development"):
    """Print server startup information"""
    local_ip = get_local_ip()
    public_ip = get_public_ip()
    
    print("=" * 60)
    print(f"Terminal Monitor Server Starting ({server_type})...")
    print("=" * 60)
    print(f"Local IP: {local_ip}")
    print(f"Public IP: {public_ip}")
    print(f"Local Access: http://localhost:{port}")
    print(f"Network Access: http://{local_ip}:{port}")
    if public_ip != "Unknown":
        print(f"Internet Access: http://{public_ip}:{port} (if port forwarded)")
    print("=" * 60)
    print("Dashboard: Access the web interface at the URLs above")
    print("API Endpoints:")
    print(f"   POST /instance/start  - Register new instance")
    print(f"   POST /instance/alive  - Send heartbeat")
    print(f"   POST /instance/crash  - Report crash")
    print(f"   POST /instance/stop   - Report stop")
    print(f"   GET  /instances       - List all instances")
    print(f"   GET  /health          - Health check")
    print("=" * 60)
    if server_type == "Flask Development":
        print("Development Mode: Flask Built-in Server")
    else:
        print("Production Mode: Waitress WSGI Server")
    print("Press Ctrl+C to stop the server")
    print("=" * 60)

def get_server_config():
    """Get server configuration from centralized config"""
    return HOST, PORT, DEBUG


## Including monitoring logic for heartbeat management
def start_server_with_monitor(app, heartbeat_monitor, server_runner_func, server_type="Flask Development"):
    """Common server startup logic with heartbeat monitor management"""
    host, port, debug = get_server_config()
    
    # Print server information
    print_server_info(host, port, server_type)
    
    # Start heartbeat monitor
    heartbeat_monitor.start()
    
    try:
        # Run the server with the provided runner function
        server_runner_func(app, host, port, debug)
    except KeyboardInterrupt:
        print("\nServer shutdown requested...")
    finally:
        # Stop heartbeat monitor on exit
        print("Stopping heartbeat monitor...")
        heartbeat_monitor.stop()
        print("Server stopped successfully")
