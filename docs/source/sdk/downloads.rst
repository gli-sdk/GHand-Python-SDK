.. _downloads:

Resource Downloads
==================

SDK Installation Package
------------------------

You can obtain the GHand Python SDK in the following ways:

**Install from Source (currently the only way)**

.. code-block:: bash

   # Clone the repository
   git clone https://github.com/gli-sdk/GHand-Python-SDK
   cd GHand-Python-SDK

   # Install SDK
   python setup.py install

**Current Version**

- Latest version: v1.1.2
- Python requirement: 3.10 - 3.13
- Supported platforms: Windows 10/11, Linux Ubuntu 18.04+

Example Code
------------

All example code is included in the ``examples/`` directory of the SDK repository.

**Basic Examples**

1. **Get Basic Info** - ``01.get_basic_info.py``
   - Get device ID, version, hand type, and other basic information
   - View hand running status

2. **Joint Control** - ``02.move_joints.py``
   - Control single joint motion
   - Control multiple joints simultaneously
   - Set target angle, speed, and torque

3. **Preset Gestures** - ``01.preset_gesture.py``
   - Execute preset gesture actions
   - Support multiple common gesture modes

4. **Data Glove** - ``08.glove_control.py``
   - Read data glove input
   - Real-time mapping to dexterous hand

**Action Examples**

5. **Gesture Dance** - ``02.gesture_dance.py``
   - Demonstrate continuous gesture actions

6. **Grabbing Action** - ``03.grabbing_action.py``
   - Demonstrate grabbing object action

7. **Press Action** - ``04.press_action.py``
   - Demonstrate press operation

8. **Clap Action** - ``05.clap_action.py``
   - Demonstrate clap action

9. **Hold Action** - ``06.hold_action.py``
   - Demonstrate holding object action

10. **Knock Action** - ``07.knock_action.py``
    - Demonstrate knock operation

11. **Lift Action** - ``08.lift_action.py``
    - Demonstrate lifting action

12. **Pull Action** - ``09.pull_action.py``
    - Demonstrate pulling action

13. **Support Action** - ``10.support_action.py``
    - Demonstrate support action

**Advanced Function Examples**

14. **Tactile Resultant Force** - ``05.tactile_callback.py``
    - Get tactile sensor resultant force data
    - Used for force feedback control

15. **Data Subscription** - ``06.subscription_demo.py``
    - Demonstrate data subscription functionality
    - Real-time reception of joint and sensor data

16. **Interactive Control** - ``09.interactive_joint_control.py``
    - Provide interactive command-line control interface
    - Real-time adjustment of joint parameters

**Running Examples**

.. code-block:: bash

   # Enter example directory
   cd examples

   # Run a specific example (device connection required first)
   python tutorial/01.get_basic_info.py

Document Downloads
------------------

**Online Documentation**

- **GitHub Repository**: https://github.com/gli-sdk/GHand-Python-SDK
  - Includes latest source code, issue tracking, and changelog

- **API Reference Documentation**: This documentation system provides complete API reference
  - Module descriptions
  - Detailed class and function descriptions
  - Parameter and return value descriptions

**Offline Document Generation**

To generate offline documentation, please execute:

.. code-block:: bash

   # Install documentation tools
   pip install sphinx sphinx-rtd-theme

   # Enter docs directory
   cd docs

   # Generate HTML documentation
   sphinx-build -b html source build

   # Open in browser
   # open build/html/index.html  (macOS)
   # xdg-open build/html/index.html  (Linux)
   # start build/html/index.html  (Windows)

**Related Resources**

- **Dependencies**: Npcap (Windows), EtherCAT configuration tools
- **Drivers**: USB to serial port driver (if using RS485 communication)
- **Development Tools**: Python IDE (PyCharm/VSCode recommended)

**Get Help**

- **Issue Feedback**: Submit an Issue in the GitHub repository
- **Feature Suggestions**: Pull Requests are welcome
- **Technical Support**: Check the documentation or contact the technical support team
