from __future__ import annotations

import math
from typing import NamedTuple, Sequence


PI = math.pi
_EPS = 1e-12

# Joint order for the 18-value collision-detection angle vector.
JOINT_ORDER = (
    'LF-MCP', 'LF-PIP', 'LF-DIP',
    'RF-MCP', 'RF-PIP', 'RF-DIP',
    'MF-MCP', 'MF-PIP', 'MF-DIP',
    'IF-Swing', 'IF-MCP', 'IF-PIP', 'IF-DIP',
    'TH-Rotation', 'TH-Swing', 'TH-MCP', 'TH-PIP', 'TH-DIP',
)

# Mapping from each finger to its PIP and DIP indices in JOINT_ORDER.
PASSIVE_DIP_INDEX_MAP = {
    'LF': (1, 2),   # little finger
    'RF': (4, 5),   # ring finger
    'MF': (7, 8),   # middle finger
    'IF': (11, 12), # index finger
    'TH': (16, 17), # thumb
}


class _Point2D(NamedTuple):
    """Two-dimensional point used in geometric calculations."""
    x: float
    y: float


class _FourBarCache(NamedTuple):
    """Precomputed four-bar linkage cache to avoid repeated work."""
    l_de: float          # DE link length
    l_dg: float          # DG link length
    l_ef: float          # EF link length
    l_fg: float          # FG link length
    phi_pip_0: float     # PIP angle offset at the reference pose
    angle_efg_0: float   # EFG angle at the reference pose
    d_branch_sign: float # Branch-selection sign for point D
    g_branch_sign: float # Branch-selection sign for point G


class _ThumbCache(NamedTuple):
    """Precomputed thumb-mechanism cache to avoid repeated work."""
    l_ac: float          # AC link length
    l_ab: float          # AB link length
    l_db: float          # DB link length
    l_cd: float          # CD link length
    theta_ca_0: float    # CA vector angle at the reference pose
    theta_cd: float      # Fixed CD vector angle
    angle_cab_0: float   # CAB angle at the reference pose
    b_branch_sign: float # Branch-selection sign for point B
    p_c: _Point2D        # Fixed point C
    p_d: _Point2D        # Fixed point D


GEO_STD = {
    'P_F': _Point2D(-2.1, 5.0),
    'P_G': _Point2D(0.5, 0.0),
    'P_E': _Point2D(20.9, 0.0),
    'P_D': _Point2D(23.1, 4.0),
    'P_C': _Point2D(19.9, 7.8),
    'P_A': _Point2D(58.5, 10.3),
    'P_B': _Point2D(50.4, 5.1),
}

GEO_LITTLE = {
    'P_F': _Point2D(11.5, 5.0),
    'P_G': _Point2D(13.7, 0.0),
    'P_E': _Point2D(29.5, 0.0),
    'P_D': _Point2D(31.4, 4.0),
    'P_C': _Point2D(28.0, 7.7),
    'P_A': _Point2D(58.5, 10.3),
    'P_B': _Point2D(49.1, 7.0),
}

GEO_THUMB = {
    'P_A': _Point2D(35.0451, 5.0),
    'P_B': _Point2D(32.1033, 0.0245),
    'P_C': _Point2D(0.0, 0.0),
    'P_D': _Point2D(0.0, 6.7),
}


def _dist(p1: _Point2D, p2: _Point2D) -> float:
    return math.hypot(p1.x - p2.x, p1.y - p2.y)


def _sub(p1: _Point2D, p2: _Point2D) -> _Point2D:
    return _Point2D(p1.x - p2.x, p1.y - p2.y)


def _cross(v1: _Point2D, v2: _Point2D) -> float:
    return v1.x * v2.y - v1.y * v2.x


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def _solve_triangle_angle(side_a: float, side_b: float, side_c_opposite: float) -> float:
    if side_a <= _EPS or side_b <= _EPS:
        return 0.0
    cos_value = (side_a * side_a + side_b * side_b - side_c_opposite * side_c_opposite) / (2.0 * side_a * side_b)
    return math.acos(_clamp(cos_value, -1.0, 1.0))


