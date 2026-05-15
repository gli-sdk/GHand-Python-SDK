import time
import math
import logging
from ghand.dexhand import DexHand
from ghand import configure_logging
from ghand.types import State, ErrorCode

# Configure SDK logging (shows connection state, warnings, errors)
configure_logging(level=logging.INFO)


def data_callback(tpdo):
    """
    数据回调函数
    
    Args:
        tpdo: 解析后的TPDO数据对象
    """
    print("Received TPDO data:")
    print(f"  Hand state: {tpdo.hand}")
    print(f"  Thumb DIP: angle={math.degrees(tpdo.th_dip.angle):.1f}°, state={State(tpdo.th_dip.state).name}, error={ErrorCode(tpdo.th_dip.error).name}")
    print(f"  FF MCP: angle={math.degrees(tpdo.ff_mcp.angle):.1f}°, state={State(tpdo.ff_mcp.state).name}, error={ErrorCode(tpdo.ff_mcp.error).name}")
    # 可以在这里处理接收到的数据

def main():
    # 创建灵巧手实例
    hand = DexHand()
    
    # 打开连接
    if not hand.open():
        print("Failed to open hand connection")
        return
    
    # 订阅数据更新
    sub_id = hand.subscribe(data_callback)
    print(f"Subscribed with ID: {sub_id}")
    
    try:
        # 让订阅运行一段时间
        time.sleep(10)
    except KeyboardInterrupt:
        print("Stopping subscription")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # 取消订阅并关闭连接
        hand.unsubscribe(sub_id)
        hand.close()

if __name__ == "__main__":
    main()
