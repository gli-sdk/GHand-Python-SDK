# SPDX-FileCopyrightText: 2025-2026 GLITech
# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass
from typing import Optional


@dataclass
class ObjectProfile:
    """Object/material parameters for adaptive grasp planning."""

    name: str
    weight_kg: float
    safe_force_min: float
    safe_force_max: float
    friction_coeff: float
    is_fragile: bool
    material: str
    position_hold_current: int
    position_hold_speed: int
    phase_closing_current: int = 30
    stiff_position_hold_speed: Optional[int] = None
    stiff_position_hold_current: Optional[int] = None
    stiff_position_hold_target_force: Optional[float] = None

    # Optional metadata reserved for perception, simulation, and strategy selection.
    color: Optional[list[float]] = None
    size: Optional[list[float]] = None
    pose: Optional[list[float]] = None
    roughness: Optional[float] = None
    shape: Optional[str] = None


DEFAULT_OBJECT_PROFILES: tuple[ObjectProfile, ...] = (
    ObjectProfile(
        name="metal",
        weight_kg=0.1,
        safe_force_min=3.0,
        safe_force_max=15.0,
        friction_coeff=0.5,
        is_fragile=False,
        material="metal",
        position_hold_current=30,
        position_hold_speed=30,
    ),
    ObjectProfile(
        name="plastic",
        weight_kg=0.01,
        safe_force_min=1.0,
        safe_force_max=9.0,
        friction_coeff=0.9,
        is_fragile=False,
        material="plastic",
        position_hold_current=15,
        position_hold_speed=15,
    ),
    ObjectProfile(
        name="glass",
        weight_kg=0.05,
        safe_force_min=3.0,
        safe_force_max=9.0,
        friction_coeff=0.5,
        is_fragile=True,
        material="glass",
        position_hold_current=15,
        position_hold_speed=15,
    ),
    ObjectProfile(
        name="tofu",
        weight_kg=0.05,
        safe_force_min=0.5,
        safe_force_max=3.0,
        friction_coeff=0.9,
        is_fragile=True,
        material="tofu",
        position_hold_current=10,
        position_hold_speed=30,
    ),
    ObjectProfile(
        name="fruit",
        weight_kg=0.15,
        safe_force_min=3,
        safe_force_max=10.0,
        friction_coeff=0.8,
        is_fragile=True,
        material="fruit",
        position_hold_current=15,
        position_hold_speed=15,
    ),
    ObjectProfile(
        name="egg",
        weight_kg=0.05,
        safe_force_min=0.2,
        safe_force_max=1.0,
        friction_coeff=0.9,
        is_fragile=True,
        material="egg",
        position_hold_current=5,
        position_hold_speed=20,
    ),
    ObjectProfile(
        name="balloon",
        weight_kg=0.005,
        safe_force_min=0.4,
        safe_force_max=0.6,
        friction_coeff=0.8,
        is_fragile=True,
        material="latex",
        position_hold_current=8,
        position_hold_speed=8,
    ),
    ObjectProfile(
        name="paper_cup",
        weight_kg=0.01,
        safe_force_min=1.0,
        safe_force_max=15.0,
        friction_coeff=0.8,
        is_fragile=True,
        material="paper",
        phase_closing_current=10,
        position_hold_current=20,
        position_hold_speed=20,
    ),
    ObjectProfile(
        name="default",
        weight_kg=0.1,
        safe_force_min=3.0,
        safe_force_max=9.0,
        friction_coeff=0.9,
        is_fragile=False,
        material="default",
        phase_closing_current=10,
        position_hold_current=30,
        position_hold_speed=30,
    ),
    ObjectProfile(
        name="plastic_cup",
        weight_kg=0.1,
        safe_force_min=3.0,
        safe_force_max=30.0,
        friction_coeff=0.7,
        is_fragile=True,
        material="plastic",
        phase_closing_current=10,
        position_hold_current=30,
        position_hold_speed=30,
    ),
    ObjectProfile(
        name="mineral_water_bottle_500ml",
        weight_kg=0.5,
        safe_force_min=10.0,
        safe_force_max=30.0,
        friction_coeff=0.5,
        is_fragile=True,
        material="plastic",
        phase_closing_current=10,
        position_hold_current=30,
        position_hold_speed=30,
    ),
    ObjectProfile(
        name="cylinder_piece",
        weight_kg=0.2,
        safe_force_min=15.0,
        safe_force_max=30.0,
        friction_coeff=0.5,
        is_fragile=False,
        material="metal",
        phase_closing_current=10,
        position_hold_current=90,
        position_hold_speed=90,
        stiff_position_hold_speed=90,
        stiff_position_hold_current=90,
        stiff_position_hold_target_force=15.0,
    ),
)

OBJECT_PROFILES: dict[str, ObjectProfile] = {
    profile.name: profile for profile in DEFAULT_OBJECT_PROFILES
}


def get_object_profile(name: str) -> Optional[ObjectProfile]:
    return OBJECT_PROFILES.get(name)


def list_object_profiles() -> list[str]:
    return list(OBJECT_PROFILES)
