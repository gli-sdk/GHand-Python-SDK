# examples/get_joint_speed.py

import sys
import os
import time
import math

# --- 手动添加 src 目录到 Python 搜索路径 ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)
# ---------------------------------------------

try:
    from xiaoyao import hand, common
    from xiaoyao.common import JOINT_NAMES # 假设关节名称定义在 common 模块中
except ImportError as e:
    print(f"错误：无法导入 'xiaoyao' 包: {e}")
    print("请确认您的项目结构正确，'src' 目录与此脚本的父目录同级。")
    sys.exit(1)

def rad_to_deg(rad):
    """将弧度转换为度。"""
    return rad * 180.0 / math.pi

def auto_select_adapter():
    """自动选择网络适配器。"""
    adapters = hand.find_adapters()
    if not adapters:
        raise RuntimeError("未找到任何网络适配器。请检查驱动和权限。")

    keywords = ['Ethernet', 'Realtek', 'GbE', 'PCIe']
    ethernet_adapters = []
    for adapter in adapters:
        desc = adapter.desc.decode('utf-8', errors='ignore').lower()
        if any(k.lower() in desc for k in keywords) and not any(f in desc for f in ['virtual', 'bluetooth', 'wi-fi']):
            ethernet_adapters.append(adapter)

    if len(ethernet_adapters) == 1:
        selected = ethernet_adapters[0]
        print(f"--- 自动选择网络适配器 ---\n  -> {selected.desc.decode('utf-8', 'ignore')}\n")
        return selected
    elif len(ethernet_adapters) > 1:
        print("找到多个可能的有线网络适配器，请手动选择:")
        for i, adapter in enumerate(ethernet_adapters):
            print(f"  [{i}]: {adapter.desc.decode('utf-8', 'ignore')}")
        choice = int(input(f"请输入编号 [0-{len(ethernet_adapters)-1}]: "))
        return ethernet_adapters[choice]
    else:
        raise RuntimeError("未能自动识别出有线网络适配器。")


def main():
    """
    主执行函数，实时获取并显示关节速度。
    """
    try:
        # --- 第1步: 自动选择适配器并连接 ---
        selected_adapter = auto_select_adapter()
        
        print("--- 连接到配置模式 (PRE-OP) ---")
        if not hand.connect_for_setup(selected_adapter.name):
            print("连接失败。")
            return

        # --- 第2步: 启动高速运行模式 (OP) ---
        print("\n--- 启动高速运行模式 (OP) ---")
        if not hand.start_pdo_communication():
            print("启动运行模式失败。")
            return

        print("\n--- 开始实时获取关节速度 (按 Ctrl+C 退出) ---")
        print("每秒更新一次。将显示所有关节的速度 (单位: °/s)。")
        
        # --- 第3步: 循环获取和显示数据 ---
        while True:
            # 获取包含所有实时数据的字典
            realtime_data = hand.get_realtime_data()

                    # +++ 临时添加的调试代码 +++
            print(f"【调试】get_realtime_data() 返回: {realtime_data}")
            # ++++++++++++++++++++++++++++

            if realtime_data:
                # 从字典中提取速度列表。协议单位是 rad/s。
                # 假设 'get_realtime_data' 返回的字典中，速度列表的键是 'joint_speeds'
                # 并且它是一个包含18个浮点数的列表
                speeds_rad = realtime_data.get('joint_speeds') # 假设键名为 'joint_speeds'

                if speeds_rad and len(speeds_rad) == len(JOINT_NAMES):
                    # 清空屏幕以便于刷新显示 (可选)
                    # os.system('cls' if os.name == 'nt' else 'clear') 
                    
                    print(f"\n--- 更新时间: {time.strftime('%Y-%m-%d %H:%M:%S')} ---")
                    
                    # 格式化输出
                    for i, speed_rad in enumerate(speeds_rad):
                        joint_name = JOINT_NAMES[i]
                        speed_deg = rad_to_deg(speed_rad)
                        # 使用 f-string 进行对齐和格式化
                        print(f"  关节 {joint_name:<8s} : {speed_deg:8.2f} °/s")
                else:
                    print("错误：无法从实时数据中获取有效的速度列表。")

            time.sleep(1) # 每秒更新一次

    except KeyboardInterrupt:
        print("\n\n程序被用户中断。")
    except Exception as e:
        print(f"\n[严重错误] {e}")
    finally:
        print("\n--- 任务结束，断开连接 ---")
        hand.close_device()

if __name__ == "__main__":
    main()