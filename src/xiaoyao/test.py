# test.py

import sys
print("--- Test Script Starting ---")

try:
    # 我们只尝试导入hand模块，这是最关键的一步
    # 这会首先执行 xiaoyao/__init__.py
    from xiaoyao import hand
    print(">>> 成功导入 xiaoyao.hand 模块!")

    # 如果导入成功，我们再尝试调用一个函数
    print("\n>>> 正在调用 hand.get_all_basic_info()...")
    basic_info = hand.get_all_basic_info()
    
    print("\n--- 函数调用结果 ---")
    if basic_info:
        print("成功获取所有基本信息:")
        for key, value in basic_info.items():
            print(f"  {key}: {value}")
    else:
        print("获取基本信息失败。返回了一个空字典。")

except ImportError as e:
    print(f"\n!!!!!! IMPORT ERROR !!!!!!!")
    print(f"错误详情: {e}")
    print("请确认您的运行目录和命令是否正确，以及 __init__.py 是否被正确简化。")
except Exception as e:
    print(f"\n!!!!!! OTHER ERROR !!!!!!!")
    print(f"错误详情: {e}")

print("\n--- Test Script Finished ---")