.. _installs:

安装与配置指南
================

系统要求
--------
- Python 3.10 to 3.13
- Windows 10/Linux Ubuntu 18.04+/macOS 10.15+
- 推荐内存：8GB+
- 存储空间：1GB+

安装SDK
-------
.. code-block:: bash

   # 使用pip安装
   pip install xiaoyao
   
   # 或者从源代码安装
   git clone https://gitee.com/glitech/xiaoyao-sdk.git
   cd xiaoyao-sdk
   python setup.py install

固件升级步骤
---------------------
1. 下载最新固件文件
2. 连接设备
3. 执行升级命令：
   
   .. code-block:: python
   
      from xiaoyao.hand import DexHand, CommType
      
      hand = DexHand()
      hand.open(CommType.ETHERCAT, "your device id")
      hand.upgrade_firmware("/path/to/firmware.bin")
   
4. 等待升级完成（约3-5分钟）
5. 设备将自动重启

卸载SDK
---------------------
.. code-block:: bash

   pip uninstall xiaoyao