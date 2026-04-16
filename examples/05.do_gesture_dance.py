import time
import math
import logging
from xiaoyao import (
    DexHand,
    CommType,
    Joint,
    JointId,
    configure_logging
)
from xiaoyao.gestures import (
    GestureType,
    execute_gesture
)

# 配置日志输出到控制台
configure_logging(level=logging.INFO)
logger = logging.getLogger("xiaoyao")

# 常量定义
ACTION_DELAY = 1
FLEX_CYCLE_COUNT = 4

# 拇指触碰其他手指的手势
thumb_touch_little_finger = {
    JointId.THUMB_PIP: math.radians(20),
    JointId.THUMB_MCP: math.radians(50),
    JointId.THUMB_SWING: math.radians(60),
    JointId.THUMB_ROTATION: math.radians(0),
    JointId.LF_PIP: math.radians(56),
    JointId.LF_MCP: math.radians(28),
    # 其他关节保持零位
    JointId.FF_PIP: math.radians(0),
    JointId.FF_MCP: math.radians(0),
    JointId.FF_SWING: math.radians(0),
    JointId.MF_PIP: math.radians(0),
    JointId.MF_MCP: math.radians(0),
    JointId.RF_PIP: math.radians(0),
    JointId.RF_MCP: math.radians(0),
}

thumb_touch_ring_finger = {
    JointId.THUMB_PIP: math.radians(19),
    JointId.THUMB_MCP: math.radians(38),
    JointId.THUMB_SWING: math.radians(45),
    JointId.THUMB_ROTATION: math.radians(0),
    JointId.RF_PIP: math.radians(67),
    JointId.RF_MCP: math.radians(39),
    JointId.LF_PIP: math.radians(0),
    JointId.LF_MCP: math.radians(0),
    # 其他关节保持零位
    JointId.FF_PIP: math.radians(0),
    JointId.FF_MCP: math.radians(0),
    JointId.FF_SWING: math.radians(0),
    JointId.MF_PIP: math.radians(0),
    JointId.MF_MCP: math.radians(0),
}

thumb_touch_middle_finger = {
    JointId.THUMB_PIP: math.radians(17),
    JointId.THUMB_MCP: math.radians(27),
    JointId.THUMB_SWING: math.radians(30),
    JointId.THUMB_ROTATION: math.radians(0),
    JointId.MF_PIP: math.radians(40),
    JointId.MF_MCP: math.radians(57),
    JointId.RF_PIP: math.radians(0),
    JointId.RF_MCP: math.radians(0),
    # 其他关节保持零位
    JointId.FF_PIP: math.radians(0),
    JointId.FF_MCP: math.radians(0),
    JointId.FF_SWING: math.radians(0),
    JointId.LF_PIP: math.radians(0),
    JointId.LF_MCP: math.radians(0),
}

thumb_touch_index_finger = {
    JointId.THUMB_PIP: math.radians(13),
    JointId.THUMB_MCP: math.radians(14),
    JointId.THUMB_SWING: math.radians(20),
    JointId.THUMB_ROTATION: math.radians(0),
    JointId.FF_PIP: math.radians(51),
    JointId.FF_MCP: math.radians(46),
    JointId.FF_SWING: math.radians(0),
    JointId.MF_PIP: math.radians(0),
    JointId.MF_MCP: math.radians(0),
    # 其他关节保持零位
    JointId.RF_PIP: math.radians(0),
    JointId.RF_MCP: math.radians(0),
    JointId.LF_PIP: math.radians(0),
    JointId.LF_MCP: math.radians(0),
}

