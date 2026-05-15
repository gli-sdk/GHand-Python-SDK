import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


if "collision_sdk" not in sys.modules:
    collision_sdk_stub = types.ModuleType("collision_sdk")

    class CollisionSDK:  # pragma: no cover - test import stub
        pass

    class CollisionCheckResult:  # pragma: no cover - test import stub
        pass

    collision_sdk_stub.CollisionSDK = CollisionSDK
    collision_sdk_stub.CollisionCheckResult = CollisionCheckResult
    sys.modules["collision_sdk"] = collision_sdk_stub
