# Copyright (c) 2026 GLITech
#
# Licensed under the MIT License. See LICENSE in the project root for license information.

"""Product configuration loader — JSON search and parsing."""

import glob
import json
import logging
import os

from .types import (
    GHandError,
    JointId,
    ProductConfig,
    ProductType,
    TactileRegionConfig,
    TactileSensorId,
)

logger = logging.getLogger("ghand.config")


_PRODUCT_TYPE_TO_FILE = {
    ProductType.G5: "xiaoyao_hand.json",
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
    paths.append(os.path.join(home, ".ghand-sdk", "config") + os.sep)

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


def load_product_config(product_type: ProductType) -> ProductConfig:
    """Load the product configuration for the given product type.

    Args:
        product_type: Product type enum value.

    Returns:
        Populated ``ProductConfig`` instance.

    Raises:
        GHandError: If the product type is unknown or the config file is missing.
    """
    if product_type == ProductType.AUTO:
        return ProductConfig()
    file_name = _PRODUCT_TYPE_TO_FILE.get(product_type)
    if not file_name:
        raise GHandError(f"Unknown product type: {product_type}")

    file_path = _find_config_file(file_name)
    if not file_path:
        raise GHandError(f"Config file '{file_name}' not found")

    return _load_config_from_file(file_path)


def _load_config_from_file(file_path: str) -> ProductConfig:
    """Parse a product configuration from disk.

    Args:
        file_path: Absolute path to the JSON config file.

    Returns:
        Parsed ``ProductConfig``.

    Raises:
        GHandError: If the file cannot be read or parsed.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise GHandError(f"Failed to parse {file_path}: {e}") from e

    valid_joints, joint_limits = _parse_joints(data.get("joints", []))
    tactile_regions = _parse_tactile_regions(data.get("tactile_regions", []))

    config = ProductConfig(
        name=data.get("name", ""),
        model=data.get("model", ""),
        valid_joints=valid_joints,
        joint_limits=joint_limits,
        has_tactile=data.get("has_tactile", False),
        tactile_regions=tactile_regions,
    )

    if not config.name or not config.valid_joints:
        raise GHandError(f"Product config in {file_path} is missing required fields")

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

    normalized_device_name = device_name.strip().strip("\x00").lower()

    for search_dir in _get_config_search_paths():
        pattern = os.path.join(search_dir, "*.json")
        for file_path in glob.glob(pattern):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue

            cfg_name = data.get("name", "").strip().strip("\x00").lower()
            cfg_model = data.get("model", "").strip().strip("\x00").lower()

            if normalized_device_name in (cfg_name, cfg_model):
                logger.info("Auto-detected product config: %s -> %s", device_name, file_path)
                return _load_config_from_file(file_path)

    logger.warning("No matching product config found for device: %s", device_name)
    return None
