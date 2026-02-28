#!/usr/bin/env python3
"""
Simple HTTP server for the dashboard with cache-busting headers.
This ensures the browser always loads the latest version of the files.
"""

from http.server import HTTPServer, SimpleHTTPRequestHandler
import os

class NoCacheHTTPRequestHandler(SimpleHTTPRequestHandler):
    """HTTP request handler that disables caching."""

    def end_headers(self):
        """Add cache-busting headers before sending headers."""
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def log_message(self, format, *args):
        """Custom log format."""
        print(f"[Dashboard] {format % args}")


def serve_dashboard(port=8080):
    """Start the dashboard HTTP server."""
    # Change to dashboard directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    server_address = ('', port)
    httpd = HTTPServer(server_address, NoCacheHTTPRequestHandler)

    print(f"\n{'='*60}")
    print(f"Dashboard Server Started!")
    print(f"{'='*60}")
    print(f"")
    print(f"  Main Dashboard:    http://localhost:{port}/index.html")
    print(f"  Option Chain:      http://localhost:{port}/option_chain.html")
    print(f"")
    print(f"  Cache-busting:     ENABLED (always loads latest version)")
    print(f"  API Backend:       http://localhost:5000")
    print(f"")
    print(f"{'='*60}")
    print(f"Press Ctrl+C to stop the server\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\nShutting down server...")
        httpd.shutdown()


if __name__ == '__main__':
    serve_dashboard()
