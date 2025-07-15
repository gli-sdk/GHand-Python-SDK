.. _installs:

安装与配置指南
================

系统要求
--------
- Python 3.8+
- Windows 10/Linux Ubuntu 18.04+/macOS 10.15+
- 推荐内存：4GB+
- 存储空间：500MB+

安装SDK
-------
.. code-block:: bash

   # 使用pip安装
   pip install xiaoyao-sdk
   
   # 或者从源代码安装
   git clone https://github.com/guolizhineng/xiaoyao-sdk.git
   cd xiaoyao-sdk
   pip install .

安装依赖库
---------
.. code-block:: bash

   pip install numpy pyserial

固件升级步骤
-----------
1. 下载最新固件文件
2. 连接设备
3. 执行升级命令：
   
   .. code-block:: python
   
      from xiaoyao.hand import Hand
      
      hand = Hand()
      hand.upgrade_firmware("/path/to/firmware.bin")
   
4. 等待升级完成（约3-5分钟）
5. 设备将自动重启

卸载SDK
-------
.. code-block:: bash

   pip uninstall xiaoyao-sdk