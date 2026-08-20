from ._core import (
    CollisionCheckResult,
    CollisionClient,
)

# Collision detection is an internal GHand SDK capability and is versioned with
# the containing SDK package.
__version__ = '2.2.0'

__all__ = [
    'CollisionCheckResult',
    'CollisionClient',
]
