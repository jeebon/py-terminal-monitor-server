from app import app, heartbeat_monitor
from server_utils import start_server_with_monitor

def run_flask_server(app, host, port, debug):
    app.run(
        host=host,
        port=port,
        debug=debug,
        use_reloader=False  # Disable reloader to prevent heartbeat monitor issues
    )

if __name__ == '__main__':
    start_server_with_monitor(
        app=app,
        heartbeat_monitor=heartbeat_monitor,
        server_runner_func=run_flask_server,
        server_type="Flask Development"
    )