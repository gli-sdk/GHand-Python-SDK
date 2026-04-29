"""
示例：多灵巧手控制器（支持任意数量）

这个示例展示了如何创建一个通用的控制器类，自动连接任意数量的灵巧手，
并提供了简洁的接口来控制它们。
"""
import time
import math
import logging
from typing import List, Dict, Optional
from xiaoyao.dexhand import DexHand, CommType, Joint, JointId
from xiaoyao import configure_logging

# Configure SDK logging
configure_logging(level=logging.INFO)


class MultiDexHandController:
    """
    多灵巧手控制器

    自动连接任意数量的灵巧手，并提供便捷的接口来控制它们。
    支持自动搜索或手动指定网络接口。

    用法示例:
        # 方式1：自动搜索所有可用接口并连接
        controller = MultiDexHandController(auto_search=True)

        # 方式2：手动指定网络接口
        controller = MultiDexHandController(
            interfaces=["\\Device\\NPF_{...}", "\\Device\\NPF_{...}"]
        )

        # 初始化（自动连接所有找到的设备）
        if controller.initialize():
            # 获取所有手的信息
            all_hands = controller.get_all_hands()

            # 控制特定手
            controller.move_hand("hand_0", joints)

            # 或同时控制所有手
            controller.move_all_hands([joints0, joints1, ...])

        # 使用完毕后关闭
        controller.close_all()
    """

    def __init__(self, interfaces: List[str] = None, auto_search: bool = False):
        """
        初始化多灵巧手控制器

        Args:
            interfaces: 网络接口ID列表（可选）
            auto_search: 是否自动搜索所有可用网络接口（推荐）
        """
        self.auto_search = auto_search
        self.interfaces = interfaces or []

        # 存储所有手的信息
        self.hands: Dict[str, DexHand] = {}
        self.hand_info: Dict[str, dict] = {}
        self.interface_to_hand: Dict[str, str] = {}  # interface -> hand_name

        # 连接状态
        self._initialized = False

        # 如果启用自动搜索，获取所有可用接口
        if auto_search:
            temp_hand = DexHand()
            self.interfaces = temp_hand.get_connectable_devices()
            del temp_hand
            print(f"自动搜索到 {len(self.interfaces)} 个可连接设备")

    def _detect_connected_interfaces(self, available_interfaces: List[str]) -> List[str]:
        """
        检测哪些接口实际连接了设备

        Args:
            available_interfaces: 所有可用网络接口列表

        Returns:
            list: 实际连接了设备的接口列表
        """
        connected_interfaces = []

        print("\n检测哪些接口连接了设备...")
        for i, iface in enumerate(available_interfaces):
            print(f"  测试接口 {i}: {iface}")

            # 尝试连接
            test_hand = DexHand()
            try:
                if test_hand.open(CommType.ETHERCAT, iface):
                    # 成功检测到设备
                    connected_interfaces.append(iface)
                    print(f"    ✓ 检测到设备")
                    test_hand.close()
                else:
                    print(f"    ✗ 连接失败")
            except Exception as e:
                print(f"    ✗ 错误: {e}")
            finally:
                del test_hand

        print(f"\n共检测到 {len(connected_interfaces)} 个设备")
        return connected_interfaces

    def initialize(self) -> bool:
        """
        自动连接所有设备并读取设备信息

        Returns:
            bool: 至少成功连接一个设备返回 True，否则返回 False
        """
        print("\n=== 初始化多灵巧手控制器 ===")

        if not self.interfaces:
            print("没有可用的网络接口")
            return False

        # 第一步：连接所有设备
        print(f"\n第一步：连接 {len(self.interfaces)} 个设备...")
        connected_hands = []
        connected_interfaces = []

        for i, interface in enumerate(self.interfaces):
            print(f"  连接设备 {i}: {interface}")

            hand = DexHand()
            try:
                if hand.open(CommType.ETHERCAT, interface):
                    hand_name = f"hand_{i}"
                    self.hands[hand_name] = hand
                    self.interface_to_hand[interface] = hand_name
                    connected_hands.append((hand_name, hand))
                    connected_interfaces.append(interface)
                    print(f"    ✓ 连接成功")
                else:
                    print(f"    ✗ 连接失败")
                    del hand
            except Exception as e:
                print(f"    ✗ 错误: {e}")
                del hand

        if not connected_hands:
            print("没有成功连接任何设备")
            return False

        print(f"\n✓ 成功连接 {len(connected_hands)} 个设备")

        # 第二步：获取所有设备信息
        print(f"\n第二步：获取所有设备信息...")
        for hand_name, hand in connected_hands:
            try:
                hand_info = {
                    'name': hand.get_device_name(),
                    'hardware_version': hand.get_hardware_version(),
                    'firmware_version': hand.get_firmware_version(),
                    'serial_number': hand.get_serial_number(),
                    'hand_type': hand.get_hand_type().value,
                    'interface': self.interface_to_hand.get(hand_name, '')
                }
                self.hand_info[hand_name] = hand_info

                print(
                    f"  {hand_name}: {hand_info['name']} "
                    f"({hand_info['hand_type']}, "
                    f"SN: {hand_info['serial_number']}, "
                    f"FW: {hand_info['firmware_version']}, "
                    f"HW: {hand_info['hardware_version']})"
                )
            except Exception as e:
                print(f"  获取 {hand_name} 信息失败: {e}")

        self._initialized = True
        print(f"\n✓ 初始化完成")
        return True

    def get_hand_names(self) -> List[str]:
        """
        获取所有已连接手的名称

        Returns:
            list: 手的名称列表
        """
        return list(self.hands.keys())

    def get_hand_count(self) -> int:
        """
        获取已连接手的数量

        Returns:
            int: 手的数量
        """
        return len(self.hands)

    def get_hand_info(self, hand_name: str) -> Optional[dict]:
        """
        获取指定手的信息

        Args:
            hand_name: 手的名称

        Returns:
            dict: 手的信息字典，如果不存在返回 None
        """
        return self.hand_info.get(hand_name)

    def get_all_hands_info(self) -> Dict[str, dict]:
        """
        获取所有手的信息

        Returns:
            dict: 键为手名称，值为信息字典
        """
        return self.hand_info.copy()

    def move_hand(self, hand_name: str, joints: List[Joint]) -> bool:
        """
        控制指定的手

        Args:
            hand_name: 手的名称
            joints: 关节命令列表

        Returns:
            bool: 成功返回 True
        """
        if not self._initialized:
            print("控制器未初始化")
            return False

        if hand_name not in self.hands:
            print(f"手 '{hand_name}' 不存在")
            return False

        hand = self.hands[hand_name]
        return hand.move_joints(joints)

    def move_all_hands(self, joints_list: List[List[Joint]]) -> bool:
        """
        同时控制所有手

        Args:
            joints_list: 关节命令列表的列表，每个元素对应一只手

        Returns:
            bool: 全部成功返回 True
        """
        if not self._initialized:
            print("控制器未初始化")
            return False

        hand_names = self.get_hand_names()

        if len(joints_list) != len(hand_names):
            print(
                f"关节数量不匹配: 有 {len(hand_names)} 只手, "
                f"但提供了 {len(joints_list)} 组关节命令"
            )
            return False

        success_all = True
        for hand_name, joints in zip(hand_names, joints_list):
            print(f"控制 {hand_name}...")
            if not self.move_hand(hand_name, joints):
                success_all = False

        return success_all

    def get_hand_joints(self, hand_name: str) -> List[Joint]:
        """
        获取指定手的关节状态

        Args:
            hand_name: 手的名称

        Returns:
            list: 关节状态列表
        """
        if not self._initialized:
            print("控制器未初始化")
            return []

        if hand_name not in self.hands:
            print(f"手 '{hand_name}' 不存在")
            return []

        hand = self.hands[hand_name]
        return hand.get_joints()

    def get_all_joints(self) -> Dict[str, List[Joint]]:
        """
        获取所有手的关节状态

        Returns:
            dict: 键为手名称，值为关节状态列表
        """
        if not self._initialized:
            print("控制器未初始化")
            return {}

        result = {}
        for hand_name in self.get_hand_names():
            result[hand_name] = self.get_hand_joints(hand_name)

        return result

    def close_all(self):
        """关闭所有连接"""
        if self._initialized:
            for hand_name, hand in self.hands.items():
                try:
                    hand.close()
                    print(f"已关闭 {hand_name}")
                except Exception as e:
                    print(f"关闭 {hand_name} 失败: {e}")

            self.hands.clear()
            self.hand_info.clear()
            self._initialized = False
            print("所有连接已关闭")

    def __enter__(self):
        """支持上下文管理器"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出时自动关闭"""
        self.close_all()


