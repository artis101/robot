#!/usr/bin/python3
import cv2
import numpy as np
from picamera2 import Picamera2
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from datetime import datetime

# Global variables
latest_frame = None
latest_thresh = None
latest_metrics = {
    "line_position": None,
    "error": None,
    "left_speed": 0,
    "right_speed": 0,
    "timestamp": None,
    "threshold_value": 127,
    "control_mode": "auto",
}
frame_lock = threading.Lock()
thresh_lock = threading.Lock()
metrics_lock = threading.Lock()

# Control variables
control_mode = "auto"  # 'auto' or 'manual'
manual_left_speed = 0
manual_right_speed = 0
controller_lock = threading.Lock()


class StreamingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            html = """
                <html>
                <head>
                    <title>Line Follower Monitor</title>
                    <style>
                        body { font-family: Arial, sans-serif; margin: 20px; }
                        .container { display: flex; gap: 20px; }
                        .metrics { width: 300px; }
                        .views { display: flex; flex-direction: column; gap: 10px; }
                        .view-container { border: 1px solid #ccc; padding: 10px; }
                        .controls { 
                            margin-top: 20px;
                            padding: 10px;
                            border: 1px solid #ccc;
                            border-radius: 5px;
                        }
                        .control-status {
                            margin-top: 10px;
                            font-family: monospace;
                        }
                        .mode-button {
                            padding: 10px 20px;
                            font-size: 16px;
                            cursor: pointer;
                            background-color: #4CAF50;
                            color: white;
                            border: none;
                            border-radius: 5px;
                            margin-bottom: 10px;
                        }
                        .mode-button.manual {
                            background-color: #f44336;
                        }
                    </style>
                    <script>
                        let gamepad = null;
                        let controlMode = 'auto';
                        let isGamepadConnected = false;

                        function updateMetrics() {
                            fetch('/metrics')
                                .then(response => response.json())
                                .then(data => {
                                    document.getElementById('metrics').innerHTML = 
                                        `<pre>${JSON.stringify(data, null, 2)}</pre>`;
                                });
                        }

                        function toggleMode() {
                            controlMode = controlMode === 'auto' ? 'manual' : 'auto';
                            const button = document.getElementById('modeButton');
                            button.textContent = `Mode: ${controlMode}`;
                            button.classList.toggle('manual');
                            
                            // Reset speeds when switching to auto
                            if (controlMode === 'auto') {
                                sendControlUpdate(0, 0);
                            }
                        }

                        function updateGamepadStatus() {
                            const gamepads = navigator.getGamepads();
                            for (let gp of gamepads) {
                                if (gp) {
                                    gamepad = gp;
                                    isGamepadConnected = true;
                                    break;
                                }
                            }
                            
                            const statusEl = document.getElementById('gamepadStatus');
                            if (isGamepadConnected) {
                                statusEl.textContent = `Connected: ${gamepad.id}`;
                                statusEl.style.color = 'green';
                            } else {
                                statusEl.textContent = 'No gamepad detected';
                                statusEl.style.color = 'red';
                            }
                        }

                        function scaleStickValue(value) {
                            // Add deadzone
                            if (Math.abs(value) < 0.1) return 0;
                            // Scale to -100 to 100
                            return Math.round(value * 100);
                        }

                        function processGamepad() {
                            if (!isGamepadConnected || controlMode === 'auto') return;
                            
                            gamepad = navigator.getGamepads()[gamepad.index];
                            
                            // Left stick for left track (vertical axis)
                            const leftSpeed = -scaleStickValue(gamepad.axes[1]);
                            // Right stick for right track (vertical axis)
                            const rightSpeed = -scaleStickValue(gamepad.axes[3]);
                            
                            sendControlUpdate(leftSpeed, rightSpeed);
                        }

                        function sendControlUpdate(leftSpeed, rightSpeed) {
                            fetch('/control', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                },
                                body: JSON.stringify({
                                    mode: controlMode,
                                    left_speed: leftSpeed,
                                    right_speed: rightSpeed
                                })
                            });
                        }

                        // Setup event listeners
                        window.addEventListener("gamepadconnected", (e) => {
                            console.log("Gamepad connected:", e.gamepad);
                            gamepad = e.gamepad;
                            isGamepadConnected = true;
                            updateGamepadStatus();
                        });

                        window.addEventListener("gamepaddisconnected", (e) => {
                            console.log("Gamepad disconnected:", e.gamepad);
                            isGamepadConnected = false;
                            updateGamepadStatus();
                            if (controlMode === 'manual') {
                                sendControlUpdate(0, 0);  // Stop when controller disconnects
                            }
                        });

                        // Main loop
                        setInterval(() => {
                            updateGamepadStatus();
                            processGamepad();
                        }, 50);  // 20Hz update rate

                        // Update views
                        setInterval(() => {
                            document.getElementById('frame').src = '/frame?' + new Date().getTime();
                            document.getElementById('threshold').src = '/threshold?' + new Date().getTime();
                            updateMetrics();
                        }, 1000);
                    </script>
                </head>
                <body>
                    <h1>Line Follower Monitor</h1>
                    <div class="container">
                        <div class="views">
                            <div class="view-container">
                                <h3>Main View</h3>
                                <img src="/frame" id="frame" style="width:320px;height:240px">
                            </div>
                            <div class="view-container">
                                <h3>Threshold View</h3>
                                <img src="/threshold" id="threshold" style="width:320px;height:240px">
                            </div>
                            <div class="controls">
                                <button id="modeButton" class="mode-button" onclick="toggleMode()">Mode: auto</button>
                                <div id="gamepadStatus" class="control-status">No gamepad detected</div>
                            </div>
                        </div>
                        <div class="metrics">
                            <h2>Metrics</h2>
                            <div id="metrics"></div>
                        </div>
                    </div>
                </body>
                </html>
            """
            self.wfile.write(html.encode())

        elif self.path.startswith("/frame"):
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.end_headers()
            with frame_lock:
                if latest_frame is not None:
                    _, jpeg = cv2.imencode(".jpg", latest_frame)
                    self.wfile.write(jpeg.tobytes())

        elif self.path.startswith("/threshold"):
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.end_headers()
            with thresh_lock:
                if latest_thresh is not None:
                    thresh_color = cv2.cvtColor(latest_thresh, cv2.COLOR_GRAY2BGR)
                    _, jpeg = cv2.imencode(".jpg", thresh_color)
                    self.wfile.write(jpeg.tobytes())

        elif self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            with metrics_lock:
                self.wfile.write(json.dumps(latest_metrics).encode())

    def do_POST(self):
        if self.path == "/control":
            content_length = int(self.headers["Content-Length"])
            post_data = json.loads(self.rfile.read(content_length))

            global control_mode, manual_left_speed, manual_right_speed
            with controller_lock:
                control_mode = post_data["mode"]
                if control_mode == "manual":
                    manual_left_speed = post_data["left_speed"]
                    manual_right_speed = post_data["right_speed"]

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())


