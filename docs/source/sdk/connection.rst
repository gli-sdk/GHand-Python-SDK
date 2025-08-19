.. _connection:

设备连接指南
==============

Xiaoyao灵巧手支持多种连接方式：

EtherCAT连接
------------
.. code-block:: python

   from xiaoyao.hand import DexHand, CommType
   
   hand = DexHand()
   hand.open_ethercat(CommType.ETHERCAT, "device_id_123")

CAN总线连接
-----------
.. code-block:: python

   from xiaoyao.hand import DexHand, CommType
   
   hand = DexHand()
   hand.set_can_com(baud_rate=1000000, node_id=1)

RS485连接
---------
.. code-block:: python

   from xiaoyao.hand import DexHand, CommType
   
   hand = DexHand()
   hand.set_rs485_com(baud_rate=115200, data_bits=8, stop_bits=1, parity='none')

连接故障排除
------------
1. 检查物理连接是否正常
2. 确认设备ID正确
3. 检查波特率设置
4. 重启设备尝试重新连接