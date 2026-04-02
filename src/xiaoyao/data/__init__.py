"""
Xiaoyao SDK 数据模块

包含碰撞检测所需的静态数据文件。
"""

try:
    # Python 3.9+
    import importlib.resources as resources
except ImportError:
    # Python 3.8
    import importlib_resources as resources


def get_collision_data_path() -> str:
    """
    获取碰撞检测数据文件的路径

    Returns:
        str: 碰撞检测数据目录的绝对路径

    Example:
        >>> from xiaoyao.data import get_collision_data_path
        >>> data_path = get_collision_data_path()
        >>> print(f"Collision data at: {data_path}")
    """
    try:
        # 使用 importlib.resources 获取包数据路径
        ref = resources.files('xiaoyao.data') / 'collision'
        # 转换为字符串路径（兼容性）
        return str(ref)
    except Exception as e:
        # 回退：尝试使用 __file__ 属性
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(current_dir, 'collision')


__all__ = ['get_collision_data_path']
