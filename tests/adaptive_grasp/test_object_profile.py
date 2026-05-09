import pytest

from xiaoyao.adaptive_grasp.object_profile import ObjectProfileRegistry


def test_paper_cup_profile_has_pouring_demo_material_properties():
    profile = ObjectProfileRegistry.get("paper_cup")

    assert profile is not None
    assert profile.weight_kg == pytest.approx(0.01)
    assert profile.safe_force_min == pytest.approx(0.5)
    assert profile.safe_force_max == pytest.approx(4.4)
    assert profile.friction_coeff == pytest.approx(0.8)
    assert profile.is_fragile is True
    assert profile.material == "paper"
