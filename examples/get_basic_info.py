# examples/get_basic_info.py (最终无误的完整版)

import sys
import os
import time

# --- 手动添加 src 目录到 Python 搜索路径 ---
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
    print("请确认您的项目结构正确，'src' 目录与此脚本的父目录同级。")
    sys.exit(1)

def main():
    selected_adapter = None
    
    # --- 第1步: 自动查找并选择网络适配器 ---
    try:
        adapters = hand.find_adapters()
        if not adapters:
            print("错误: 未找到任何网络适配器。请确认：")
            print("1. Npcap 驱动已正确安装 (并勾选了'WinPcap API兼容模式')。")
            print("2. 您正以管理员/root权限运行此脚本。")
            return

        # 定义用于识别物理有线网卡的关键字列表
        # 您可以根据需要调整这些关键字
        # 例如，如果您的网卡是Intel的，可以加入 'Intel'
        keywords = ['Ethernet', 'Realtek', 'GbE', 'PCIe']
        
        ethernet_adapters = []
        for adapter in adapters:
            # 将描述信息解码为字符串以便于搜索
            desc = adapter.desc.decode('utf-8', errors='ignore').lower()
            if any(keyword.lower() in desc for keyword in keywords) and 'virtual' not in desc and 'bluetooth' not in desc and 'wi-fi' not in desc:
                ethernet_adapters.append(adapter)

        if len(ethernet_adapters) == 1:
            # 如果只找到一个匹配的网卡，就自动选择它
            selected_adapter = ethernet_adapters[0]
            print(f"--- 自动选择网络适配器 ---\n  -> {selected_adapter.desc.decode('utf-8', errors='ignore')}\n")
        elif len(ethernet_adapters) > 1:
            # 如果找到多个可能的网卡，则退回手动选择模式
            print("找到多个可能的有线网络适配器，请手动选择:")
            for i, adapter in enumerate(ethernet_adapters):
                print(f"  [{i}]: {adapter.desc.decode('utf-8', errors='ignore')}")
            
            choice_str = input(f"请输入要使用的适配器编号 [0-{len(ethernet_adapters)-1}]: ")
            choice = int(choice_str)
            selected_adapter = ethernet_adapters[choice]
        else:
            # 如果一个都没找到，则提示用户并列出所有适配器
            print("错误: 未能自动识别出有线网络适配器。请从以下列表中手动选择：")
            for i, adapter in enumerate(adapters):
                print(f"  [{i}]: {adapter.desc.decode('utf-8', errors='ignore')}")
            
            choice_str = input(f"请输入要使用的适配器编号 [0-{len(adapters)-1}]: ")
            choice = int(choice_str)
            selected_adapter = adapters[choice]

    except (ValueError, IndexError):
        print("输入无效，请输入列表中的数字。程序退出。")
        return
    except Exception as e:
        print(f"查找适配器时出错: {e}")
        return

    # --- 第2步: 连接到灵巧手 ---
    try:
        # --- 阶段一: PRE-OP 配置 ---
        print("\n--- 阶段一: 连接到配置模式 (PRE-OP) ---")
        if not hand.open_ethercat(selected_adapter.name):
            print("连接到配置模式失败。")
            return
            
        print("\n正在获取静态信息 (SDO)...")
        static_info = hand.get_all_basic_info()
        print(f"  设备ID: {static_info.get('device_id', 'N/A')}")
        print(f"  软件版本: {static_info.get('software_version', 'N/A')}")
        print(f"  手部类型: {static_info.get('hand_type', 'N/A')}")

        # --- 阶段二: OP 运行 ---
        print("\n--- 阶段二: 启动高速运行模式 (OP) ---")
        if not hand.start_pdo_communication():
            print("启动运行模式失败。")
            return

        print("\n正在获取实时信息 (PDO)...")
        for i in range(10): # 循环获取10次
            realtime_data = hand.get_realtime_data()
            if realtime_data:
                State_code = realtime_data.get('operation_state_code')
                temp = realtime_data.get('current_temperature')
                print(f"  实时状态码: {State_code}, 温度: {temp}°C")
            time.sleep(0.2)
            
    except Exception as e:
        print(f"\n[严重错误] {e}")
    finally:
        print("\n--- 任务结束，断开连接 ---")
        hand.close_device()

if __name__ == "__main__":
    main()