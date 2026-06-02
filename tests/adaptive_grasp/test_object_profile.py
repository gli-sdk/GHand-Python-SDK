import pytest

from adaptive_grasp.object_profile import DEFAULT_OBJECT_PROFILES, ObjectProfileRegistry


def _default_profile(name: str):
    return next(profile for profile in DEFAULT_OBJECT_PROFILES if profile.name == name)


def test_paper_cup_profile_has_pouring_demo_material_properties():
    profile = ObjectProfileRegistry.get("paper_cup")
    expected = _default_profile("paper_cup")

    assert profile is not None
    assert profile.weight_kg == pytest.approx(expected.weight_kg)
    assert profile.safe_force_min == pytest.approx(expected.safe_force_min)
    assert profile.safe_force_max == pytest.approx(expected.safe_force_max)
    assert profile.friction_coeff == pytest.approx(expected.friction_coeff)
    assert profile.is_fragile is expected.is_fragile
    assert profile.material == expected.material
    assert profile.phase_closing_torque == expected.phase_closing_torque


def test_default_profiles_define_phase_closing_torque():
    for name in ObjectProfileRegistry.list_all():
        profile = ObjectProfileRegistry.get(name)
        assert profile is not None
        assert isinstance(profile.phase_closing_torque, int), name
        assert 0 <= profile.phase_closing_torque <= 100


def test_default_profiles_define_position_hold_command_params():
    for name in ObjectProfileRegistry.list_all():
        profile = ObjectProfileRegistry.get(name)

        assert profile is not None
        assert isinstance(profile.position_hold_torque, int), name
        assert 0 <= profile.position_hold_torque <= 100
        assert isinstance(profile.position_hold_speed, int), name
        assert 0 <= profile.position_hold_speed <= 100


def test_registry_exposes_only_list_all_for_names():
    assert not hasattr(ObjectProfileRegistry, "list_names")
