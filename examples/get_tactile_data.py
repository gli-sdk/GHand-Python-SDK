# get_tactile_data.py
import sys
import numpy as np # 用于更好地显示数组
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

# 导入 xiaoyao 包内的 tactile 模块
try:
    from xiaoyao import tactile
except ImportError:
    print("错误：无法导入 'xiaoyao' 包。")
    print("请确保您在项目的父目录（例如 'src/'）下，并使用 'python -m examples.get_tactile_data' 命令来运行此示例。")
    sys.exit(1)

print("--- 示例: 获取指尖触觉传感器数据 ---")

try:
    # 假设查询传感器ID为 0 的触觉数据
    sensor_id_to_query = 0
    print(f"\n正在调用 tactile.get_data(sensor_id={sensor_id_to_query})...")
    # 直接调用 tactile 模块中的顶层函数 get_data
    tactile_data = tactile.get_data(sensor_id=sensor_id_to_query)
    
    # 检查返回的是否是一个非空的列表 (表示二维数组)
    if tactile_data:
        print(f"\n指尖传感器 {sensor_id_to_query} 的触觉数据 (3x3矩阵):")
        # 使用numpy更好地格式化输出二维数组
        print(np.array(tactile_data))
    else:
        print(f"\n获取指尖传感器 {sensor_id_to_query} 的触觉数据失败或无数据。")

except Exception as e:
    print(f"获取触觉数据时发生错误: {e}")
finally:
    print("\n示例运行完毕!")