# module.py

from . import comm # 导入 comm 模块，以便 Module 能够访问 Dispatcher

class Module:
    """
    所有模块的基类。
    每个模块实例都会通过 client_dispatcher 访问底层的通讯机制。
    """
    def __init__(self, client_dispatcher):
        self._dispatcher = client_dispatcher
    
    def _send_internal_msg(self, msg_type, data=None):
        """
        供模块内部调用的发送消息方法。
        它通过与该模块实例关联的调度器发送消息。
        """
        # 在实际SDK中，这里会创建并序列化一个Message对象，然后通过dispatcher发送
        return self._dispatcher.send(comm.Message(msg_type, data))

    def _recv_internal_msg(self, msg_type, timeout=1.0):
        """
        供模块内部调用的接收消息方法（通常用于订阅或异步回调）。
        """
        # 在实际SDK中，这里会从dispatcher获取或等待特定类型的消息
        return self._dispatcher.recv(msg_type, timeout)