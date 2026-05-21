.. _beginner:

###################
Getting Started
###################

This guide will help you quickly get started with the GHand Python SDK.

Step 1: Install SDK
------------------------
.. code-block:: bash

   python setup.py install

Step 2: Connect Device
------------------------
Refer to the :ref:`connection` guide.

Step 3: Run Example Code
------------------------
.. code-block:: python

   from ghand.ghand import GHand, CommType

   # Create dexterous hand object
   hand = GHand()

   # Connect to dexterous hand device
   hand.open(CommType.ETHERCAT, "your device id")
   # Or automatically connect to your current dexterous hand device
   hand.open(CommType.ETHERCAT,  "auto")

   # Get hand type (left/right) and print
   hand_type = hand.get_hand_type()
   print(hand_type.value)


Using Example Programs
------------------------
More example programs are in the ``/ghand/examples`` directory.