# 单独张开手指的手势
open_index_finger = {
    JointId.THUMB_PIP: math.radians(30),
    JointId.THUMB_MCP: math.radians(20),
    JointId.THUMB_SWING: math.radians(20),
    JointId.THUMB_ROTATION: math.radians(0),
    # 张开食指
    JointId.FF_PIP: math.radians(0),
    JointId.FF_MCP: math.radians(0),
    JointId.FF_SWING: math.radians(0),
    # 其他关节保持零位
    JointId.MF_PIP: math.radians(75),
    JointId.MF_MCP: math.radians(70),
    JointId.RF_PIP: math.radians(75),
    JointId.RF_MCP: math.radians(70),
    JointId.LF_PIP: math.radians(70),
    JointId.LF_MCP: math.radians(70),
}

open_middle_finger = {
    JointId.THUMB_PIP: math.radians(30),
    JointId.THUMB_MCP: math.radians(20),
    JointId.THUMB_SWING: math.radians(20),
    JointId.THUMB_ROTATION: math.radians(0),
    # 张开食指
    JointId.FF_PIP: math.radians(0),
    JointId.FF_MCP: math.radians(0),
    JointId.FF_SWING: math.radians(0),
    JointId.MF_PIP: math.radians(0),
    JointId.MF_MCP: math.radians(0),
    # 其他关节保持零位
    JointId.RF_PIP: math.radians(75),
    JointId.RF_MCP: math.radians(70),
    JointId.LF_PIP: math.radians(70),
    JointId.LF_MCP: math.radians(70),
}

open_ring_finger = {
    JointId.THUMB_PIP: math.radians(30),
    JointId.THUMB_MCP: math.radians(20),
    JointId.THUMB_SWING: math.radians(20),
    JointId.THUMB_ROTATION: math.radians(0),
    # 张开无名指
    JointId.FF_PIP: math.radians(0),
    JointId.FF_MCP: math.radians(0),
    JointId.FF_SWING: math.radians(0),
    JointId.MF_PIP: math.radians(0),
    JointId.MF_MCP: math.radians(0),
    JointId.RF_PIP: math.radians(0),
    JointId.RF_MCP: math.radians(0),
    # 其他关节保持零位
    JointId.LF_PIP: math.radians(70),
    JointId.LF_MCP: math.radians(70),
}

open_little_finger = {
    JointId.THUMB_PIP: math.radians(30),
    JointId.THUMB_MCP: math.radians(20),
    JointId.THUMB_SWING: math.radians(20),
    JointId.THUMB_ROTATION: math.radians(0),
    # 张开小拇指
    JointId.FF_PIP: math.radians(0),
    JointId.FF_MCP: math.radians(0),
    JointId.FF_SWING: math.radians(0),
    JointId.MF_PIP: math.radians(0),
    JointId.MF_MCP: math.radians(0),
    JointId.RF_PIP: math.radians(0),
    JointId.RF_MCP: math.radians(0),
    JointId.LF_PIP: math.radians(0),
    JointId.LF_MCP: math.radians(0),
}

# 食指摆动手势
index_finger_swing_neg = {
    JointId.THUMB_PIP: math.radians(30),
    JointId.THUMB_MCP: math.radians(20),
    JointId.THUMB_SWING: math.radians(20),
    JointId.THUMB_ROTATION: math.radians(0),
    # 侧摆-15度
    JointId.FF_PIP: math.radians(0),
    JointId.FF_MCP: math.radians(0),
    JointId.FF_SWING: math.radians(-10),

    JointId.MF_PIP: math.radians(75),
    JointId.MF_MCP: math.radians(70),
    JointId.RF_PIP: math.radians(75),
    JointId.RF_MCP: math.radians(70),
    JointId.LF_PIP: math.radians(70),
    JointId.LF_MCP: math.radians(70),
}

index_finger_swing_pos = {
    JointId.THUMB_PIP: math.radians(30),
    JointId.THUMB_MCP: math.radians(20),
    JointId.THUMB_SWING: math.radians(20),
    JointId.THUMB_ROTATION: math.radians(0),
    # 侧摆15度
    JointId.FF_PIP: math.radians(0),
    JointId.FF_MCP: math.radians(0),
    JointId.FF_SWING: math.radians(10),
    JointId.MF_PIP: math.radians(75),
    JointId.MF_MCP: math.radians(70),
    JointId.RF_PIP: math.radians(75),
    JointId.RF_MCP: math.radians(70),
    JointId.LF_PIP: math.radians(74),
    JointId.LF_MCP: math.radians(70),
}

