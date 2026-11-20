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
"""Internal helpers for parsing and displaying device enum values."""

import enum
from typing import TypeVar

_DeviceValue = TypeVar("_DeviceValue", bound=enum.IntEnum)


def parse_device_value(enum_type: type[_DeviceValue], value: int) -> _DeviceValue | int:
    """Return a known enum member or the original undefined integer."""
    try:
        return enum_type(value)
    except ValueError:
        return value


def format_device_value(value: enum.IntEnum | int) -> str:
    """Display a device value with its enum name or undefined."""
    name = value.name if isinstance(value, enum.IntEnum) else "undefined"
    return f"{int(value)}({name})"
