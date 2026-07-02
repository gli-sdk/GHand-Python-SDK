import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_sdk_exposes_ghand_and_adaptive_grasp_as_parallel_src_packages():
    assert (ROOT / "src" / "ghand").is_dir()
    assert (ROOT / "src" / "adaptive_grasp").is_dir()

    assert importlib.util.find_spec("ghand") is not None
    assert importlib.util.find_spec("adaptive_grasp") is not None