def main():
    """示例：使用多灵巧手控制器"""

    # 方式1：自动搜索并连接所有可用设备（推荐）
    print("=== 方式1：自动搜索模式 ===")
    controller = MultiDexHandController(auto_search=True)

    # 方式2：手动指定网络接口
    # controller = MultiDexHandController(
    #     interfaces=[
    #         "\\Device\\NPF_{FDC7358F-FC71-4446-8247-A53015F23C29}",
    #         "\\Device\\NPF_{D40A6875-C1A4-499A-BD51-273F04D08604}"
    #     ]
    # )

    # 自动连接所有设备
    if not controller.initialize():
        print("初始化失败")
        return

    # 显示设备信息
    print(f"\n=== 成功连接 {controller.get_hand_count()} 只灵巧手 ===")
    all_info = controller.get_all_hands_info()
    for hand_name, info in all_info.items():
        print(
            f"{hand_name}: {info['name']} "
            f"({info['hand_type']}, SN: {info['serial_number']})"
        )

    # 示例：分别控制每只手
    print("\n=== 示例：分别控制 ===")

    # 准备关节命令
    test_joints = [
        Joint(id=JointId.THUMB_PIP, angle=math.radians(30), speed=100, torque=100),
        Joint(id=JointId.FF_PIP, angle=math.radians(45), speed=100, torque=100),
        Joint(id=JointId.FF_MCP, angle=math.radians(30), speed=100, torque=100),
    ]

    # 控制所有手
    for hand_name in controller.get_hand_names():
        print(f"控制 {hand_name}...")
        if controller.move_hand(hand_name, test_joints):
            print(f"  ✓ 指令发送成功")
            time.sleep(1)

            # 读取关节状态
            joints = controller.get_hand_joints(hand_name)
            print(f"  当前关节数: {len(joints)}")

    # 示例：同时控制所有手
    print("\n=== 示例：同时控制 ===")

    # 准备复位命令
    reset_joints = [
        Joint(id=JointId.THUMB_PIP, angle=math.radians(0), speed=100, torque=100),
        Joint(id=JointId.FF_PIP, angle=math.radians(0), speed=100, torque=100),
        Joint(id=JointId.FF_MCP, angle=math.radians(0), speed=100, torque=100),
    ]

    # 为每只手准备命令
    all_joints = [reset_joints] * controller.get_hand_count()

    print("同时控制所有手...")
    if controller.move_all_hands(all_joints):
        print("  ✓ 所有手指令发送成功")
        time.sleep(1)

    # 获取所有手的关节状态
    print("\n=== 关节状态 ===")
    all_joints_state = controller.get_all_joints()
    for hand_name, joints in all_joints_state.items():
        print(f"\n{hand_name}: {len(joints)} 个关节")
        for joint in joints:
            print(
                f"  {JointId(joint.id).name:<15}- angle: {math.degrees(joint.angle):.2f}°, "
                f"speed: {joint.speed}, torque: {joint.torque}"
            )

    print("\n=== 完成 ===")

    # 关闭所有连接
    controller.close_all()


if __name__ == "__main__":
    main()
