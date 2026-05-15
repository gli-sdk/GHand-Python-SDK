.. _downloads:

资源下载
==========

SDK安装包
-----------

您可以通过以下方式获取 GHand Python SDK：

**从源代码安装（当前唯一方式）**

.. code-block:: bash

   # 克隆仓库
   git clone https://gitee.com/glitech/ghand-sdk.git
   cd ghand-sdk

   # 安装 SDK
   python setup.py install

**当前版本**

- 最新版本：v1.1.1
- Python 要求：3.10 - 3.13
- 支持平台：Windows 10/11

示例代码
-----------

所有示例代码均包含在 SDK 仓库的 ``examples/`` 目录中。

**基础示例**

1. **获取基本信息** - ``1.get_basic_info.py``
   - 获取设备 ID、版本号、手部类型等基本信息
   - 查看手部运行状态

2. **关节控制** - ``2.move_joints.py``
   - 控制单个关节运动
   - 控制多个关节同时运动
   - 设置目标角度、速度和力矩

3. **预设手势** - ``3.do_preset_gestrue.py``
   - 执行预设的手势动作
   - 支持多种常用手势模式

4. **数据手套** - ``4.get_glove_data.py``
   - 读取数据手套输入
   - 实时映射到灵巧手

**动作示例**

5. **舞蹈手势** - ``5.do_gesture_dance.py``
   - 演示连续手势动作

6. **抓取动作** - ``6.grabbing_action.py``
   - 演示抓取物体动作

7. **按压动作** - ``7.press_action.py``
   - 演示按压操作

8. **拍手动作** - ``8.clap_action.py``
   - 演示拍手动作

9. **持握动作** - ``9.hold_action.py``
   - 演示持握物体动作

10. **敲击动作** - ``10.knock_action.py``
    - 演示敲击操作

11. **抬起动作** - ``11.lift_action.py``
    - 演示抬举动作

12. **拉取动作** - ``12.pull_action.py``
    - 演示拉拽操作

13. **支撑动作** - ``13.support_action.py``
    - 演示支撑动作

**高级功能示例**

14. **触觉合力** - ``14.get_tactile_resultant_force.py``
    - 获取触觉传感器的合力数据
    - 用于力反馈控制

15. **数据订阅** - ``15.subscription_demo.py``
    - 演示数据订阅功能
    - 实时接收关节和传感器数据

16. **交互式控制** - ``16.interactive_joint_control.py``
    - 提供交互式命令行控制界面
    - 实时调整关节参数

**运行示例**

.. code-block:: bash

   # 进入示例目录
   cd examples

   # 运行特定示例（需要先连接设备）
   python 1.get_basic_info.py

文档下载
-----------

**在线文档**

- **GitHub/Gitee 仓库**: https://gitee.com/glitech/ghand-sdk
  - 包含最新源码、问题追踪和更新日志

- **API 参考文档**: 本文档系统提供完整的 API 参考
  - 模块说明
  - 类和函数详细说明
  - 参数和返回值说明

**离线文档生成**

如需生成离线文档，请执行：

.. code-block:: bash

   # 安装文档工具
   pip install sphinx sphinx-rtd-theme

   # 进入文档目录
   cd docs

   # 生成 HTML 文档
   sphinx-build -b html source build

   # 在浏览器中打开
   # open build/html/index.html  (macOS)
   # xdg-open build/html/index.html  (Linux)
   # start build/html/index.html  (Windows)

**相关资源**

- **依赖库**: Npcap (Windows), EtherCAT 配置工具
- **驱动程序**: USB 转串口驱动（如使用 RS485 通信）
- **开发工具**: Python IDE（推荐 PyCharm/VSCode）

**获取帮助**

- **问题反馈**: 在 Gitee 仓库提交 Issue
- **功能建议**: 欢迎提交 Pull Request
- **技术支持**: 查看文档或联系技术支持团队