def run_server(server_class=HTTPServer, handler_class=StreamingHandler, port=8000):
    server_address = ("", port)
    httpd = server_class(server_address, handler_class)
    print(f"Starting monitoring server on port {port}")
    httpd.serve_forever()


def process_frame(frame):
    global latest_thresh

    if frame.shape[2] == 4:
        frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2RGB)

    # Convert to grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

    # Threshold to get line
    thresh_value = 127
    _, thresh = cv2.threshold(gray, thresh_value, 255, cv2.THRESH_BINARY_INV)

    # Store threshold image for display
    with thresh_lock:
        latest_thresh = thresh.copy()

    # Get top half of image
    height = thresh.shape[0]
    search_bottom = height // 2
    top_half = thresh[0:search_bottom, :]

    # Find the line in the top half
    contours, _ = cv2.findContours(top_half, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if contours:
        # Find the largest contour
        largest_contour = max(contours, key=cv2.contourArea)

        # Get the minimum area rectangle instead of boundingRect
        rect = cv2.minAreaRect(largest_contour)
        box = cv2.boxPoints(rect)
        box = np.int0(box)

        # Calculate center from the rotated rectangle
        cx = int(rect[0][0])
        cy = int(rect[0][1])

        return cx, cy, thresh, thresh_value, box
    return None, None, thresh, thresh_value, None


def update_monitoring_data(frame, line_data, error, left_speed, right_speed):
    global latest_frame, latest_metrics

    line_pos_x, line_pos_y, thresh, thresh_value, box = line_data

    with frame_lock:
        if frame.shape[2] == 4:
            debug_frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2RGB)
        else:
            debug_frame = frame.copy()

        # Draw search area rectangle (top half)
        height = frame.shape[0]
        search_bottom = height // 2
        cv2.rectangle(
            debug_frame, (0, 0), (frame.shape[1], search_bottom), (0, 255, 255), 1
        )

        # Draw threshold value and control mode
        cv2.putText(
            debug_frame,
            f"Threshold: {thresh_value} | Mode: {control_mode}",
            (10, 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            1,
        )

        if line_pos_x is not None and box is not None:
            # Draw rotated bounding box
            cv2.drawContours(debug_frame, [box], 0, (0, 0, 255), 2)

            # Draw detected center
            cv2.circle(debug_frame, (line_pos_x, line_pos_y), 5, (0, 255, 0), -1)

            # Draw error line
            center_x = frame.shape[1] // 2
            cv2.line(
                debug_frame,
                (center_x, line_pos_y),
                (line_pos_x, line_pos_y),
                (0, 255, 0),
                2,
            )

            # Draw error value
            cv2.putText(
                debug_frame,
                f"Error: {error}",
                (10, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                1,
            )

        latest_frame = debug_frame

    with metrics_lock:
        latest_metrics.update(
            {
                "line_position": line_pos_x,
                "error": error,
                "left_speed": left_speed,
                "right_speed": right_speed,
                "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                "threshold_value": thresh_value,
                "control_mode": control_mode,
            }
        )


def main():
    # Start monitoring server in a separate thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Setup camera
    picam = Picamera2()
    config = picam.create_video_configuration(
        main={"size": (320, 240), "format": "RGB888"},
        raw=picam.sensor_modes[0],
        controls={"FrameDurationLimits": (100000, 100000)},  # 10 FPS
    )
    picam.configure(config)
    picam.start()

    try:
        while True:
            frame = picam.capture_array()
            line_data = process_frame(frame)
            line_pos_x = line_data[0]

            with controller_lock:
                current_mode = control_mode
                if current_mode == "manual":
                    left_speed = manual_left_speed
                    right_speed = manual_right_speed
                    update_monitoring_data(
                        frame, line_data, None, left_speed, right_speed
                    )
                else:  # Auto mode
                    if line_pos_x is not None:
                        error = frame.shape[1] / 2 - line_pos_x
                        if abs(error) < 10:
                            left_speed = right_speed = 50  # Go straight
                        elif error > 0:
                            left_speed, right_speed = 30, 70  # Turn left
                        else:
                            left_speed, right_speed = 70, 30  # Turn right
                        update_monitoring_data(
                            frame, line_data, error, left_speed, right_speed
                        )
                    else:
                        # No line found
                        update_monitoring_data(
                            frame,
                            (None, None, line_data[2], line_data[3], None),
                            None,
                            0,
                            0,
                        )

            time.sleep(0.01)

    except KeyboardInterrupt:
        picam.stop()
        print("\nShutting down...")


if __name__ == "__main__":
    main()
