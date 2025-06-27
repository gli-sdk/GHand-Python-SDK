# examples/get_basic_info.py

import sys
import os

# --- 手动添加 src 目录到 Python 搜索路径 (保持不变) ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)
# ---------------------------------------------

try:
    from xiaoyao import hand, common
except ImportError as e:
    print(f"错误：无法导入 'xiaoyao' 包: {e}")
    print("请确认您的项目结构正确，并且您在项目根目录下运行此脚本。")
    sys.exit(1)

def main():
    """主执行函数，展示SDK的连接->操作->断开完整流程"""
    selected_adapter = None
    
    # --- 第1步: 查找并选择网络适配器 ---
    try:
        adapters = hand.find_adapters()
        if not adapters:
            print("错误: 未找到任何网络适配器。请确认：")
            print("1. Npcap 已正确安装 (勾选了'WinPcap兼容模式')。")
            print("2. 您正以管理员/root权限运行此脚本。")
            return

        print("找到以下网络适配器:")
        for i, adapter in enumerate(adapters):
            print(f"  [{i}]: {adapter.desc}")
        
        choice_str = input(f"请输入要使用的适配器编号 [0-{len(adapters)-1}]: ")
        choice = int(choice_str)
        if 0 <= choice < len(adapters):
            selected_adapter = adapters[choice]
        else:
            print("无效的选择。")
            return
            
    except (ValueError, IndexError):
        print("输入无效，请输入列表中的数字。")
        return
    except Exception as e:
        print(f"查找适配器时出错: {e}")
        return

    # --- 第2步: 连接到灵巧手 ---
    # 我们将连接和操作放在 try...finally 结构中，确保设备总是被关闭
    try:
        print(f"\n正在使用 '{selected_adapter.desc}' 进行连接...")
        # 此处不要求进入OP状态，因为获取基本信息只需要PRE-OP状态
        if not hand.connect_to_hand(selected_adapter.name, enable_op_state=False):
            print("连接失败，请检查物理连接和设备状态。")
            return
        
        print("\n--- 示例: 获取手部所有基本信息 ---")
        
        # --- 第3步: 调用API获取信息 ---
        hand_info = hand.get_all_basic_info()
        
        if hand_info:
            print("\n成功获取手部基本信息:")
            print(f"  设备ID: {hand_info.get('device_id', 'N/A')}")
            print(f"  软件版本: {hand_info.get('software_version', 'N/A')}")
            
            hand_type_code = hand_info.get('hand_type_code')
            hand_type_desc = "左手" if hand_type_code == 0 else "右手" if hand_type_code == 1 else "未知"
            print(f"  手部类型: {hand_type_desc} (Code: {hand_type_code})")
            
            print(f"  当前温度: {hand_info.get('current_temperature', 'N/A')} 摄氏度")
            
            status_code = hand_info.get('operation_status_code')
            try:
                status_desc = common.RobotStatus(status_code).name if status_code is not None else "N/A"
            except ValueError:
                status_desc = "未知的状态码"
            print(f"  运行状态: {status_desc} (Code: {status_code})")
        else:
            print("未能从设备获取任何有效信息。")

    except ConnectionError as e:
        print(f"\n连接或通信错误: {e}")
    except Exception as e:
        print(f"\n操作过程中发生未知错误: {e}")
    finally:
        # --- 第4步: 断开连接 ---
        print("\n示例运行完毕，正在关闭设备连接...")
        hand.close_device()

if __name__ == "__main__":
    main()