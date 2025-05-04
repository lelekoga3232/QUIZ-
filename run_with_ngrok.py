from flask import Flask
from pyngrok import ngrok
import os
import sys
import subprocess
import webbrowser
import time

def run_with_ngrok():
    # Get the port from command line args or use default 5000
    port = 5000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port number: {sys.argv[1]}. Using default port 5000.")
    
    # Start ngrok tunnel
    public_url = ngrok.connect(port).public_url
    print(f"\n* Quiz application is running at: {public_url}")
    print("* Share this URL with others to access your quiz from anywhere!")
    print("* Your local URL is: http://localhost:5000")
    print("* Press Ctrl+C to stop the application\n")
    
    # Open the ngrok URL in the browser
    webbrowser.open(public_url)
    
    # Run the Flask app
    os.system(f"python app.py")

if __name__ == "__main__":
    run_with_ngrok()
