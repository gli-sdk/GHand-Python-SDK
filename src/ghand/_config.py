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

"""Product configuration loader — JSON search and parsing."""

import glob
import json
import logging
import os

from .types import (
    JointId,
    ProductConfig,
    ProductType,
    TactileRegionConfig,
    TactileSensorId,
)

logger = logging.getLogger("ghand.config")


_PRODUCT_TYPE_TO_FILE = {
    ProductType.G5: "xiaoyao_hand.json",
    ProductType.L1: "l1_hand.json",
}

_JOINT_NAME_TO_ID = {
    "THUMB_DIP": JointId.THUMB_DIP,
    "THUMB_PIP": JointId.THUMB_PIP,
    "THUMB_MCP": JointId.THUMB_MCP,
    "THUMB_SWING": JointId.THUMB_SWING,
    "THUMB_ROTATION": JointId.THUMB_ROTATION,
    "FF_DIP": JointId.FF_DIP,
    "FF_PIP": JointId.FF_PIP,
    "FF_MCP": JointId.FF_MCP,
    "FF_SWING": JointId.FF_SWING,
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
    """Return the ordered list of directories to search for product configs."""
    paths = []

    env_path = os.environ.get("GHAND_SDK_CONFIG")
    if env_path:
        paths.append(env_path)

    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.dirname(pkg_dir)
    proj_root = os.path.dirname(src_dir)
    paths.append(os.path.join(proj_root, "config") + os.sep)

    paths.append("." + os.sep + "config" + os.sep)

    home = os.path.expanduser("~")
    paths.append(os.path.join(home, ".ghand", "config") + os.sep)

    return paths


def _find_config_file(file_name: str) -> str | None:
    """Search for ``file_name`` across the configured search paths.

    Args:
        file_name: Name of the JSON config file.

    Returns:
        Absolute path if found, otherwise None.
    """
    for search_dir in _get_config_search_paths():
        full = os.path.join(search_dir, file_name)
        if os.path.isfile(full):
            logger.debug("Found config: %s", full)
            return full
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


def load_product_config(product_type: ProductType) -> ProductConfig:
    """Load the product configuration for the given product type.

    Args:
        product_type: Product type enum value.

    Returns:
        Populated ``ProductConfig``, or empty ``ProductConfig`` on failure (error is logged).
    """
    file_name = _PRODUCT_TYPE_TO_FILE.get(product_type)
    if not file_name:
        logger.error("Unknown product type: %s", product_type)
        return ProductConfig()

    file_path = _find_config_file(file_name)
    if not file_path:
        logger.error("Config file '%s' not found", file_name)
        return ProductConfig()

    return _load_config_from_file(file_path)


def _load_config_from_file(file_path: str) -> ProductConfig:
    """Parse a product configuration from disk.

    Args:
        file_path: Absolute path to the JSON config file.

    Returns:
        Parsed ``ProductConfig``, or empty ``ProductConfig`` on failure (error is logged).
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to parse %s: %s", file_path, e)
        return ProductConfig()

    valid_joints, joint_limits = _parse_joints(data.get("joints", []))
    tactile_regions = _parse_tactile_regions(data.get("tactile_regions", []))

    config = ProductConfig(
        name=data.get("name", ""),
        model=data.get("model", ""),
        aliases=list(data.get("aliases", [])),
        valid_joints=valid_joints,
        joint_limits=joint_limits,
        has_tactile=data.get("has_tactile", False),
        tactile_regions=tactile_regions,
        slave_id=int(data.get("slave_id", 0x31)),
        modbus_profile=data.get("modbus_profile", "g5"),
        ethercat_input_sizes=_parse_int_tuple(data.get("ethercat_input_sizes", [])),
        ethercat_output_size=(
            int(data["ethercat_output_size"])
            if data.get("ethercat_output_size") is not None
            else None
        ),
        ethercat_rpdo_layout=data.get("ethercat_rpdo_layout", "shared_mode_float"),
        ethercat_tpdo_layout=data.get("ethercat_tpdo_layout", "default"),
    )

    if not config.name or not config.valid_joints:
        logger.error("Product config in %s is missing required fields", file_path)
        return ProductConfig()

    logger.info("Loaded product config: %s from %s", config.name, file_path)
    return config


def find_config_by_name(device_name: str) -> ProductConfig | None:
    """Search all config paths for a product matching the given device name.

    Args:
        device_name: Name string read from the device.

    Returns:
        Matching ``ProductConfig`` if found, otherwise None.
    """
    if not device_name:
        return None

    for search_dir in _get_config_search_paths():
        pattern = os.path.join(search_dir, "*.json")
        for file_path in glob.glob(pattern):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue

            names = [data.get("name", ""), *data.get("aliases", [])]
            if any(name.lower() == device_name.lower() for name in names if name):
                logger.info("Auto-detected product config: %s -> %s", device_name, file_path)
                return _load_config_from_file(file_path)

    logger.warning("No matching product config found for device: %s", device_name)
    return None
