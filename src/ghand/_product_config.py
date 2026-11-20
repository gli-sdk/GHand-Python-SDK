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
"""Internal product configuration dataclasses."""

from dataclasses import dataclass, field

from .types.enums import JointId, ProductType, TactileSensorId


@dataclass
class TactileRegionConfig:
    """Configuration for a single tactile sensor region."""

    id: TactileSensorId
    count: int


@dataclass
class ProductConfig:
    """Product-specific configuration loaded from JSON."""

    name: str = ""
    model: str = ""
    all_joints: list[JointId] = field(default_factory=list)
    active_joints: dict[JointId, tuple[float, float]] = field(default_factory=dict)
    has_tactile: bool = False
    tactile_regions: list[TactileRegionConfig] = field(default_factory=list)
    product_type: ProductType | None = None
