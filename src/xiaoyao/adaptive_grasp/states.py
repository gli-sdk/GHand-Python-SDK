from enum import Enum


class GraspState(Enum):
    IDLE = "idle"
    OPEN = "open"
    PRE_GRASP = "pre_grasp"
    CLOSING_TO_CONTACT = "closing_to_contact"
    ADAPTIVE_HOLD = "adaptive_hold"
    RELEASE = "release"
    COMPLETED = "completed"
    ERROR = "error"
    STOPPED = "stopped"

