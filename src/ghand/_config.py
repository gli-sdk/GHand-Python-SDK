"""产品配置加载器 — JSON 搜索、解析"""
import json
import logging
import os

from .types import JointId, ProductType, TactileRegionConfig, ProductConfig, GHandError

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


def _find_config_file(filename: str) -> str | None:
    for search_dir in _get_config_search_paths():
        full = os.path.join(search_dir, filename)
        if os.path.isfile(full):
            logger.debug("Found config: %s", full)
            return full
    return None


def _parse_joints(json_array: list) -> tuple[list[JointId], dict[JointId, tuple[float, float]]]:
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


def _parse_tactile_regions(json_array: list) -> list[TactileRegionConfig]:
    regions = []
    for item in json_array:
        name = item.get("name", "")
        count = item.get("count", 0)
        if name and count > 0:
            regions.append(TactileRegionConfig(name=name, count=count))
    return regions


def load_product_config(product_type: ProductType) -> ProductConfig:
    filename = _PRODUCT_TYPE_TO_FILE.get(product_type)
    if not filename:
        raise GHandError(f"Unknown product type: {product_type}")

    filepath = _find_config_file(filename)
    if not filepath:
        raise GHandError(f"Config file '{filename}' not found")

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise GHandError(f"Failed to parse {filepath}: {e}") from e

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
        raise GHandError(f"Product config in {filepath} is missing required fields")

    logger.info("Loaded product config: %s from %s", config.name, filepath)
    return config
