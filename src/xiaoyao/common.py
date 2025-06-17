class JointInfo:
    """关节信息类"""
    def __init__(self):
        self.joint_id: int = 0
        self.angle: float = 0.0
        self.speed: float = 0.0
        self.torque: float = 0.0
        self.status: int = 0