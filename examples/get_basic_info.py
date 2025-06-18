# get_basic_info.py
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
    print("请确保您在项目的父目录（例如 'src/'）下，并使用 'python -m examples.get_basic_info' 命令来运行此示例。")
    sys.exit(1)

print("--- 示例 1: 获取手部所有基本信息 ---")

# 在这种纯函数设计中，我们假设SDK初始化时已经处理了底层连接。
# 因此，不需要显式调用 client.connect()。

try:
    print("\n正在调用 hand.get_all_basic_info()...")
    # 直接调用 hand 模块中的顶层函数 get_all_basic_info
    hand_info = hand.get_all_basic_info()
    
    if hand_info:
        print("\n手部基本信息:")
        # 使用更结构化的方式打印信息，并解析枚举值
        print(f"  设备ID: {hand_info.get('device_id', 'N/A')}")
        print(f"  软件版本: {hand_info.get('software_version', 'N/A')}")
        
        hand_type_code = hand_info.get('hand_type_code')
        hand_type_desc = "左手" if hand_type_code == 0 else "右手" if hand_type_code == 1 else "未知"
        print(f"  手部类型: {hand_type_desc} (Code: {hand_type_code})")
        
        print(f"  当前温度: {hand_info.get('current_temperature', 'N/A')} 摄氏度")
        
        status_code = hand_info.get('operation_status_code')
        if status_code is not None:
            try:
                status_desc = common.RobotStatus(status_code).name
            except ValueError:
                status_desc = "未知的状态码"
        else:
            status_desc = "N/A"
        print(f"  运行状态: {status_desc} (Code: {status_code})")
        
    else:
        print("获取手部基本信息失败。")
except Exception as e:
    print(f"获取信息时发生错误: {e}")
finally:
    # 在纯函数设计中，关闭设备的逻辑可能也由一个专门的函数处理，
    # 或者由SDK在程序退出时自动管理。这里只打印一条消息。
    print("\n示例 1 运行完毕!")