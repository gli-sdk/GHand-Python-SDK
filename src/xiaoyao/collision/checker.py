"""
碰撞检测器包装类

提供简化的接口，桥接 Collision SDK 和 DexHand 类。
支持延迟加载，仅在首次使用时初始化。
"""

import logging
import numpy as np
from xiaoyao.collision.core.sdk import CollisionSDK, CollisionCheckResult
from xiaoyao.collision.converter import joints_to_nparray, nparray_to_joints
from xiaoyao.dexhand import Joint

logger = logging.getLogger("xiaoyao.collision.checker")


class CollisionChecker:
    """
    碰撞检测器包装类

    提供简化的接口用于关节碰撞检测。采用延迟加载策略，
    首次调用 check() 方法时才初始化 CollisionSDK。
    """

    def __init__(self):
        """
        初始化碰撞检测器

        注意：CollisionSDK 会在首次调用 check() 时延迟加载
        """
        self._sdk: CollisionSDK | None = None
        self._is_loaded = False

    def check(self, joints: list[Joint], safety_margin: float = 0.0,
              current_joints: list[Joint] | None = None) -> CollisionCheckResult:
        """
        检查关节姿态是否发生碰撞

        Args:
            joints: 目标关节列表（可以不包含全部18个关节）
            safety_margin: 安全边距，范围 [0.0, 1.0]
                          0.0 = 无边距（精确接触）
                          1.0 = 最大边距（2mm）
            current_joints: 当前关节状态（用于填充未指定的关节）
                          如果为 None，未指定的关节默认为 0°

        Returns:
            CollisionCheckResult: 碰撞检测结果
                - has_collision: 是否发生碰撞
                - safe_angles: 安全角度（18个关节的numpy数组），如果无碰撞则为None
                - collision_pairs: 碰撞对列表，如果无碰撞则为None

        Raises:
            CollisionCheckError: 数据文件缺失或加载失败

        Example:
            >>> checker = CollisionChecker()
            >>> joints = [Joint(id=JointId.THUMB_PIP, angle=1.5)]
            >>> result = checker.check(joints, safety_margin=0.5)
            >>> if result.has_collision:
            ...     print("Collision detected!")
            ...     safe_joints = nparray_to_joints(result.safe_angles)
        """
        # 延迟加载 CollisionSDK
        if not self._is_loaded:
            self._load_runtime()

        # 转换 Joint 列表为 numpy 数组
        angles = joints_to_nparray(joints, current_joints)

        # 执行碰撞检测
        try:
            result = self._sdk.collision_check(angles, safety_margin)
            return result
        except FileNotFoundError as e:
            from xiaoyao.collision.exceptions import CollisionCheckError
            raise CollisionCheckError(f"数据文件未找到: {e}")
        except Exception as e:
            from xiaoyao.collision.exceptions import CollisionCheckError
            raise CollisionCheckError(f"碰撞检测失败: {e}")

    def _load_runtime(self):
        """
        加载碰撞检测运行时环境

        首次调用 check() 时自动执行。加载 STL 模型、关节数据等。
        """
        if self._is_loaded:
            return

        logger.info("正在加载碰撞检测数据...")
        try:
            self._sdk = CollisionSDK()
            self._is_loaded = True
            logger.info("碰撞检测数据加载完成")
        except Exception as e:
            logger.error(f"碰撞检测数据加载失败: {e}")
            from xiaoyao.collision.exceptions import CollisionCheckError
            raise CollisionCheckError(f"运行时初始化失败: {e}")

    def is_loaded(self) -> bool:
        """
        检查碰撞检测运行时是否已加载

        Returns:
            bool: 如果已加载返回 True，否则返回 False
        """
        return self._is_loaded


__all__ = ['CollisionChecker']
