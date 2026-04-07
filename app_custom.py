from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import subprocess
import os

BASE_DIR = "/opt/scripts/custom_data"
SCRIPT = "/opt/scripts/lms-custom-stats.sh"
TOKEN = "2uUdz3lRCsfDCwEzsziu"

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)

        # ✅ RUN
        if parsed.path == "/run-script":
            params = parse_qs(parsed.query)
            token = params.get("token", [None])[0]

            if token != TOKEN:
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b"Forbidden")
                return

            try:
                # ✅ non bloquant
                subprocess.Popen([SCRIPT])

                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Script launched")

            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode())

            return

        if parsed.path == "/run":
            params = parse_qs(parsed.query)
            token = params.get("token", [""])[0]

            if token != TOKEN:
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b"Forbidden")
                return

            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()

            self.wfile.write(f"""
            <html>
            <body style="font-family:sans-serif;text-align:center;margin-top:40px;">
                <h2>🚀 Running script...</h2>

                <script>
                    fetch('/run-script?token={TOKEN}')
                        .then(() => {{
                            document.body.innerHTML = "<h2>Done</h2>";
                            setTimeout(() => window.close(), 800);
                        }})
                        .catch(() => {{
                            document.body.innerHTML = "<h2>Error</h2>";
                        }});
                </script>
            </body>
            </html>
            """.encode())

        # ✅ FILES
        if parsed.path.startswith("/files"):
            path = parsed.path.replace("/files", "")
            file_path = os.path.join(BASE_DIR, path.strip("/"))

            if os.path.exists(file_path):
                self.send_response(200)
                self.end_headers()
                with open(file_path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Not found")
            return

        # ✅ fallback obligatoire
        self.send_response(404)
        self.end_headers()
        self.wfile.write(b"Not Found")


httpd = HTTPServer(("0.0.0.0", 5000), Handler)
httpd.serve_forever()