# 手指弯曲手势
flex_all_fingers = {
    JointId.THUMB_PIP: math.radians(0),
    JointId.THUMB_MCP: math.radians(0),
    JointId.THUMB_SWING: math.radians(20),
    JointId.THUMB_ROTATION: math.radians(0),

    JointId.FF_PIP: math.radians(75),
    JointId.FF_MCP: math.radians(70),
    JointId.FF_SWING: math.radians(0),
    JointId.MF_PIP: math.radians(75),
    JointId.MF_MCP: math.radians(70),
    JointId.RF_PIP: math.radians(75),
    JointId.RF_MCP: math.radians(70),

    JointId.LF_PIP: math.radians(74),
    JointId.LF_MCP: math.radians(70),
}

flex_ring_and_little_fingers = {
    JointId.THUMB_PIP: math.radians(0),
    JointId.THUMB_MCP: math.radians(0),
    JointId.THUMB_SWING: math.radians(20),
    JointId.THUMB_ROTATION: math.radians(0),
    JointId.FF_PIP: math.radians(0),
    JointId.FF_MCP: math.radians(0),
    JointId.FF_SWING: math.radians(0),
    JointId.MF_PIP: math.radians(0),
    JointId.MF_MCP: math.radians(0),

    JointId.RF_PIP: math.radians(75),
    JointId.RF_MCP: math.radians(70),
    JointId.LF_PIP: math.radians(74),
    JointId.LF_MCP: math.radians(70),
}

flex_middle_ring_little_fingers = {
    JointId.THUMB_PIP: math.radians(0),
    JointId.THUMB_MCP: math.radians(0),
    JointId.THUMB_SWING: math.radians(20),
    JointId.THUMB_ROTATION: math.radians(0),
    JointId.FF_PIP: math.radians(0),
    JointId.FF_MCP: math.radians(0),
    JointId.FF_SWING: math.radians(0),

    JointId.MF_PIP: math.radians(75),
    JointId.MF_MCP: math.radians(70),
    JointId.RF_PIP: math.radians(75),
    JointId.RF_MCP: math.radians(70),
    JointId.LF_PIP: math.radians(74),
    JointId.LF_MCP: math.radians(70),
}

flex_little_finger = {
    JointId.THUMB_PIP: math.radians(0),
    JointId.THUMB_MCP: math.radians(0),
    JointId.THUMB_SWING: math.radians(20),
    JointId.THUMB_ROTATION: math.radians(0),
    JointId.FF_PIP: math.radians(0),
    JointId.FF_MCP: math.radians(0),
    JointId.FF_SWING: math.radians(0),
    JointId.MF_PIP: math.radians(0),
    JointId.MF_MCP: math.radians(0),
    JointId.RF_PIP: math.radians(0),
    JointId.RF_MCP: math.radians(0),

    JointId.LF_PIP: math.radians(74),
    JointId.LF_MCP: math.radians(70),
}

flex_index_finger = {
    JointId.THUMB_PIP: math.radians(0),
    JointId.THUMB_MCP: math.radians(0),
    JointId.THUMB_SWING: math.radians(20),
    JointId.THUMB_ROTATION: math.radians(0),
    JointId.FF_PIP: math.radians(75),
    JointId.FF_MCP: math.radians(70),
    JointId.FF_SWING: math.radians(0),
    JointId.MF_PIP: math.radians(0),
    JointId.MF_MCP: math.radians(0),
    JointId.RF_PIP: math.radians(0),
    JointId.RF_MCP: math.radians(0),
    JointId.LF_PIP: math.radians(0),
    JointId.LF_MCP: math.radians(0),
}

