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
    assert profile.phase_closing_torque == 8


def test_non_paper_cup_profiles_use_default_phase_closing_torque():
    for name in ObjectProfileRegistry.list_all():
        if name == "paper_cup":
            continue
        profile = ObjectProfileRegistry.get(name)
        assert profile is not None
        assert profile.phase_closing_torque == 30


def test_default_profiles_define_position_hold_command_params():
    for name in ObjectProfileRegistry.list_all():
        profile = ObjectProfileRegistry.get(name)

        assert profile is not None
        assert isinstance(profile.position_hold_torque, int), name
        assert 0 <= profile.position_hold_torque <= 100
        assert isinstance(profile.position_hold_speed, int), name
        assert 0 <= profile.position_hold_speed <= 100
