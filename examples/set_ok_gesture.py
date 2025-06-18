# set_ok_gesture.py
import sys
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
# 导入 xiaoyao 包内的 hand 和 common 模块
try:
    from xiaoyao import hand, common
except ImportError:
    print("错误：无法导入 'xiaoyao' 包。")
    print("请确保您在项目的父目录（例如 'src/'）下，并使用 'python -m examples.set_ok_gesture' 命令来运行此示例。")
    sys.exit(1)

print("--- 示例: 设置手部预设手势 (比OK) ---")

try:
    print("\n正在调用 hand.do_preset_gesture(...) 来设置手势为 'OK'...")
    # 直接调用 hand 模块中的顶层函数 do_preset_gesture
    # 使用 common 模块中的 GestureType 枚举来指定手势
    result = hand.do_preset_gesture(common.GestureType.OK_SIGN)
    
    # 使用 common 模块中的 RobotError 枚举来检查返回码
    if result == common.RobotError.NO_ERROR:
        print("\n成功设置手势为 'OK'。")
    elif result == common.RobotError.INVALID_PARAMETER:
        print(f"\n设置手势失败: 参数无效。错误码: {result.value} ({result.name})")
    elif result == common.RobotError.ACTION_FAILED:
        print(f"\n设置手势失败: 动作执行失败或被终止。错误码: {result.value} ({result.name})")
    else:
        # 捕获其他可能的错误
        error_name = result.name if isinstance(result, common.RobotError) else "未知错误"
        error_value = result.value if isinstance(result, common.RobotError) else result
        print(f"\n设置手势失败，错误码: {error_value} ({error_name})")

except Exception as e:
    print(f"设置手势时发生错误: {e}")
finally:
    print("\n示例运行完毕!")