flex_middle_finger = {
    JointId.THUMB_PIP: math.radians(0),
    JointId.THUMB_MCP: math.radians(0),
    JointId.THUMB_SWING: math.radians(20),
    JointId.THUMB_ROTATION: math.radians(0),
    JointId.FF_PIP: math.radians(0),
    JointId.FF_MCP: math.radians(0),
    JointId.FF_SWING: math.radians(0),
    JointId.MF_PIP: math.radians(75),
    JointId.MF_MCP: math.radians(70),
    JointId.RF_PIP: math.radians(0),
    JointId.RF_MCP: math.radians(0),
    JointId.LF_PIP: math.radians(0),
    JointId.LF_MCP: math.radians(0),
}

flex_index_middle_and_ring_fingers = {
    JointId.THUMB_PIP: math.radians(0),
    JointId.THUMB_MCP: math.radians(0),
    JointId.THUMB_SWING: math.radians(20),
    JointId.THUMB_ROTATION: math.radians(0),
    JointId.FF_PIP: math.radians(75),
    JointId.FF_MCP: math.radians(70),
    JointId.FF_SWING: math.radians(0),
    JointId.MF_PIP: math.radians(75),
    JointId.MF_MCP: math.radians(70),
    JointId.RF_PIP: math.radians(75),
    JointId.RF_MCP: math.radians(70),
    JointId.LF_PIP: math.radians(0),
    JointId.LF_MCP: math.radians(0),
}

# 通用的关节位置执行函数
def execute_joint_positions(hand, joint_positions, description):
    """通用的关节位置执行函数

    Args:
        hand: DexHand实例
        joint_positions: 关节位置字典
        description: 动作描述

    Returns:
        bool: 动作执行成功返回True，失败返回False
    """
    try:
        joints = Joint.create_joint_positions(joint_positions)
        if not hand.move_joints(joints):
            logger.error(f"{description}执行失败")
            return False
        time.sleep(ACTION_DELAY)
        return True
    except Exception as e:
        logger.error(f"{description}执行失败: {e}")
        return False

