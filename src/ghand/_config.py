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

"""Product configuration loader and JSON search/parsing.

External configuration directories override the configs bundled inside the
``ghand`` package. The SDK ships ``config/*.json`` in the wheel, so product
configs work out of the box after ``pip install``.
"""

import glob
import json
import logging
import os
from importlib.resources import files

from .types import (
    JointId,
    ProductConfig,
    ProductType,
    TactileRegionConfig,
    TactileSensorId,
)

logger = logging.getLogger("ghand.config")


_PRODUCT_TYPE_TO_FILE = {
    ProductType.GHand5: "ghand5.json",
    ProductType.GHandLite1: "ghandlite1.json",
}

_JOINT_NAME_TO_ID = {
    "THUMB_IP": JointId.THUMB_IP,
    "THUMB_MCP": JointId.THUMB_MCP,
    "THUMB_TMC_FE": JointId.THUMB_TMC_FE,
    "THUMB_TMC_AA": JointId.THUMB_TMC_AA,
    "THUMB_TMC_PS": JointId.THUMB_TMC_PS,
    "FF_DIP": JointId.FF_DIP,
    "FF_PIP": JointId.FF_PIP,
    "FF_MCP": JointId.FF_MCP,
    "FF_MCP_AA": JointId.FF_MCP_AA,
    "MF_DIP": JointId.MF_DIP,
    "MF_PIP": JointId.MF_PIP,
    "MF_MCP": JointId.MF_MCP,
    "RF_DIP": JointId.RF_DIP,
    "RF_PIP": JointId.RF_PIP,
    "RF_MCP": JointId.RF_MCP,
    "LF_DIP": JointId.LF_DIP,
    "LF_PIP": JointId.LF_PIP,
    "LF_MCP": JointId.LF_MCP,
}


def _get_config_search_paths() -> list[str]:
    """Return external directories used to override bundled configs."""
    paths: list[str] = []

    env_path = os.environ.get("GHAND_SDK_CONFIG")
    if env_path:
        paths.append(os.path.abspath(os.path.expanduser(env_path)))

    paths.append(os.path.abspath(os.path.join(".", "config")))

    paths.append(
        os.path.join(
            os.path.expanduser("~"),
            ".ghand",
            "config",
        )
    )

    return paths


def _find_external_config_file(file_name: str) -> str | None:
    """Search external override directories for a product config."""
    for search_dir in _get_config_search_paths():
        full_path = os.path.join(search_dir, file_name)
        if os.path.isfile(full_path):
            logger.debug("Found external config: %s", full_path)
            return full_path
    return None


def _load_bundled_config_data(file_name: str) -> dict | None:
    """Load a product config bundled with the ghand package."""
    try:
        resource = files("ghand").joinpath("config", file_name)
        with resource.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to load bundled config '%s': %s", file_name, exc)
        return None


def _parse_joints(
    json_array: list[dict],
) -> tuple[list[JointId], dict[JointId, tuple[float, float]]]:
    """Parse the ``joints`` section of a product config.

    Args:
        json_array: List of joint definition dicts.

    Returns:
        Tuple of (valid_joint_ids, joint_limits_dict).
    """
    valid_joints = []
    joint_limits = {}

    for item in json_array:
        name = item.get("id", "")
        joint_id = _JOINT_NAME_TO_ID.get(name)
        if joint_id is None:
            logger.warning("Unknown joint name in config: %s", name)
            continue

        valid_joints.append(joint_id)

        if "min" in item and "max" in item:
            mn = float(item["min"])
            mx = float(item["max"])
            if mn > mx:
                mn, mx = mx, mn
            joint_limits[joint_id] = (mn, mx)

    return valid_joints, joint_limits


def _parse_tactile_regions(json_array: list[dict]) -> list[TactileRegionConfig]:
    """Parse the ``tactile_regions`` section of a product config.

    Args:
        json_array: List of tactile region definition dicts.

    Returns:
        List of ``TactileRegionConfig`` objects.
    """
    regions = []
    for item in json_array:
        region_id = item.get("id", "")
        count = item.get("count", 0)
        try:
            sensor_id = TactileSensorId[region_id]
        except KeyError:
            logger.warning("Unknown tactile region id in config: %s", region_id)
            continue
        if count > 0:
            regions.append(TactileRegionConfig(id=sensor_id, count=count))
    return regions


