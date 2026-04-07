from enum import Enum


class GraspState(Enum):
    IDLE = "idle"
    OPENING = "opening"
    PRE_GRASPING = "pre_grasping"
    CLOSING = "closing"
    ADAPTIVE_HOLDING = "adaptive_holding"
    RELEASING = "releasing"
    COMPLETED = "completed"
    ERROR = "error"
    STOPPED = "stopped"

