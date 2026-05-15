.. _beginner:

####################################
新手入门
####################################

本指南将帮助您快速开始使用GHand Python SDK。

第一步：安装SDK
------------------------
.. code-block:: bash

   python setup.py install

第二步：连接设备
------------------------
参考 :ref:`connection` 指南

第三步：运行示例代码
------------------------
.. code-block:: python

   from ghand.dexhand import DexHand, CommType
   
   # 创建灵巧手对象
   hand = DexHand()
   
   # 连接灵巧手设备
   hand.open(CommType.ETHERCAT, "your device id")
   # 或自动连接您当前的灵巧手设备
   hand.open(CommType.ETHERCAT,  "auto")
   
   # 获取手部类型（左手/右手）并打印
   hand_type = hand.get_hand_type()
   print(hand_type.value)


使用示例程序
------------------------
更多示例程序在``/ghand/examples``目录下。