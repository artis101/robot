from picamera2 import Picamera2
import time
from datetime import datetime
import threading
from http.server import HTTPServer

from config import Config
from web_server import StreamingHandler
from image_processor import ImageProcessor
from robot_controller import RobotController


def run_server():
    server_address = ("", Config.SERVER_PORT)
    httpd = HTTPServer(server_address, StreamingHandler)
    print(f"Starting monitoring server on port {Config.SERVER_PORT}")
    httpd.serve_forever()


def main():
    # Start monitoring server
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Setup camera
    picam = Picamera2()
    config = picam.create_video_configuration(
        main={"size": Config.CAMERA_RESOLUTION, "format": Config.CAMERA_FORMAT},
        raw=picam.sensor_modes[0],
        controls={
            "FrameDurationLimits": (
                int(1e6 / Config.CAMERA_FPS),
                int(1e6 / Config.CAMERA_FPS),
            )
        },
    )
    picam.configure(config)
    picam.start()

    try:
        while True:
            frame = picam.capture_array()
            line_data = ImageProcessor.process_frame(frame)
            line_pos_x = line_data[0]

            with Config.controller_lock:
                if Config.control_mode == "manual":
                    left_speed = Config.manual_left_speed
                    right_speed = Config.manual_right_speed
                else:  # Auto mode
                    left_speed, right_speed = RobotController.calculate_motor_speeds(
                        frame.shape[1], line_pos_x
                    )

                error = (
                    frame.shape[1] / 2 - line_pos_x if line_pos_x is not None else None
                )

                # Update debug frame and metrics
                debug_frame = ImageProcessor.create_debug_frame(
                    frame, line_data, error, left_speed, right_speed
                )

                with Config.frame_lock:
                    Config.latest_frame = debug_frame

                with Config.metrics_lock:
                    Config.latest_metrics.update(
                        {
                            "line_position": line_pos_x,
                            "error": error,
                            "left_speed": left_speed,
                            "right_speed": right_speed,
                            "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                            "threshold_value": Config.THRESHOLD_VALUE,
                            "control_mode": Config.control_mode,
                        }
                    )

            time.sleep(0.01)

    except KeyboardInterrupt:
        picam.stop()
        print("\nShutting down...")


if __name__ == "__main__":
    main()
