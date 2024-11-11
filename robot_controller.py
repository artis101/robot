from config import Config


class RobotController:
    @staticmethod
    def calculate_motor_speeds(frame_width, line_pos_x):
        if line_pos_x is None:
            return 0, 0

        error = frame_width / 2 - line_pos_x

        if abs(error) < Config.ERROR_TOLERANCE:
            # Go straight
            return Config.STRAIGHT_SPEED, Config.STRAIGHT_SPEED
        elif error > 0:
            # Turn left
            return Config.TURN_SPEED_SLOW, Config.TURN_SPEED_FAST
        else:
            # Turn right
            return Config.TURN_SPEED_FAST, Config.TURN_SPEED_SLOW
