.. _introduction:

Introduction
============

The GHand Python SDK is the official development toolkit for the XiaoYao Dexterous Hand. It provides a complete Python API that allows developers to easily interact with the dexterous hand, enabling precise control and data acquisition for joints, sensors, and other core functions.

Key Features
------------
- Hand-level Control:
    - Get overall hand status and basic information (device ID, version, hand type, etc.).
    - Clear hand protection state.
    - Configure and get communication mode (EtherCAT, CAN, RS485).
    - Hand reboot and position initialization.
    - Hardware self-test (sensors, motors).
    - Firmware upgrade.
- Fine Joint Control:
    - Set target angle, speed, or torque for single or multiple joints.
    - Get current angle, speed, and torque for single or all joints.
    - Stop all joint motion.
- Tactile Sensing:
    - Read five-finger tactile sensor arrays and resultant force data (52 sensors for thumb, 31 sensors for each of the other four fingers).
    - Tactile sensor control (open, close, zero).
