from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEMO_SCRIPT = ROOT / "examples" / "extension" / "02.adaptive_grasp_demo.py"


def test_adaptive_grasp_demo_uses_code_defined_config_only():
    source = DEMO_SCRIPT.read_text(encoding="utf-8")

    assert "--config" not in source
    assert "build_demo_runtime_config_from_toml" not in source


def test_adaptive_grasp_demo_does_not_duplicate_logging_configuration():
    source = DEMO_SCRIPT.read_text(encoding="utf-8")

    assert "logging.basicConfig" not in source
