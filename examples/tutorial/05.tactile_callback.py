import time
import sys
import threading
from ghand.ghand import GHand, CommType
from ghand import TactileSensorId


class TactileDisplay:
    def __init__(self):
        self.hand = GHand()
        self.connected = False
        self.tactile_opened = False
        self.running = False
        self.display_thread = None
        self.start_time = None  # 添加开始时间记录

    def connect(self):
        self.connected = self.hand.open(CommType.ETHERCAT, "auto")
        if not self.connected:
            print("连接失败")
            return False
        print("连接成功！")
        return True

    def tactile_open(self):
        if not self.connected:
            print("请先连接设备")
            return False
            
        tactile_connected = self.hand.tactile_open()
        if tactile_connected:
            print("触觉传感器已打开")
            self.tactile_opened = True
            return True
        else:
            print("触觉传感器打开失败")
            return False

    def tactile_close(self):
        if self.tactile_opened:
            self.hand.tactile_close()
            print("触觉传感器已关闭")
            self.tactile_opened = False

    def start_display(self):
        if not self.tactile_opened:
            print("请先打开触觉传感器")
            return

        self.running = True
        self.start_time = time.time()  # 记录开始时间
        self.display_thread = threading.Thread(target=self._display_loop)
        self.display_thread.start()

    def _display_loop(self):
        try:
            while self.running:
                # 使用新的get_tactile_data函数来获取触觉数据
                tactile_data = self.hand.get_tactile_data()
                
                if tactile_data:
                    # 直接通过枚举访问各手指的合力数据

                    thumb_data = tactile_data[TactileSensorId.THUMB]
                    ff_data = tactile_data[TactileSensorId.FOREFINGER]
                    mf_data = tactile_data[TactileSensorId.MIDDLE_FINGER]
                    rf_data = tactile_data[TactileSensorId.RING_FINGER]
                    lf_data = tactile_data[TactileSensorId.LITTLE_FINGER]
                    
                    # 获取各手指在XYZ轴的合力
                    thumb_x, thumb_y, thumb_z = thumb_data.resultant_force
                    ff_x, ff_y, ff_z = ff_data.resultant_force
                    mf_x, mf_y, mf_z = mf_data.resultant_force
                    rf_x, rf_y, rf_z = rf_data.resultant_force
                    lf_x, lf_y, lf_z = lf_data.resultant_force
                    
                    # 计算运行时长
                    elapsed_time = time.time() - self.start_time if self.start_time else 0
                    hours = int(elapsed_time // 3600)
                    minutes = int((elapsed_time % 3600) // 60)
                    seconds = int(elapsed_time % 60)
                    runtime_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                    
                    # 确定状态
                    status = "触觉传感器开启" if self.tactile_opened else "触觉传感器关闭"
                    
                    # 使用ANSI转义序列覆盖之前的数据行
                    sys.stdout.write("\033[10A")  # 光标向上移动8+2行（表头 + 5个手指 + 分隔线 + 状态行 + 2行确保完全覆盖）
                    sys.stdout.write("\033[J")   # 清除光标位置到屏幕底部的所有内容
                    
                    # 更新数据显示
                    print("手指     |     X轴      |     Y轴      |     Z轴      |")
                    sys.stdout.write("\033[K")   # 清除当前行
                    print(f"大拇指   | {thumb_x:8.2f}N   | {thumb_y:8.2f}N   | {thumb_z:8.2f}N")
                    sys.stdout.write("\033[K")   # 清除当前行
                    print(f"食指     | {ff_x:8.2f}N   | {ff_y:8.2f}N   | {ff_z:8.2f}N")
                    sys.stdout.write("\033[K")   # 清除当前行
                    print(f"中指     | {mf_x:8.2f}N   | {mf_y:8.2f}N   | {mf_z:8.2f}N")
                    sys.stdout.write("\033[K")   # 清除当前行
                    print(f"无名指   | {rf_x:8.2f}N   | {rf_y:8.2f}N   | {rf_z:8.2f}N")
                    sys.stdout.write("\033[K")   # 清除当前行
                    print(f"小指     | {lf_x:8.2f}N   | {lf_y:8.2f}N   | {lf_z:8.2f}N")
                    sys.stdout.write("\033[K")   # 清除当前行
                    print("-"*70)
                    sys.stdout.write("\033[K")   # 清除当前行
                    print(f"实时更新中... 按 Ctrl+C 停止 | 运行时长: {runtime_str} | 状态: {status}")
                    sys.stdout.write("\033[K")   # 清除当前行
                    
                    sys.stdout.flush()
                else:
                    # 计算运行时长
                    elapsed_time = time.time() - self.start_time if self.start_time else 0
                    hours = int(elapsed_time // 3600)
                    minutes = int((elapsed_time % 3600) // 60)
                    seconds = int(elapsed_time % 60)
                    runtime_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                    
                    # 确定状态
                    status = "触觉传感器开启" if self.tactile_opened else "触觉传感器关闭"
                    
                    sys.stdout.write("\033[10A")  # 光标向上移动8+2行
                    sys.stdout.write("\033[J")   # 清除光标位置到屏幕底部的所有内容
                    print(f"触觉数据获取失败或为空")
                    sys.stdout.write("\033[K")   # 清除当前行
                    print("-"*70)
                    sys.stdout.write("\033[K")   # 清除当前行
                    print(f"实时更新中... 按 Ctrl+C 停止 | 运行时长: {runtime_str} | 状态: {status}")
                    sys.stdout.write("\033[K")   # 清除当前行
                    sys.stdout.flush()
                
                time.sleep(0.015)  # 每15毫秒刷新一次

        except Exception as e:
            print(f"\n显示线程发生错误: {e}")

    def stop_display(self):
        self.running = False
        if self.display_thread:
            self.display_thread.join()

    def close(self):
        self.stop_display()
        self.tactile_close()
        if self.connected:
            self.hand.close()
        print("\n程序结束")


def simple_tactile_display():
    display = TactileDisplay()
    
    if not display.connect():
        return

    print("\n命令说明:")
    print("  'o' 或 'open' - 打开触觉传感器")
    print("  'c' 或 'close' - 关闭触觉传感器")
    print("  's' 或 'start' - 开始显示触觉数据")
    print("  't' 或 'stop' - 停止显示触觉数据")
    print("  'q' 或 'quit' - 退出程序")
    print("-" * 50)

    try:
        while True:
            command = input("\n请输入命令: ").strip().lower()
            
            if command in ['o', 'open']:
                if not display.tactile_opened:
                    display.tactile_open()
                else:
                    print("触觉传感器已经开启")
            
            elif command in ['c', 'close']:
                if display.tactile_opened:
                    display.tactile_close()
                    print("触觉传感器已关闭")
                else:
                    print("触觉传感器已经关闭")
            
            elif command in ['s', 'start']:
                if display.tactile_opened:
                    if not display.running:
                        display.start_display()
                        print("触觉数据显示已启动")
                        print("注意：数据正在实时显示，按 Ctrl+C 返回命令模式")
                    else:
                        print("触觉数据已经在显示中")
                else:
                    print("请先打开触觉传感器")
            
            elif command in ['t', 'stop']:
                if display.running:
                    display.stop_display()
                    print("触觉数据显示已停止")
                else:
                    print("触觉数据未在显示")
            
            elif command in ['q', 'quit']:
                print("正在退出程序...")
                break
            
            else:
                print("无效命令，请重新输入")
                
    except KeyboardInterrupt:
        print("\n\n用户中断，正在关闭...")
    finally:
        display.close()


if __name__ == "__main__":
    simple_tactile_display()