def _is_triangle_feasible(side_a: float, side_b: float, side_c: float) -> bool:
    return abs(side_a - side_b) <= side_c <= side_a + side_b


def _normalize_angle(angle_rad: float) -> float:
    return (angle_rad + PI) % (2.0 * PI) - PI


def _rotate_to_local(point: _Point2D, origin: _Point2D, angle_rad: float) -> _Point2D:
    dx = point.x - origin.x
    dy = point.y - origin.y
    cos_angle = math.cos(angle_rad)
    sin_angle = math.sin(angle_rad)
    return _Point2D(
        x=dx * cos_angle - dy * sin_angle,
        y=dx * sin_angle + dy * cos_angle,
    )


def _sign_or_default(value: float, default: float) -> float:
    if abs(value) <= _EPS:
        return default
    return 1.0 if value > 0.0 else -1.0


def _solve_circle_intersections(
    center0: _Point2D,
    radius0: float,
    center1: _Point2D,
    radius1: float,
) -> tuple[_Point2D, _Point2D]:
    """
    Compute the intersection points of two circles in 2D.

    Args:
        center0: Center of the first circle.
        radius0: Radius of the first circle, must be positive.
        center1: Center of the second circle.
        radius1: Radius of the second circle, must be positive.

    Returns:
        tuple[_Point2D, _Point2D]:
            Two intersection points. The first point is offset in the
            positive perpendicular direction of the center-to-center axis,
            and the second point is offset in the negative direction.

    Raises:
        ValueError: Raised when the centers overlap or the circles do not
            produce valid intersection points.
    """
    center_distance = _dist(center0, center1)
    if center_distance <= _EPS:
        raise ValueError('circle centers overlap; intersection points are not uniquely defined')
    if not _is_triangle_feasible(radius0, radius1, center_distance):
        raise ValueError('circles do not have valid intersection points')

    axis_x = (radius0 * radius0 - radius1 * radius1 + center_distance * center_distance) / (2.0 * center_distance)
    height_sq = max(0.0, radius0 * radius0 - axis_x * axis_x)
    height = math.sqrt(height_sq)

    unit_x = (center1.x - center0.x) / center_distance
    unit_y = (center1.y - center0.y) / center_distance

    mid_x = center0.x + axis_x * unit_x
    mid_y = center0.y + axis_x * unit_y
    offset_x = -height * unit_y
    offset_y = height * unit_x

    return (
        _Point2D(mid_x + offset_x, mid_y + offset_y),
        _Point2D(mid_x - offset_x, mid_y - offset_y),
    )


def _select_point_by_y_sign(point0: _Point2D, point1: _Point2D, expected_sign: float) -> _Point2D:
    sign0 = _sign_or_default(point0.y, expected_sign)
    sign1 = _sign_or_default(point1.y, expected_sign)
    if sign0 == expected_sign and sign1 != expected_sign:
        return point0
    if sign1 == expected_sign and sign0 != expected_sign:
        return point1
    return point0 if abs(point0.y) <= abs(point1.y) else point1


def _select_point_by_cross_sign(
    origin: _Point2D,
    axis_end: _Point2D,
    point0: _Point2D,
    point1: _Point2D,
    expected_sign: float,
) -> _Point2D:
    axis = _sub(axis_end, origin)
    sign0 = _sign_or_default(_cross(axis, _sub(point0, origin)), expected_sign)
    sign1 = _sign_or_default(_cross(axis, _sub(point1, origin)), expected_sign)
    if sign0 == expected_sign and sign1 != expected_sign:
        return point0
    if sign1 == expected_sign and sign0 != expected_sign:
        return point1
    return point0


