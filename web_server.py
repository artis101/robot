import cv2
import os
import json
from http.server import BaseHTTPRequestHandler
from config import Config


class StreamingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()

            # Load the HTML template
            template_path = os.path.join(
                os.path.dirname(__file__), "templates", "index.html"
            )
            with open(template_path, "r") as f:
                template = f.read()

            self.wfile.write(template.encode())

        elif self.path.startswith("/frame"):
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.end_headers()
            with Config.frame_lock:
                if Config.latest_frame is not None:
                    _, jpeg = cv2.imencode(".jpg", Config.latest_frame)
                    self.wfile.write(jpeg.tobytes())

        elif self.path.startswith("/threshold"):
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.end_headers()
            with Config.thresh_lock:
                if Config.latest_thresh is not None:
                    thresh_color = cv2.cvtColor(
                        Config.latest_thresh, cv2.COLOR_GRAY2BGR
                    )
                    _, jpeg = cv2.imencode(".jpg", thresh_color)
                    self.wfile.write(jpeg.tobytes())

        elif self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            with Config.metrics_lock:
                self.wfile.write(json.dumps(Config.latest_metrics).encode())

    def do_POST(self):
        if self.path == "/control":
            content_length = int(self.headers["Content-Length"])
            post_data = json.loads(self.rfile.read(content_length))

            with Config.controller_lock:
                Config.control_mode = post_data["mode"]
                if Config.control_mode == "manual":
                    Config.manual_left_speed = post_data["left_speed"]
                    Config.manual_right_speed = post_data["right_speed"]

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
