from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
import json


def serve(evidence, port=8765):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/api/state':
                data = json.dumps(evidence.snapshot(), allow_nan=False).encode()
                mime = 'application/json'
            elif self.path == '/brain.js':
                data = files('lauff').joinpath('web/brain.js').read_bytes()
                mime = 'text/javascript; charset=utf-8'
            elif self.path == '/':
                data = files('lauff').joinpath('web/index.html').read_bytes()
                mime = 'text/html; charset=utf-8'
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'")
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        def log_message(self, *_):
            pass
    return ThreadingHTTPServer(('127.0.0.1', port), Handler)
