import os
import socket
from dotenv import load_dotenv
from waitress import serve
from app import app
import requests

dotenv_path = os.path.join(os.path.dirname(__file__), 'src', '.env')
load_dotenv(dotenv_path)

def get_public_ip():
    try:
        # Get internal IP
        hostname = socket.gethostname()
        internal_ip = socket.gethostbyname(hostname)
        public_ip = requests.get('https://api.ipify.org').text
        
        return internal_ip, public_ip
    except Exception as e:
        print(f"Could not determine IP: {e}")
        return "Unknown internal IP", "Unknown public IP"

if __name__ == '__main__':
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5000))
        
    internal_ip, public_ip = get_public_ip()
    print(f"Internal IP address: {internal_ip}")
    print(f"Public IP address: {public_ip}")
    print(f"Accessible at: \nhttp://{internal_ip}:{port} (local network)")
    print(f"If port forwarding is configured, it may be accessible at: \nhttp://{public_ip}:{port} (internet)")
    
    serve(app, host=host, port=port)

## NOTE: for foreground `python waitress_server.py` and background `pythonw waitress_server.py`