def _precompute_fourbar_cache(geo: dict[str, _Point2D]) -> _FourBarCache:
    l_de = _dist(geo['P_D'], geo['P_E'])
    l_dg = _dist(geo['P_D'], geo['P_G'])
    l_ef = _dist(geo['P_E'], geo['P_F'])
    l_fg = _dist(geo['P_F'], geo['P_G'])

    angle_deg_0 = _solve_triangle_angle(l_de, _dist(geo['P_E'], geo['P_G']), l_dg)
    angle_feg_0 = _solve_triangle_angle(l_ef, _dist(geo['P_E'], geo['P_G']), l_fg)
    phi_pip_0 = angle_deg_0 - angle_feg_0
    angle_efg_0 = _solve_triangle_angle(l_ef, l_fg, _dist(geo['P_E'], geo['P_G']))

    ef_angle = -math.atan2(geo['P_F'].y - geo['P_E'].y, geo['P_F'].x - geo['P_E'].x)
    d_local = _rotate_to_local(geo['P_D'], geo['P_E'], ef_angle)
    g_local = _rotate_to_local(geo['P_G'], geo['P_E'], ef_angle)
    d_branch_sign = _sign_or_default(d_local.y, -1.0)
    g_branch_sign = _sign_or_default(g_local.y, -1.0)

    return _FourBarCache(
        l_de=l_de,
        l_dg=l_dg,
        l_ef=l_ef,
        l_fg=l_fg,
        phi_pip_0=phi_pip_0,
        angle_efg_0=angle_efg_0,
        d_branch_sign=d_branch_sign,
        g_branch_sign=g_branch_sign,
    )


def _precompute_thumb_cache(geo: dict[str, _Point2D]) -> _ThumbCache:
    l_ac = _dist(geo['P_A'], geo['P_C'])
    l_ab = _dist(geo['P_A'], geo['P_B'])
    l_db = _dist(geo['P_D'], geo['P_B'])
    l_cd = _dist(geo['P_C'], geo['P_D'])
    theta_ca_0 = math.atan2(geo['P_A'].y - geo['P_C'].y, geo['P_A'].x - geo['P_C'].x)
    theta_cd = math.atan2(geo['P_D'].y - geo['P_C'].y, geo['P_D'].x - geo['P_C'].x)
    angle_cab_0 = _solve_triangle_angle(l_ac, l_ab, _dist(geo['P_C'], geo['P_B']))
    b_branch_sign = _sign_or_default(_cross(_sub(geo['P_D'], geo['P_A']), _sub(geo['P_B'], geo['P_A'])), -1.0)

    return _ThumbCache(
        l_ac=l_ac,
        l_ab=l_ab,
        l_db=l_db,
        l_cd=l_cd,
        theta_ca_0=theta_ca_0,
        theta_cd=theta_cd,
        angle_cab_0=angle_cab_0,
        b_branch_sign=b_branch_sign,
        p_c=geo['P_C'],
        p_d=geo['P_D'],
    )


def _solve_fourbar_dip_from_pip(cache: _FourBarCache, pip_rad: float) -> float:
    phi_curr = cache.phi_pip_0 - pip_rad
    point_e = _Point2D(0.0, 0.0)
    point_f = _Point2D(cache.l_ef, 0.0)
    point_d = _Point2D(cache.l_de * math.cos(phi_curr), cache.d_branch_sign * cache.l_de * math.sin(phi_curr))

    point_g0, point_g1 = _solve_circle_intersections(point_d, cache.l_dg, point_f, cache.l_fg)
    point_g = _select_point_by_y_sign(point_g0, point_g1, cache.g_branch_sign)

    l_ge = _dist(point_e, point_g)
    angle_efg = _solve_triangle_angle(cache.l_ef, cache.l_fg, l_ge)
    return angle_efg - cache.angle_efg_0


