.. _connection:

设备连接指南
==============

枭尧灵巧手支持多种连接方式：

EtherCAT连接
------------
.. code-block:: python

   from ghand.hand import DexHand, CommType
   
   hand = DexHand()
   hand.open_ethercat(CommType.ETHERCAT, "device_id_123")

   # 或自动连接您当前的灵巧手设备
   hand.open_ethercat(CommType.ETHERCAT, "auto")

连接故障排除
------------
1. 检查物理连接是否正常
2. 确认设备ID正确
3. 检查波特率设置
4. 重启设备尝试重新连接
