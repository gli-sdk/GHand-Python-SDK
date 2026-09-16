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

"""Communication layer for the GHand SDK."""

from .factory import create_comm
from .icomm import IComm

__all__ = [
    "IComm",
    "create_comm",
    "CanfdComm",
    "EthercatComm",
    "Rs485Comm",
]


def __getattr__(name: str):
    if name == "CanfdComm":
        from .canfd_comm import CanfdComm

        return CanfdComm
    if name == "EthercatComm":
        from .ethercat_comm import EthercatComm

        return EthercatComm
    if name == "Rs485Comm":
        from .rs485_comm import Rs485Comm

        return Rs485Comm
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
