import time
from xiaoyao.dexhand import DexHand, CommType, Joint, JointId


def main():
    hand = DexHand()
    connected = hand.open(CommType.ETHERCAT, "auto")
    if not connected:
        print("connect failed")
        return

    th_pip = Joint(id=JointId.THUMB_PIP, angle=10)
    th_mcp = Joint(id=JointId.THUMB_MCP, angle=10)
    joints = [th_pip, th_mcp]
    hand.move_joints(joints=joints)
    for i in range(10):
        joints = hand.get_joints()
        print(joints)
        time.sleep(0.1)
    hand.close()
