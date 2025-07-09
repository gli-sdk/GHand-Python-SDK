# examples/set_light_effect.py

import sys
import os
import time

# 添加src目录到搜索路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))
from xiaoyao import hand

def main():
    print("***** 枭尧灵巧手 SDK - 灯光控制功能测试 *****")
    
    selected_adapter = None

    # --- 步骤 1: 自动查找并选择网络适配器 ---
    try:
        adapters = hand.find_adapters()
        if not adapters:
            print("错误: 未找到任何网络适配器。请确认：")
            print("1. Npcap 驱动已正确安装 (并勾选了'WinPcap API兼容模式')。")
            print("2. 您正以管理员/root权限运行此脚本。")
            return

        keywords = ['Ethernet', 'Realtek', 'GbE', 'PCIe', 'ASIX'] # 添加了 ASIX
        
        ethernet_adapters = []
        for adapter in adapters:
            desc = adapter.desc.decode('utf-8', errors='ignore').lower()
            if any(k.lower() in desc for k in keywords) and not any(f in desc for f in ['virtual', 'bluetooth', 'wi-fi']):
                ethernet_adapters.append(adapter)

        if len(ethernet_adapters) == 1:
            selected_adapter = ethernet_adapters[0]
            print(f"--- 自动选择网络适配器 ---\n  -> {selected_adapter.desc.decode('utf-8', 'ignore')}\n")
        elif len(ethernet_adapters) > 1:
            print("找到多个可能的有线网络适配器，请手动选择:")
            for i, adapter in enumerate(ethernet_adapters):
                print(f"  [{i}]: {adapter.desc.decode('utf-8', 'ignore')}")
            choice = int(input(f"请输入编号 [0-{len(ethernet_adapters)-1}]: "))
            selected_adapter = ethernet_adapters[choice]
        else:
            print("错误: 未能自动识别出有线网络适配器。请从以下列表中手动选择：")
            for i, adapter in enumerate(adapters):
                print(f"  [{i}]: {adapter.desc.decode('utf-8', 'ignore')}")
            choice = int(input(f"请输入编号 [0-{len(adapters)-1}]: "))
            selected_adapter = adapters[choice]

    except (ValueError, IndexError):
        print("输入无效，程序退出。")
        return
    except Exception as e:
        print(f"查找适配器时出错: {e}")
        return

    # --- 步骤 2: 连接到设备 ---
    try:
        # 灯光设置是配置操作，只需要PRE-OP状态
        print("\n--- 步骤 2: 连接到设备 (PRE-OP 模式)... ---")
        if not hand.open_ethercat(selected_adapter.name): # 使用最新的 open_ethercat 函数
            print("连接失败，测试终止。")
            return
        
        print("连接成功！")
        time.sleep(0.5)

        # --- 步骤 3: 测试不同的灯光效果 ---
        print("\n--- 步骤 3: 设置灯光为【蓝色常亮】---")
        if hand.set_light(mode=0, color=(0, 0, 255)):
            print("  -> 设置蓝色常亮指令发送成功。")
        else:
            print("  -> 设置蓝色常亮指令发送失败。")
        time.sleep(3) # 等待3秒观察效果

        print("\n--- 步骤 4: 设置灯光为【绿色闪烁】---")
        # 设置为闪烁模式(1)，颜色为绿色，频率为500ms（每秒闪2次）
        if hand.set_light(mode=1, color=(0, 255, 0), frequency_ms=500):
            print("  -> 设置绿色闪烁指令发送成功。")
        else:
            print("  -> 设置绿色闪烁指令发送失败。")
        time.sleep(5) # 等待5秒观察效果

        print("\n--- 步骤 5: 设置灯光为【红色呼吸】---")
        # 假设呼吸模式为2，周期为2000ms（2秒一个呼吸周期）
        if hand.set_light(mode=2, color=(255, 0, 0), frequency_ms=2000):
            print("  -> 设置红色呼吸指令发送成功。")
        else:
            print("  -> 设置红色呼吸指令发送失败。")
        time.sleep(5) # 等待5秒观察效果

    except Exception as e:
        print(f"\n测试过程中发生未知错误: {e}")
    finally:
        print("\n测试脚本运行完毕，正在断开连接...")
        hand.close_device()

if __name__ == "__main__":
    main()