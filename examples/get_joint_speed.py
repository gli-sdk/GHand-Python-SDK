# get_joint_speed.py
import sys
import math
import os

# --- 手动添加 src 目录到 Python 搜索路径 ---
# 获取当前脚本文件所在的目录 (即 .../examples/)
current_dir = os.path.dirname(os.path.abspath(__file__))
# 获取项目根目录 (即 .../XIAOYAO-SDK-1/)
project_root = os.path.dirname(current_dir)
# 构建 src 目录的路径
src_path = os.path.join(project_root, 'src')

# 如果 src 目录不在 sys.path 中，则添加它
if src_path not in sys.path:
    sys.path.insert(0, src_path)
# ---------------------------------------------


# 导入 xiaoyao 包内的 joint 模块
try:
    from xiaoyao import joint
except ImportError:
    print("错误：无法导入 'xiaoyao' 包。")
    print("请确保您在项目的父目录（例如 'src/'）下，并使用 'python -m examples.get_joint_speed' 命令来运行此示例。")
    sys.exit(1)

print("--- 示例: 获取关节当前运行速度 ---")

try:
    joint_id_to_query = 0 # 假设查询关节ID 0 的速度
    print(f"\n正在调用 joint.get_speed(joint_id={joint_id_to_query})...")
    # 直接调用 joint 模块中的顶层函数 get_speed
    joint_speed = joint.get_speed(joint_id=joint_id_to_query)
    
    # 检查返回的是否是一个有效的浮点数
    if isinstance(joint_speed, float) and not math.isnan(joint_speed):
        print(f"\n关节ID {joint_id_to_query} 的当前运行速度: {joint_speed:.2f} 弧度/秒")
    else:
        print(f"\n获取关节 {joint_id_to_query} 的速度失败或返回无效值。")

except Exception as e:
    print(f"获取关节速度时发生错误: {e}")
finally:
    print("\n示例运行完毕!")