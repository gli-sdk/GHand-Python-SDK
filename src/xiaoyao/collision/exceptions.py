"""
碰撞检测模块的异常类
"""

from xiaoyao.exceptions import XiaoyaoError


class CollisionCheckError(XiaoyaoError):
    """碰撞检测失败异常

    当碰撞检测数据文件缺失、损坏或加载失败时抛出。

    Attributes:
        reason: 错误原因描述
    """

    def __init__(self, reason: str):
        """
        初始化碰撞检测异常

        Args:
            reason: 错误原因描述，如"数据文件未找到"或"STL模型加载失败"
        """
        self.reason = reason
        super().__init__(f"碰撞检测失败: {reason}")


    def __str__(self):
        return f"CollisionCheckError: {self.reason}"


__all__ = ['CollisionCheckError']