def _solve_thumb_dip_from_pip(cache: _ThumbCache, pip_rad: float) -> float:
    theta_ca = cache.theta_ca_0 + pip_rad
    point_a = _Point2D(
        cache.p_c.x + cache.l_ac * math.cos(theta_ca),
        cache.p_c.y + cache.l_ac * math.sin(theta_ca),
    )

    point_b0, point_b1 = _solve_circle_intersections(point_a, cache.l_ab, cache.p_d, cache.l_db)
    point_b = _select_point_by_cross_sign(point_a, cache.p_d, point_b0, point_b1, cache.b_branch_sign)

    l_cb = _dist(cache.p_c, point_b)
    angle_cab = _solve_triangle_angle(cache.l_ac, cache.l_ab, l_cb)
    return angle_cab - cache.angle_cab_0


def _fourbar_pip_range(cache: _FourBarCache) -> tuple[float, float]:
    df_min = max(abs(cache.l_de - cache.l_ef), abs(cache.l_dg - cache.l_fg))
    df_max = min(cache.l_de + cache.l_ef, cache.l_dg + cache.l_fg)
    phi_min = _solve_triangle_angle(cache.l_de, cache.l_ef, df_min)
    phi_max = _solve_triangle_angle(cache.l_de, cache.l_ef, df_max)
    pip_min = cache.phi_pip_0 - phi_max
    pip_max = cache.phi_pip_0 - phi_min
    return min(pip_min, pip_max), max(pip_min, pip_max)


def _thumb_pip_range(cache: _ThumbCache) -> tuple[float, float]:
    ad_min = max(abs(cache.l_ab - cache.l_db), abs(cache.l_ac - cache.l_cd))
    ad_max = min(cache.l_ab + cache.l_db, cache.l_ac + cache.l_cd)
    delta_min = _solve_triangle_angle(cache.l_ac, cache.l_cd, ad_min)
    delta_max = _solve_triangle_angle(cache.l_ac, cache.l_cd, ad_max)

    reference_delta = _normalize_angle(cache.theta_ca_0 - cache.theta_cd)
    branch_sign = _sign_or_default(reference_delta, -1.0)
    theta_start = cache.theta_cd + branch_sign * delta_max
    theta_end = cache.theta_cd + branch_sign * delta_min
    pip_min = theta_start - cache.theta_ca_0
    pip_max = theta_end - cache.theta_ca_0
    return min(pip_min, pip_max), max(pip_min, pip_max)


def _validate_pip_range(pip_rad: float, mechanism_name: str, pip_range: tuple[float, float]) -> None:
    if not math.isfinite(pip_rad):
        raise ValueError('PIP angle must be finite')
    if pip_rad < pip_range[0] - _EPS or pip_rad > pip_range[1] + _EPS:
        raise ValueError(
            f'{mechanism_name} PIP angle is out of the supported mapping range: {pip_rad:.6f}, '
            f'expected [{pip_range[0]:.6f}, {pip_range[1]:.6f}]'
        )


def _normalize_finger_identifier(finger: str) -> str:
    if not isinstance(finger, str):
        raise ValueError('finger must be a string')

    normalized_finger = finger.upper()
    if normalized_finger not in _FINGER_RANGE_MAP:
        raise ValueError(f'unsupported finger identifier: {finger}')

    return normalized_finger


_STD_CACHE = _precompute_fourbar_cache(GEO_STD)
_LITTLE_CACHE = _precompute_fourbar_cache(GEO_LITTLE)
_THUMB_CACHE = _precompute_thumb_cache(GEO_THUMB)

_STD_PIP_RANGE = _fourbar_pip_range(_STD_CACHE)
_LITTLE_PIP_RANGE = _fourbar_pip_range(_LITTLE_CACHE)
_THUMB_PIP_RANGE = _thumb_pip_range(_THUMB_CACHE)

_FINGER_RANGE_MAP = {
    'IF': _STD_PIP_RANGE,
    'MF': _STD_PIP_RANGE,
    'RF': _STD_PIP_RANGE,
    'LF': _LITTLE_PIP_RANGE,
    'TH': _THUMB_PIP_RANGE,
}


def get_supported_pip_range(finger: str) -> tuple[float, float]:
    """
    Return the supported PIP angle range for a given finger.

    Args:
        finger: Finger identifier (LF/RF/MF/IF/TH).

    Returns:
        tuple[float, float]: Supported PIP angle range in radians.
    """
    normalized_finger = _normalize_finger_identifier(finger)
    return _FINGER_RANGE_MAP[normalized_finger]


