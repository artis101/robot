import cv2
import numpy as np
from config import Config


class ImageProcessor:
    @staticmethod
    def process_frame(frame):
        if frame.shape[2] == 4:
            frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2RGB)

        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

        # Threshold to get line
        _, thresh = cv2.threshold(
            gray, Config.THRESHOLD_VALUE, 255, cv2.THRESH_BINARY_INV
        )

        # Store threshold image for display
        with Config.thresh_lock:
            Config.latest_thresh = thresh.copy()

        # Get top half of image
        height = thresh.shape[0]
        search_bottom = height // Config.SEARCH_HEIGHT_RATIO
        top_half = thresh[0:search_bottom, :]

        # Find the line in the top half
        contours, _ = cv2.findContours(
            top_half, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        if contours:
            largest_contour = max(contours, key=cv2.contourArea)
            rect = cv2.minAreaRect(largest_contour)
            box = cv2.boxPoints(rect)
            box = np.int0(box)

            cx = int(rect[0][0])
            cy = int(rect[0][1])

            return cx, cy, thresh, Config.THRESHOLD_VALUE, box

        return None, None, thresh, Config.THRESHOLD_VALUE, None

    @staticmethod
    def create_debug_frame(frame, line_data, error, left_speed, right_speed):
        line_pos_x, line_pos_y, thresh, thresh_value, box = line_data

        if frame.shape[2] == 4:
            debug_frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2RGB)
        else:
            debug_frame = frame.copy()

        # Draw search area
        height = frame.shape[0]
        search_bottom = height // Config.SEARCH_HEIGHT_RATIO
        cv2.rectangle(
            debug_frame, (0, 0), (frame.shape[1], search_bottom), (0, 255, 255), 1
        )

        # Draw info text
        cv2.putText(
            debug_frame,
            f"Threshold: {thresh_value} | Mode: {Config.control_mode}",
            (10, 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            1,
        )

        if line_pos_x is not None and box is not None:
            # Draw bounding box and center
            cv2.drawContours(debug_frame, [box], 0, (0, 0, 255), 2)
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

        return debug_frame
