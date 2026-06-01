from typing import Literal, Optional
from dataclasses import dataclass


HoldStrategy = Literal["fixed", "adaptive", "slip_triggered", "position"]


@dataclass
class ObjectProfile:
    """物体/材质参数，用于估算抓取力目标和安全力边界。"""

    name: str
    weight_kg: float
    safe_force_min: float # 最小抓取力下限 保障能抓起物品的力（手指法向力的合力）
    safe_force_max: float # 最大抓取力上限 避免物体被抓坏（手指法向力的合力）
    friction_coeff: float # 摩擦系数
    is_fragile: bool 
    material: str
    position_hold_torque: int # 用于保持手指位置的电流，该值越大，提供的法向力越大
    position_hold_speed: int # 用于保持手指位置的角速度，与position_hold_torque一致即可
    phase_closing_torque: int = 30
    
    # 可选描述信息，预留给视觉识别、仿真或策略选择使用。
    color: Optional[list[float]] = None
    size: Optional[list[float]] = None
    pose: Optional[list[float]] = None
    roughness: Optional[float] = None
    shape: Optional[str] = None
    hold_strategy: Optional[HoldStrategy] = None
    


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
        safe_force_min=3.0,
        safe_force_max=15.0,
        friction_coeff=0.5,
        is_fragile=False,
        material="metal",
        hold_strategy="slip_triggered",
        position_hold_torque=30,
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
        hold_strategy="slip_triggered",
        position_hold_torque=15,
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
        hold_strategy="fixed",
        position_hold_torque=15,
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
        hold_strategy="fixed",
        position_hold_torque=10,
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
        hold_strategy="slip_triggered",
        position_hold_torque=15,
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
        hold_strategy="fixed",
        position_hold_torque=5,
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
        hold_strategy="adaptive",
        position_hold_torque=8,
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
        hold_strategy="position",
        phase_closing_torque=10,
        position_hold_torque=20,
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
        hold_strategy="position",
        phase_closing_torque=10,
        position_hold_torque=30,
        position_hold_speed=30,
    ),
    ObjectProfile(
        name = "plastic_cup",
        weight_kg=0.1,
        safe_force_min=3.0,
        safe_force_max=30.0,
        friction_coeff=0.7,
        is_fragile=True,
        material="plastic",
        hold_strategy="position",
        phase_closing_torque=10,
        position_hold_torque=30,
        position_hold_speed=30,
    ),
    ObjectProfile(
        name = "mineral_water_bottle_500ml",
        weight_kg=0.5,
        safe_force_min=10.0,
        safe_force_max=30.0,
        friction_coeff=0.5,
        is_fragile=True,
        material="plastic",
        hold_strategy="position",
        phase_closing_torque=10,
        position_hold_torque=30,
        position_hold_speed=30,
    )
)



def _register_default_profiles() -> None:
    for profile in DEFAULT_OBJECT_PROFILES:
        ObjectProfileRegistry.register(profile)


_register_default_profiles()
