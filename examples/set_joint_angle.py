# set_joint_angle.py
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

# 导入 xiaoyao 包内的 joint 和 common 模块
try:
    from xiaoyao import joint, common
except ImportError:
    print("错误：无法导入 'xiaoyao' 包。")
    print("请确保您在项目的父目录（例如 'src/'）下，并使用 'python -m examples.set_joint_angle' 命令来运行此示例。")
    sys.exit(1)

print("--- 示例: 设置单个关节角度 ---")

try:
    # 定义关节运动的参数
    joint_id_to_set = 0
    target_angle_degrees = 90.0 # 目标角度，单位度
    target_angle_radians = math.radians(target_angle_degrees) # 转换为弧度
    set_speed = 0.5 # 设定运动速度，单位弧度/秒

    print(f"\n正在调用 joint.set_angle(...) 将关节ID {joint_id_to_set} 的角度设置为 {target_angle_degrees} 度...")

    # 构建函数所需的目标列表
    joint_targets = [
        {'joint_id': joint_id_to_set, 'target_angle': target_angle_radians, 'speed': set_speed}
    ]
    
    # 直接调用 joint 模块中的顶层函数 set_angle
    result_code = joint.set_angle(joint_targets)
    
    # 使用 common 模块中的 HandError 枚举来检查返回码
    if result_code == common.HandError.NO_ERROR.value:
        print("\n关节角度设置指令发送成功。")
        # 在实际SDK中，这里可以等待运动完成或使用订阅来确认状态
    elif result_code == common.HandError.INVALID_PARAMETER.value:
        print(f"\n关节角度设置失败: 参数无效。错误码: {result_code}")
    else:
        print(f"\n关节角度设置失败，未知错误码: {result_code}")

except Exception as e:
    print(f"设置关节角度时发生错误: {e}")
finally:
    print("\n示例运行完毕!")