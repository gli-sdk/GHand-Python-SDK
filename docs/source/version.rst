===========
Version Notes
===========

To provide a better user experience and support more powerful features, the developer documentation will be updated regularly. Before use, please confirm whether your dexterous hand firmware version, SDK version, and documentation version match. If they do not match, it is recommended to update the software to the required version or use the documentation for the corresponding version.

Refer to the version information table below:

2025/10/15 Update:

+-------------+------------------+--------------+
|    doc      | GHand Firmware   |  GHand SDK   |
+=============+==================+==============+
|   v0.0.1    |      v1.0.0      |    v1.0.0    |
+-------------+------------------+--------------+

1. Created initial version

2025/10/23 Update:

+-------------+------------------+--------------+
|    doc      | GHand Firmware   |  GHand SDK   |
+=============+==================+==============+
|   v0.0.1    |      v1.0.0      |    v1.0.1    |
+-------------+------------------+--------------+

1. Fixed spelling error in "Install Npcap Library" in environment setup
2. Updated SDK version to 1.0.1

2025/12/19 Update:

+-------------+------------------+--------------+
|    doc      | GHand Firmware   |  GHand SDK   |
+=============+==================+==============+
|   v0.2.0    |      v1.1.6      |    v1.0.2    |
+-------------+------------------+--------------+

1. Optimized device shutdown process to ensure slave switches to INIT state before shutting down master
2. Removed unimplemented light control methods
3. Updated example file contents and deleted obsolete examples
4. Fixed hardcoded network card ID in example code, changed to "auto" automatic recognition
5. Migrated create_joint_positions function to Joint class as a static method
6. Added joint angle limit checking logic and set to boundary values when exceeded
7. Example file renaming and cleanup, removed unused do_gesture_dance imports
8. Added steps for building documentation
9. Replaced print debug information with logging
10. Updated Python version requirement description, clearly stating supported Python version range is 3.10 to 3.13
11. Improved data subscription functionality, including subscription management and data processing examples
12. Updated SDK version to 1.0.2

2026/1/14 Update:

+-------------+------------------+--------------+
|    doc      | GHand Firmware   |  GHand SDK   |
+=============+==================+==============+
|   v0.2.1    |      v1.2.0      |    v1.1.0    |
+-------------+------------------+--------------+

1. Added tactile functionality
2. Removed unused files
3. Updated example file contents
4. Modified example file names
5. Updated SDK version to 1.1.0

2026/3/6 Update:

+-------------+------------------+--------------+
|    doc      | GHand Firmware   |  GHand SDK   |
+=============+==================+==============+
|   v0.2.2    |      v1.2.1      |    v1.1.1    |
+-------------+------------------+--------------+

1. Added exception handling functionality and examples
2. Added preset gesture functionality
3. Added get_hand_info method to get hand status, error, and temperature
4. Added Linux system support
5. Added manual/automatic multi-hand connection
6. Fixed device information acquisition failure issue caused by repeated connect/disconnect operations
7. Deleted unused method: tactile_restart
8. Fixed issue where opening another program during device connection overwrites the previous connection
9. Modified log display

2026/4/16 Update:

+-------------+------------------+--------------+
|    doc      | GHand Firmware   |  GHand SDK   |
+=============+==================+==============+
|   v0.2.3    |      v2.4.2      |    v1.1.2    |
+-------------+------------------+--------------+

1. Updated default log output to WARNING and ERROR levels
2. Added subscription manager resource cleanup
3. Added torque control and speed control example programs
4. Added CtrlMode enum type and modified move_joints method parameters
5. Added collision detection functionality and examples
6. Added get_motor_driver_version method and example
