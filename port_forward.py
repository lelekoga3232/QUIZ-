import socket
import threading
import sys
import time
import webbrowser
import subprocess
import os

class PortForwarder:
    def __init__(self, local_port=5000, public_port=8080):
        self.local_port = local_port
        self.public_port = public_port
        self.running = False
        self.server_socket = None
        self.connections = []
        self.lock = threading.Lock()

    def start(self):
        """Start the port forwarding server"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            # Bind to all interfaces
            self.server_socket.bind(('0.0.0.0', self.public_port))
            self.server_socket.listen(5)
            self.running = True
            
            print(f"\n* Port forwarding active:")
            print(f"* Local URL: http://localhost:{self.local_port}")
            print(f"* Network URL: http://{self.get_local_ip()}:{self.public_port}")
            print("* Share the Network URL with others on your local network to access your quiz")
            print("* Press Ctrl+C to stop the server\n")
            
            # Open browser with the network URL
            webbrowser.open(f"http://{self.get_local_ip()}:{self.public_port}")
            
            # Accept connections in a separate thread
            accept_thread = threading.Thread(target=self.accept_connections)
            accept_thread.daemon = True
            accept_thread.start()
            
            return True
        except Exception as e:
            print(f"Error starting port forwarding: {e}")
            return False

    def accept_connections(self):
        """Accept incoming connections and start forwarding threads"""
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                print(f"New connection from {address[0]}:{address[1]}")
                
                with self.lock:
                    self.connections.append(client_socket)
                
                # Start a new thread to handle this connection
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, address)
                )
                client_thread.daemon = True
                client_thread.start()
            except Exception as e:
                if self.running:
                    print(f"Error accepting connection: {e}")
                break

    def handle_client(self, client_socket, address):
        """Handle client connection by forwarding to local service"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        try:
            # Connect to the local service
            server_socket.connect(('localhost', self.local_port))
            
            # Set up bidirectional forwarding
            client_to_server = threading.Thread(
                target=self.forward_data,
                args=(client_socket, server_socket)
            )
            server_to_client = threading.Thread(
                target=self.forward_data,
                args=(server_socket, client_socket)
            )
            
            client_to_server.daemon = True
            server_to_client.daemon = True
            
            client_to_server.start()
            server_to_client.start()
            
            # Wait for threads to complete
            client_to_server.join()
            server_to_client.join()
        except Exception as e:
            print(f"Error handling client {address[0]}:{address[1]}: {e}")
        finally:
            # Clean up
            try:
                server_socket.close()
            except:
                pass
            
            try:
                client_socket.close()
            except:
                pass
            
            with self.lock:
                if client_socket in self.connections:
                    self.connections.remove(client_socket)

    def forward_data(self, source, destination):
        """Forward data from source socket to destination socket"""
        try:
            buffer_size = 4096
            while self.running:
                try:
                    data = source.recv(buffer_size)
                    if not data:
                        break
                    destination.sendall(data)
                except ConnectionResetError:
                    break
                except Exception as e:
                    print(f"Error forwarding data: {e}")
                    break
        except:
            pass

    def stop(self):
        """Stop the port forwarding server"""
        self.running = False
        
        # Close all client connections
        with self.lock:
            for conn in self.connections:
                try:
                    conn.close()
                except:
                    pass
            self.connections = []
        
        # Close server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
            self.server_socket = None

    def get_local_ip(self):
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

def run_with_port_forwarding():
    """Run the Flask app with port forwarding"""
    local_port = 5000
    public_port = 8080
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        try:
            public_port = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port number: {sys.argv[1]}. Using default port {public_port}.")
    
    # Start port forwarding
    forwarder = PortForwarder(local_port, public_port)
    if not forwarder.start():
        print("Failed to start port forwarding. Exiting.")
        return
    
    # Start the Flask app in a separate process
    flask_process = None
    try:
        # Start the Flask app
        print("Starting Flask application...")
        flask_process = subprocess.Popen(
            ["python", "app.py"],
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        
        # Keep the script running
        while True:
            time.sleep(1)
            
            # Check if Flask process is still running
            if flask_process.poll() is not None:
                print("Flask application has stopped. Shutting down port forwarding.")
                break
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        # Clean up
        if flask_process and flask_process.poll() is None:
            print("Stopping Flask application...")
            flask_process.terminate()
            flask_process.wait()
        
        print("Stopping port forwarding...")
        forwarder.stop()
        print("Port forwarding stopped.")

if __name__ == "__main__":
    run_with_port_forwarding()
