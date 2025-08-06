from waitress import serve
from app import app, heartbeat_monitor
from server_utils import start_server_with_monitor

def run_waitress_server(app, host, port, debug):
    serve(app, host=host, port=port)

if __name__ == '__main__':
    start_server_with_monitor(
        app=app,
        heartbeat_monitor=heartbeat_monitor,
        server_runner_func=run_waitress_server,
        server_type="Waitress WSGI"
    )

# NOTE: Use python for foreground, pythonw for background on macOS/Windows