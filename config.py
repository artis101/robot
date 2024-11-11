import threading


class Config:
    # Camera settings
    CAMERA_RESOLUTION = (320, 240)
    CAMERA_FORMAT = "RGB888"
    CAMERA_FPS = 10  # 1/0.0001 seconds

    # Processing settings
    THRESHOLD_VALUE = 127
    SEARCH_HEIGHT_RATIO = 2  # Divide height by this to get search area

    # Control settings
    STRAIGHT_SPEED = 50
    TURN_SPEED_SLOW = 30
    TURN_SPEED_FAST = 70
    ERROR_TOLERANCE = 10

    # Server settings
    SERVER_PORT = 8000

    # Global state (with thread-safe access)
    latest_frame = None
    latest_thresh = None
    latest_metrics = {
        "line_position": None,
        "error": None,
        "left_speed": 0,
        "right_speed": 0,
        "timestamp": None,
        "threshold_value": THRESHOLD_VALUE,
        "control_mode": "auto",
    }

    # Locks for thread-safe access
    frame_lock = threading.Lock()
    thresh_lock = threading.Lock()
    metrics_lock = threading.Lock()

    # Control state
    control_mode = "auto"
    manual_left_speed = 0
    manual_right_speed = 0
    controller_lock = threading.Lock()