def solve_std_finger_dip_from_pip(pip_rad: float) -> float:
    """
    Compute the DIP angle for a standard finger (index/middle/ring).

    Args:
        pip_rad: PIP joint angle in radians.

    Returns:
        DIP joint angle in radians.
    """
    _validate_pip_range(pip_rad, 'standard finger', _STD_PIP_RANGE)
    return _solve_fourbar_dip_from_pip(_STD_CACHE, pip_rad)


def solve_little_finger_dip_from_pip(pip_rad: float) -> float:
    """
    Compute the DIP angle for the little finger.

    Args:
        pip_rad: PIP joint angle in radians.

    Returns:
        DIP joint angle in radians.
    """
    _validate_pip_range(pip_rad, 'little finger', _LITTLE_PIP_RANGE)
    return _solve_fourbar_dip_from_pip(_LITTLE_CACHE, pip_rad)


def solve_thumb_dip_from_pip(pip_rad: float) -> float:
    """
    Compute the DIP angle for the thumb.

    Note:
        In the collision-detection convention, the thumb IP joint is
        represented as TH-PIP.

    Args:
        pip_rad: PIP joint angle in radians.

    Returns:
        DIP joint angle in radians.
    """
    _validate_pip_range(pip_rad, 'thumb', _THUMB_PIP_RANGE)
    return _solve_thumb_dip_from_pip(_THUMB_CACHE, pip_rad)


def solve_finger_dip_from_pip(pip_rad: float, finger: str) -> float:
    """
    Compute the DIP angle for a finger from its PIP angle.

    Args:
        pip_rad: PIP joint angle in radians.
        finger: Finger identifier (LF/RF/MF/IF/TH).

    Returns:
        DIP joint angle in radians.
    """
    normalized_finger = _normalize_finger_identifier(finger)
    if normalized_finger == 'LF':
        return solve_little_finger_dip_from_pip(pip_rad)
    if normalized_finger == 'TH':
        return solve_thumb_dip_from_pip(pip_rad)
    if normalized_finger in {'IF', 'MF', 'RF'}:
        return solve_std_finger_dip_from_pip(pip_rad)
    raise ValueError(f'unsupported finger identifier: {finger}')


def apply_passive_dip_mapping(angles: Sequence[float]) -> list[float]:
    """
    Apply passive DIP mapping to a full 18-value joint-angle vector.

    The DIP entries are overwritten using the corresponding PIP angles for
    each finger.

    Args:
        angles: 18-value joint-angle sequence ordered by JOINT_ORDER.

    Returns:
        list[float]: Mapped 18-value joint-angle vector with updated DIP values.
    """
    if isinstance(angles, (str, bytes)):
        raise ValueError('angles must be a numeric sequence, not a string or bytes')

    try:
        mapped_angles = [float(value) for value in angles]
    except TypeError as exc:
        raise ValueError('angles must be an iterable numeric sequence') from exc
    except ValueError as exc:
        raise ValueError('angles contains a value that cannot be converted to float') from exc

    if len(mapped_angles) != len(JOINT_ORDER):
        raise ValueError(f'angles length must be {len(JOINT_ORDER)}, got {len(mapped_angles)}')

    for finger, (pip_index, dip_index) in PASSIVE_DIP_INDEX_MAP.items():
        mapped_angles[dip_index] = solve_finger_dip_from_pip(mapped_angles[pip_index], finger)
    return mapped_angles


__all__ = [
    'JOINT_ORDER',
    'PASSIVE_DIP_INDEX_MAP',
    'get_supported_pip_range',
    'solve_std_finger_dip_from_pip',
    'solve_little_finger_dip_from_pip',
    'solve_thumb_dip_from_pip',
    'solve_finger_dip_from_pip',
    'apply_passive_dip_mapping',
]

