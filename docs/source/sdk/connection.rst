.. _connection:

Device Connection Guide
=======================

The XiaoYao Dexterous Hand supports multiple connection methods:

EtherCAT Connection
-------------------
.. code-block:: python

   from ghand.ghand import GHand, CommType

   hand = GHand()
   hand.open(CommType.ETHERCAT, "device_id_123")

   # Or automatically connect to your current dexterous hand device
   hand.open(CommType.ETHERCAT, "auto")

Connection Troubleshooting
--------------------------
1. Check whether the physical connection is normal
2. Confirm the device ID is correct
3. Check baud rate settings
4. Restart the device and attempt to reconnect
