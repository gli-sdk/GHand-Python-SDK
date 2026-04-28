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
    def list_all(cls) -> list[str]:
        return list(cls._profiles.keys())

    @classmethod
    def list_names(cls) -> list[str]:
        return cls.list_all()




# 注册默认材质（以 ObjectProfile 形式存储，weight_kg=0 表示纯材质模板）
ObjectProfileRegistry.register(
    ObjectProfile(name="metal", weight_kg=0.1, material="metal", safe_force_min=2.0, safe_force_max=15.0, friction_coeff=0.9, is_fragile=False)
)
ObjectProfileRegistry.register(
    ObjectProfile(name="plastic", weight_kg=0.01, material="plastic", safe_force_min=0.5, safe_force_max=5.0, friction_coeff=0.9, is_fragile=False)
)
ObjectProfileRegistry.register(
    ObjectProfile(name="glass", weight_kg=0.1, material="glass", safe_force_min=0.5, safe_force_max=8.0, friction_coeff=0.5, is_fragile=True)
)
ObjectProfileRegistry.register(
    ObjectProfile(name="tofu", weight_kg=0.05, material="tofu", safe_force_min=0.5, safe_force_max=3.0, friction_coeff=0.9, is_fragile=True)
)
ObjectProfileRegistry.register(
    ObjectProfile(name="fruit", weight_kg=0.0, material="fruit", safe_force_min=0.5, safe_force_max=4.0, friction_coeff=0.8, is_fragile=True)
)
ObjectProfileRegistry.register(
    ObjectProfile(name="egg", weight_kg=0.05, material="egg", safe_force_min=0.2, safe_force_max=1.0, friction_coeff=0.9, is_fragile=True)
)

ObjectProfileRegistry.register(
    ObjectProfile(
        name="balloon",
        weight_kg=0.005,        # 典型乳胶气球约 5g
        material="latex",
        safe_force_min=0.1,     # 克服滑移所需最小力（见下方计算）
        safe_force_max=0.3,     # 乳胶气球爆裂临界力约 0.2~0.4N，保守取 0.3N
        friction_coeff=0.8,     # 乳胶对硅胶/橡胶手指，干燥时摩擦系数
        is_fragile=True,
    )
)
