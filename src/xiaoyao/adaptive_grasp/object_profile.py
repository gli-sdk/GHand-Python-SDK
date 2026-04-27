from dataclasses import dataclass
from typing import Optional


@dataclass
class ObjectProfile:
    """抓取物品的材质库，包含物品的基本属性
    
    
    """
    name: str
    weight_kg: float
    material: str
    safe_force_min: float
    safe_force_max: float
    friction_coeff: float
    is_fragile: bool


class ObjectProfileRegistry:
    _profiles: dict[str, ObjectProfile] = {}

    @classmethod
    def register(cls, profile: ObjectProfile) -> None:
        cls._profiles[profile.name] = profile

    @classmethod
    def get(cls, name: str) -> Optional[ObjectProfile]:
        return cls._profiles.get(name)

    @classmethod
    def list_names(cls) -> list[str]:
        return list(cls._profiles.keys())


ObjectProfileRegistry.register(
    ObjectProfile(
        name="metal_block",
        weight_kg=0.5,
        material="metal",
        safe_force_min=2.0,
        safe_force_max=15.0,
        friction_coeff=0.9,
        is_fragile=False,
    )
)
ObjectProfileRegistry.register(
    ObjectProfile(
        name="plastic_cup",
        weight_kg=0.1,
        material="plastic",
        safe_force_min=0.5,
        safe_force_max=5.0,
        friction_coeff=0.9,
        is_fragile=False,
    )
)
ObjectProfileRegistry.register(
    ObjectProfile(
        name="tofu",
        weight_kg=0.05,
        material="tofu",
        safe_force_min=0.5,
        safe_force_max=2.0,
        friction_coeff=0.9,
        is_fragile=True,
    )
)
ObjectProfileRegistry.register(
    ObjectProfile(
        name="banana",
        weight_kg=0.12,
        material="fruit",
        safe_force_min=0.5,
        safe_force_max=4.0,
        friction_coeff=0.8,
        is_fragile=True,
    )
)
ObjectProfileRegistry.register(
    ObjectProfile(
        name="egg",
        weight_kg=0.07,
        material="egg",
        safe_force_min=0.5,
        safe_force_max=2.0,
        friction_coeff=0.9,
        is_fragile=True,
    )
)
