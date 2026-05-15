环境设置
==============

检查Python版本
--------------
GHand SDK支持Python 3.10到3.13版本。

.. code-block:: bash

   # 检查Python版本
   python --version

   # 如果版本不符，请安装正确的Python版本

安装Npcap库
--------------
正确下载并安装Npcap安装程序，Npcap官方网址：https://npcap.com/

检查C/C++ 编译工具
-------------------------------
在安装依赖前请确保您的系统或环境包含C/C++编译工具。

Windows系统可以安装Microsoft C++ 生成工具，并选择“使用C++的桌面开发”，进行C/C++编译工具的安装。

Microsoft C++ 生成工具官方网址：https://visualstudio.microsoft.com/zh-hans/visual-cpp-build-tools/

安装依赖
--------
使用pip安装所需依赖：

.. code-block:: bash

   pip install -r requirements.txt

配置开发环境
------------
推荐使用VS Code作为开发环境，并安装Python扩展。