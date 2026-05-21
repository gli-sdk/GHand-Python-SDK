# Copyright (c) 2026 GLITech
#
# Licensed under the MIT License. See LICENSE in the project root for license information.

"""Communication layer for the GHand SDK."""

from .canfd_comm import CANFDComm
from .ethercat_comm import EtherCATComm
from .icomm import IComm
from .rs485_comm import RS485Comm
