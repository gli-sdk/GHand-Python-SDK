import time
import logging
from xiaoyao.dexhand import DexHand

logger = logging.getLogger("xiaoyao")

def data_callback(tpdo):
    """
    数据回调函数
    
    Args:
        tpdo: 解析后的TPDO数据对象
    """
    logger.info("Received TPDO data:")
    logger.info(f"  Hand state: {tpdo.hand}")
    logger.info(f"  Thumb DIP angle: {tpdo.th_dip.angle}")
    logger.info(f"  FF MCP angle: {tpdo.ff_mcp.angle}")
    # 可以在这里处理接收到的数据

def main():
    # 创建灵巧手实例
    hand = DexHand()
    
    # 打开连接
    if not hand.open():
        logger.error("Failed to open hand connection")
        return
    
    # 订阅数据更新
    sub_id = hand.subscribe(data_callback)
    logger.info(f"Subscribed with ID: {sub_id}")
    
    try:
        # 让订阅运行一段时间
        time.sleep(10)
    finally:
        # 取消订阅并关闭连接
        hand.unsubscribe(sub_id)
        hand.close()

if __name__ == "__main__":
    main()