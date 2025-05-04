import socket
import webbrowser
import subprocess
import os
import time
import sys

def get_local_ip():
    """Get the local IP address of this machine"""
    try:
        # Create a socket to determine the local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Doesn't need to be reachable
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        # Fallback
        return socket.gethostbyname(socket.gethostname())

def run_network_quiz():
    """Run the quiz application with network access"""
    # Get local IP address
    local_ip = get_local_ip()
    
    # Default port
    port = 5000
    
    # Parse command line arguments for custom port
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port number: {sys.argv[1]}. Using default port {port}.")
    
    # Print access information
    print("\n" + "="*60)
    print(f"Quiz Application Network Access")
    print("="*60)
    print(f"Local URL:     http://localhost:{port}")
    print(f"Network URL:   http://{local_ip}:{port}")
    print("\nShare the Network URL with others on your local network")
    print("to access your quiz from other devices.")
    print("\nPress Ctrl+C to stop the server")
    print("="*60 + "\n")
    
    # Open browser with the local URL
    webbrowser.open(f"http://localhost:{port}")
    
    # Set environment variables to make Flask listen on all interfaces
    os.environ['FLASK_RUN_HOST'] = '0.0.0.0'
    os.environ['FLASK_RUN_PORT'] = str(port)
    
    # Run the Flask app directly
    # This ensures all WebSocket connections work properly
    os.system(f"python app.py")

if __name__ == "__main__":
    run_network_quiz()
