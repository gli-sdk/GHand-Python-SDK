from dataclasses import dataclass
from email.mime import base
from turtle import position
from typing import Literal, Optional


HoldStrategy = Literal["fixed", "adaptive", "slip_triggered"]


@dataclass
class ObjectProfile:
    """物体/材质参数，用于估算抓取力目标和安全力边界。"""

    name: str
    weight_kg: float
    safe_force_min: float
    safe_force_max: float
    friction_coeff: float
    is_fragile: bool
    material: str

    # 可选描述信息，预留给视觉识别、仿真或策略选择使用。
    color: Optional[list[float]] = None
    size: Optional[list[float]] = None
    pose: Optional[list[float]] = None
    roughness: Optional[float] = None
    shape: Optional[str] = None
    hold_strategy: Optional[HoldStrategy] = None
    base_hold_torque: Optional[int] = None
    position_hold_torque: Optional[int] = None
    position_hold_speed: Optional[int] = None


class ObjectProfileRegistry:
    """简单的物体/材质参数注册表。"""

    _profiles: dict[str, ObjectProfile] = {}

    @classmethod
    def register(cls, profile: ObjectProfile) -> None:
        cls._profiles[profile.name] = profile

    @classmethod
    def get(cls, name: str) -> Optional[ObjectProfile]:
        return cls._profiles.get(name)

    @classmethod
    def list_all(cls) -> list[str]:
        return list(cls._profiles.keys())

    @classmethod
    def list_names(cls) -> list[str]:
        return cls.list_all()


DEFAULT_OBJECT_PROFILES: tuple[ObjectProfile, ...] = (
    ObjectProfile(
        name="metal",
        weight_kg=0.1,
        safe_force_min=2.0,
        safe_force_max=15.0,
        friction_coeff=0.9,
        is_fragile=False,
        material="metal",
        hold_strategy="slip_triggered",
        base_hold_torque=20,
    ),
    ObjectProfile(
        name="plastic",
        weight_kg=0.01,
        safe_force_min=0.5,
        safe_force_max=5.0,
        friction_coeff=0.9,
        is_fragile=False,
        material="plastic",
        hold_strategy="slip_triggered",
        base_hold_torque=20,
        position_hold_torque=30,
        position_hold_speed =30,
    ),
    ObjectProfile(
        name="glass",
        weight_kg=0.1,
        safe_force_min=0.5,
        safe_force_max=8.0,
        friction_coeff=0.5,
        is_fragile=True,
        material="glass",
        hold_strategy="fixed",
        base_hold_torque=20,
        position_hold_torque=30,
        position_hold_speed =30,
    ),
    ObjectProfile(
        name="tofu",
        weight_kg=0.05,
        safe_force_min=0.5,
        safe_force_max=3.0,
        friction_coeff=0.9,
        is_fragile=True,
        material="tofu",
        hold_strategy="fixed",
        base_hold_torque=10,
    ),
    ObjectProfile(
        name="fruit",
        weight_kg=0.0,
        safe_force_min=0.5,
        safe_force_max=4.0,
        friction_coeff=0.8,
        is_fragile=True,
        material="fruit",
        hold_strategy="slip_triggered",
    ),
    ObjectProfile(
        name="egg",
        weight_kg=0.05,
        safe_force_min=0.2,
        safe_force_max=1.0,
        friction_coeff=0.9,
        is_fragile=True,
        material="egg",
        hold_strategy="fixed",
    ),
    ObjectProfile(
        name="balloon",
        weight_kg=0.005,
        safe_force_min=0.2,
        safe_force_max=0.3,
        friction_coeff=0.8,
        is_fragile=True,
        material="latex",
        hold_strategy="adaptive",
        base_hold_torque=10,
        position_hold_torque=10,
        position_hold_speed =30,
    ),
    ObjectProfile(
        name="paper_cup",
        weight_kg=0.01,
        safe_force_min=0.5,
        safe_force_max=4.4,
        friction_coeff=0.8,
        is_fragile=True,
        material="paper",
        hold_strategy="adaptive",
        base_hold_torque=5,
        position_hold_torque=5,
        position_hold_speed =5,
    )
)


def _register_default_profiles() -> None:
    for profile in DEFAULT_OBJECT_PROFILES:
        ObjectProfileRegistry.register(profile)


_register_default_profiles()
