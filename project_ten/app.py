"""Read-only local HTTP dashboard. Binds to loopback by default."""
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
from .storage import REPORTS

STATIC=Path(__file__).resolve().parent.parent/'web'

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(STATIC),**kwargs)
    def do_GET(self):
        if self.path.split('?')[0]=='/api/state':
            fp=REPORTS/'dashboard.json'
            if not fp.exists():
                self.send_error(503,'Generate an example with python -m project_ten demo first')
                return
            data=fp.read_bytes()
            self.send_response(200);self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)))
            self.end_headers();self.wfile.write(data);return
        return super().do_GET()


def serve(host='127.0.0.1',port=8765):
    server=ThreadingHTTPServer((host,port),Handler)
    print(f'Project Ten dashboard: http://{host}:{port}')
    print('Local read-only dashboard. Ctrl+C to stop.')
    try:server.serve_forever()
    finally:server.server_close()