# 装饰器：统一错误处理
def handle_action_error(description):
    """统一错误处理装饰器

    Args:
        description: 动作描述

    Returns:
        装饰后的函数
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"{description}执行失败: {e}")
                return False
        return wrapper
    return decorator

@handle_action_error("拇指依次触碰其他手指")
def thumb_touch_tp(hand):
    """拇指依次触碰其他手指的指尖

    动作序列：
    1. 拇指触碰小指
    2. 拇指触碰无名指
    3. 拇指触碰中指
    4. 拇指触碰食指
    5. 复位到零位

    Args:
        hand: DexHand实例

    Returns:
        bool: 动作执行成功返回True，失败返回False
    """
    # 1: 拇指和小指指尖触碰，其他手指保持在零位
    if not execute_joint_positions(hand, thumb_touch_little_finger, "拇指触碰小指"):
        return False

    # 2: 拇指和无名指指尖触碰，其他手指保持在零位
    if not execute_joint_positions(hand, thumb_touch_ring_finger, "拇指触碰无名指"):
        return False

    # 3: 拇指和中指指尖触碰，其他手指保持在零位
    if not execute_joint_positions(hand, thumb_touch_middle_finger, "拇指触碰中指"):
        return False

    # 4: 拇指和食指指尖触碰，其他手指保持在零位
    if not execute_joint_positions(hand, thumb_touch_index_finger, "拇指触碰食指"):
        return False

    # 5: 全部手指保持在零位（使用预设动作）
    if not execute_gesture(hand, GestureType.OPEN_HAND):
        logger.error("手指复位动作执行失败")
        return False
    time.sleep(ACTION_DELAY)

    return True

@handle_action_error("握拳和张开")
def fist_then_open(hand):
    """握拳然后张开的动作（使用预设动作）

    动作序列：
    1. 握拳
    2. 张开手掌

    Args:
        hand: DexHand实例

    Returns:
        bool: 动作执行成功返回True，失败返回False
    """
    # 1: 握拳动作
    if not execute_gesture(hand, GestureType.FIST):
        logger.error("握拳动作执行失败")
        return False
    time.sleep(ACTION_DELAY)

    # 2: 张开手掌动作
    if not execute_gesture(hand, GestureType.OPEN_HAND):
        logger.error("张开手掌动作执行失败")
        return False
    time.sleep(ACTION_DELAY)

    return True

@handle_action_error("顺序张开手指")
def seq_open_finger(hand):
    """依次张开手指的动作

    动作序列：
    1. 握拳
    2. 张开食指
    3. 张开中指
    4. 张开无名指
    5. 张开小拇指
    6. 张开大拇指

    Args:
        hand: DexHand实例

    Returns:
        bool: 动作执行成功返回True，失败返回False
    """
    # 1: 握拳动作（使用预设动作）
    if not execute_gesture(hand, GestureType.FIST):
        logger.error("握拳动作执行失败")
        return False
    time.sleep(ACTION_DELAY)

    # 2: 张开食指动作
    if not execute_joint_positions(hand, open_index_finger, "张开食指"):
        return False

    # 3: 张开中指动作
    if not execute_joint_positions(hand, open_middle_finger, "张开中指"):
        return False

    # 4: 张开无名指动作
    if not execute_joint_positions(hand, open_ring_finger, "张开无名指"):
        return False

    # 5: 张开小拇指动作
    if not execute_joint_positions(hand, open_little_finger, "张开小拇指"):
        return False

    # 6: 张开大拇指动作（使用预设动作）
    if not execute_gesture(hand, GestureType.OPEN_HAND):
        logger.error("张开大拇指动作执行失败")
        return False
    time.sleep(ACTION_DELAY)

    return True

@handle_action_error("食指摆动")
def swing_index_finger(hand):
    """食指摆动动作

    动作序列：
    1. 初始姿势
    2. 负向摆动（-15度）
    3. 正向摆动（15度）
    4. 重复一次
    5. 复位到初始姿势

    Args:
        hand: DexHand实例

    Returns:
        bool: 动作执行成功返回True，失败返回False
    """
    if not execute_joint_positions(hand, open_index_finger, "初始姿势"):
        return False

    for _ in range(2):
        if not execute_joint_positions(hand, index_finger_swing_neg, "食指负向摆动"):
            return False

        if not execute_joint_positions(hand, index_finger_swing_pos, "食指正向摆动"):
            return False

    if not execute_joint_positions(hand, open_index_finger, "复位姿势"):
        return False

    return True

@handle_action_error("手指弯曲")
def flex_finger_movement(hand, cycle_count=FLEX_CYCLE_COUNT):
    """手指弯曲动作序列

    动作序列：
    1. 弯曲小指
    2. 弯曲无名指和小指
    3. 弯曲中指、无名指和小指
    4. 弯曲所有手指
    5. 弯曲食指、中指和无名指
    6. 弯曲食指
    7. 弯曲中指
    8. 复位到零位

    Args:
        hand: DexHand实例
        cycle_count: 循环次数，默认4次

    Returns:
        bool: 动作执行成功返回True，失败返回False
    """
    for i in range(cycle_count):
        logger.info(f"第 {i+1} 次弯曲循环开始")

        if not execute_joint_positions(hand, flex_little_finger, "弯曲小指"):
            return False

        if not execute_joint_positions(hand, flex_ring_and_little_fingers, "弯曲无名指和小指"):
            return False

        if not execute_joint_positions(hand, flex_middle_ring_little_fingers, "弯曲中指、无名指和小指"):
            return False

        if not execute_joint_positions(hand, flex_all_fingers, "弯曲所有手指"):
            return False

        if not execute_joint_positions(hand, flex_index_middle_and_ring_fingers, "弯曲食指、中指和无名指"):
            return False

        if not execute_joint_positions(hand, flex_index_finger, "弯曲食指"):
            return False

        if not execute_joint_positions(hand, flex_middle_finger, "弯曲中指"):
            return False

        # 复位到零位（使用预设动作）
        if not execute_gesture(hand, GestureType.OPEN_HAND):
            logger.error("手指复位动作执行失败")
            return False
        time.sleep(ACTION_DELAY)

    return True

@handle_action_error("OK手势")
def make_ok(hand):
    """OK手势（使用预设动作）

    动作：
    拇指和食指指尖触碰

    Args:
        hand: DexHand实例

    Returns:
        bool: 动作执行成功返回True，失败返回False
    """
    if not execute_gesture(hand, GestureType.OK):
        logger.error("OK手势执行失败")
        return False
    time.sleep(ACTION_DELAY)
    return True

@handle_action_error("第一组动作")
def first_action(hand):
    """第一组动作：拇指触碰和握拳张开

    动作序列：
    1. 拇指依次触碰其他手指
    2. 握拳和张开（重复两次）

    Args:
        hand: DexHand实例

    Returns:
        bool: 动作执行成功返回True，失败返回False
    """
    if not thumb_touch_tp(hand):
        return False

    for i in range(2):
        logger.info(f"第 {i+1} 次握拳和张开循环")
        if not fist_then_open(hand):
            return False

    return True

@handle_action_error("第二组动作")
def second_action(hand, flex_cycles=FLEX_CYCLE_COUNT):
    """第二组动作：顺序张开手指和摆动

    动作序列：
    1. 顺序张开手指
    2. 食指摆动
    3. 手指弯曲动作序列（重复指定次数）
    4. OK手势

    Args:
        hand: DexHand实例
        flex_cycles: 手指弯曲动作的循环次数，默认4次

    Returns:
        bool: 动作执行成功返回True，失败返回False
    """
    if not seq_open_finger(hand):
        return False

    if not swing_index_finger(hand):
        return False

    for i in range(flex_cycles):
        logger.info(f"第 {i+1} 次手指弯曲循环")
        if not flex_finger_movement(hand, cycle_count=1):
            return False

    if not make_ok(hand):
        return False

    return True

def main():
    logger.info("***** 枭尧灵巧手 SDK - 手势舞功能演示 *****")
    hand = DexHand()
    connected = hand.open(CommType.ETHERCAT, "auto")

    try:
        if not connected:
            logger.error("[扫描结束] 未能连接到灵巧手。")
            return

        logger.info("\n--- 设备已就绪，将开始手势舞功能演示 ---")

        # 循环执行手势动作
        gesture_cycle = 0
        max_cycles = 0  # 设置循环次数，可以根据需要调整，0表示无限循环

        while True:
            gesture_cycle += 1
            if max_cycles > 0 and gesture_cycle > max_cycles:
                break

            logger.info(f"\n--- 第 {gesture_cycle} 轮手势演示开始 ---")

            if not first_action(hand):
                logger.error(f"第 {gesture_cycle} 轮演示中的第一组动作执行失败")
                break

            if not second_action(hand):
                logger.error(f"第 {gesture_cycle} 轮演示中的第二组动作执行失败")
                break

            logger.info(f"--- 第 {gesture_cycle} 轮手势演示结束 ---")

            # 提示信息
            if max_cycles == 0:
                logger.info("按 Ctrl+C 停止演示并退出程序")

    except KeyboardInterrupt:
        logger.info("\n\n程序被用户中断。")
    except Exception as e:
        logger.error(f"\n[严重错误] {e}")
    finally:
        hand.close()
        time.sleep(0.5)
        logger.info("\n--- 演示结束，断开连接 ---")

if __name__ == "__main__":
    main()
