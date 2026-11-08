import json
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer


class H(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        ok = self.path == "/sign-requests" and self.headers.get("Authorization") == "Bearer mock-api-key" and body["document"]["content_base64"]
        self.send_response(201 if ok else 401)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"request_id": f"REQ-{uuid.uuid4().hex[:8]}", "sign_url": "https://mock-esign.local/sign"} if ok else {"error": "bad"}).encode())

    def log_message(self, *a):
        pass


HTTPServer(("127.0.0.1", 8099), H).serve_forever()