def _parse_int_tuple(values) -> tuple[int, ...]:
    """Parse an optional JSON integer list into a tuple."""
    if not values:
        return ()
    result = []
    for value in values:
        try:
            result.append(int(value))
        except (TypeError, ValueError):
            logger.warning("Invalid integer value in config: %s", value)
    return tuple(result)


def _parse_product_config(
    data: dict,
    *,
    product_type: ProductType | None = None,
    source: str = "",
) -> ProductConfig:
    """Convert product config JSON data into ProductConfig."""
    valid_joints, joint_limits = _parse_joints(data.get("joints", []))

    tactile_regions = _parse_tactile_regions(
        data.get("tactile_regions", [])
    )

    config = ProductConfig(
        name=data.get("name", ""),
        model=data.get("model", ""),
        valid_joints=valid_joints,
        joint_limits=joint_limits,
        has_tactile=data.get("has_tactile", False),
        tactile_regions=tactile_regions,
        product_type=product_type,
    )

    if not config.name or not config.valid_joints:
        logger.error(
            "Product config in %s is missing required fields",
            source,
        )
        return ProductConfig()

    logger.info(
        "Loaded product config: %s from %s",
        config.name,
        source,
    )

    return config


def _load_config_from_file(
    file_path: str,
    product_type: ProductType | None = None,
) -> ProductConfig:
    """Load a product configuration from an external JSON file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to parse %s: %s", file_path, exc)
        return ProductConfig()

    return _parse_product_config(
        data,
        product_type=product_type,
        source=file_path,
    )


def load_product_config(product_type: ProductType) -> ProductConfig:
    """Load configuration for the requested product type.

    External configuration overrides bundled defaults.
    """
    file_name = _PRODUCT_TYPE_TO_FILE.get(product_type)

    if not file_name:
        logger.error("Unknown product type: %s", product_type)
        return ProductConfig()

    external_file = _find_external_config_file(file_name)

    if external_file:
        return _load_config_from_file(
            external_file,
            product_type=product_type,
        )

    data = _load_bundled_config_data(file_name)

    if data is None:
        logger.error(
            "Config file '%s' not found",
            file_name,
        )
        return ProductConfig()

    return _parse_product_config(
        data,
        product_type=product_type,
        source=f"ghand/config/{file_name}",
    )


def find_config_by_name(device_name: str) -> ProductConfig | None:
    """Find a product configuration matching a device name.

    External configuration takes priority over bundled defaults.
    """
    if not device_name:
        return None

    normalized_name = device_name.lower()

    # 1. Search external override configs first.
    for search_dir in _get_config_search_paths():
        pattern = os.path.join(search_dir, "*.json")

        for file_path in glob.glob(pattern):
            try:
                with open(
                    file_path,
                    "r",
                    encoding="utf-8",
                ) as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue

            names = [data.get("name", "")]

            if any(
                name.lower() == normalized_name
                for name in names
                if name
            ):
                product_type = next(
                    (
                        candidate
                        for candidate, expected_file
                        in _PRODUCT_TYPE_TO_FILE.items()
                        if os.path.basename(file_path)
                        == expected_file
                    ),
                    None,
                )

                return _parse_product_config(
                    data,
                    product_type=product_type,
                    source=file_path,
                )

    # 2. Search bundled product configs.
    for product_type, file_name in _PRODUCT_TYPE_TO_FILE.items():
        data = _load_bundled_config_data(file_name)

        if data is None:
            continue

        names = [data.get("name", "")]

        if any(
            name.lower() == normalized_name
            for name in names
            if name
        ):
            return _parse_product_config(
                data,
                product_type=product_type,
                source=f"ghand/config/{file_name}",
            )

    logger.warning(
        "No matching product config found for device: %s",
        device_name,
    )

    return None
