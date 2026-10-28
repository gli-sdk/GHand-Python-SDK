# SPDX-FileCopyrightText: 2025-2026 GLITech
# SPDX-License-Identifier: Apache-2.0

# Copyright 2026 GLITech
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Communication protocol factory for creating IComm instances."""

from .._product_config import ProductConfig
from ..types import CommType
from .icomm import IComm


def create_comm(comm_type: CommType, config: ProductConfig) -> IComm:
    """Factory function to create communication protocol instances.

    Args:
        comm_type: Type of communication protocol (RS485, CANFD, or EtherCAT).
        config: Product configuration.

    Returns:
        IComm instance for the specified protocol.

    Raises:
        ValueError: If comm_type is not supported.
    """
    if comm_type == CommType.ETHERCAT:
        from .ethercat_comm import EthercatComm
        return EthercatComm(config)
    elif comm_type == CommType.CANFD:
        from .canfd_comm import CanfdComm
        return CanfdComm(config)
    elif comm_type == CommType.RS485:
        from .rs485_comm import Rs485Comm
        return Rs485Comm(config)
    else:
        raise ValueError(f"Unsupported communication type: {comm_type}")
