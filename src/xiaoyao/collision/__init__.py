"""
Xiaoyao SDK 碰撞检测模块

提供灵巧手姿态碰撞检测和安全角搜索功能。

注意：此功能需要额外的依赖项。
安装方法：pip install -e .[collision]
"""

# 尝试导入碰撞检测模块
try:
    from xiaoyao.collision.checker import CollisionChecker
    from xiaoyao.collision.exceptions import CollisionCheckError
    _collision_available = True
except ImportError as e:
    # 依赖未安装时定义占位符类
    _collision_available = False
    _missing_deps = str(e).split("'")[1] if "'" in str(e) else "unknown"

    class CollisionChecker:
        """碰撞检测器占位符类（依赖未安装）"""

        def __init__(self):
            raise ImportError(
                f"碰撞检测功能需要额外的依赖项。"
                f"请运行: pip install -e .[collision]\n"
                f"缺失的依赖: {_missing_deps}"
            )

    class CollisionCheckError(Exception):
        """碰撞检测错误占位符类"""
        pass


__all__ = ['CollisionChecker', 'CollisionCheckError']
