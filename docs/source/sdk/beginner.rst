.. _beginner:

初学者指南
============

本指南将帮助您快速开始使用Xiaoyao灵巧手SDK。

第一步：安装SDK
---------------
.. code-block:: bash

   pip install xiaoyao-sdk

第二步：连接设备
----------------
参考 :ref:`connection` 指南

第三步：运行示例代码
-------------------
.. code-block:: python

   from xiaoyao.hand import Hand
   
   # 初始化手部控制
   hand = Hand()
   
   # 执行预设手势
   hand.do_preset_gesture(hand.GestureType.FIST)
   
   print("手势执行完成！")

常见问题
--------
问：如何获取设备状态？
答：使用 ``get_operation_status()`` 方法

问：如何更新固件？
答：参考 :ref:`installs` 指南