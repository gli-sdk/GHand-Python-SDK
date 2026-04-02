from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from .datatypes import JointData, Plane, STLData
from .passive_dip_mapping import JOINT_ORDER, apply_passive_dip_mapping
from .transforms import cal_capsule_param, update_joint_transforms

EPS = 1e-8

COLLISION_JOINT_LIST = [
    'TH-MCP', 'TH-PIP', 'TH-DIP',
    'IF-MCP', 'IF-PIP', 'IF-DIP',
    'MF-MCP', 'MF-PIP', 'MF-DIP',
    'RF-MCP', 'RF-PIP', 'RF-DIP',
    'LF-MCP', 'LF-PIP', 'LF-DIP',
]

PLANE_COLLISION_JOINTS = ['TH-DIP', 'IF-DIP', 'MF-DIP', 'RF-DIP', 'LF-DIP']

COLLISION_JOINT_INDEX = {name: idx for idx, name in enumerate(COLLISION_JOINT_LIST)}

ADJACENT_JOINT_PAIRS = [
    ('TH-MCP', 'TH-PIP'),
    ('TH-PIP', 'TH-DIP'),
    ('IF-MCP', 'IF-PIP'),
    ('IF-PIP', 'IF-DIP'),
    ('MF-MCP', 'MF-PIP'),
    ('MF-PIP', 'MF-DIP'),
    ('RF-MCP', 'RF-PIP'),
    ('RF-PIP', 'RF-DIP'),
    ('LF-MCP', 'LF-PIP'),
    ('LF-PIP', 'LF-DIP'),
    ('IF-MCP', 'TH-MCP'),
]

NON_INTERFERENCE_GROUP = [
    'MF-MCP', 'MF-PIP', 'MF-DIP',
    'RF-MCP', 'RF-PIP', 'RF-DIP',
    'LF-MCP', 'LF-PIP', 'LF-DIP',
    'TH-MCP',
]

PLANE_NORMAL = np.array([0.0, -1.17, 0.0])
PLANE_ORIGIN = np.array([0.0, -0.017, 0.05])


def _as_point3(point: np.ndarray) -> np.ndarray:
    return np.asarray(point, dtype=float).reshape(3)


def _validate_horizontal_plane_normal(n: np.ndarray, eps: float = EPS) -> np.ndarray:
    n = np.asarray(n, dtype=float).flatten()
    norm = np.linalg.norm(n)
    if norm < eps:
        raise ValueError('plane normal cannot be zero')

    n_unit = n / norm
    if abs(n_unit[0]) > eps or abs(n_unit[2]) > eps:
        raise ValueError('plane normal must be aligned with the Y axis')

    y_sign = -1.0 if n_unit[1] < 0 else 1.0
    return np.array([0.0, y_sign, 0.0], dtype=float)


def _get_stl_points(stl_item: STLData) -> np.ndarray:
    if stl_item.V_homo is not None:
        return stl_item.V_homo[:3, :].T
    return stl_item.raw_data.points.reshape(-1, 3)


def _get_plane_quad_vertices(plane: Plane) -> np.ndarray:
    y_value = float(plane.p0[1])
    return np.array([
        [plane.aabb_min[0], y_value, plane.aabb_min[2]],
        [plane.aabb_min[0], y_value, plane.aabb_max[2]],
        [plane.aabb_max[0], y_value, plane.aabb_max[2]],
        [plane.aabb_max[0], y_value, plane.aabb_min[2]],
    ])


def _get_collision_pair_indices(adj_matrix: np.ndarray) -> List[Tuple[int, int]]:
    num_joints = len(COLLISION_JOINT_LIST)
    collision_pairs: List[Tuple[int, int]] = []
    for i in range(num_joints):
        for j in range(i + 1, num_joints):
            if adj_matrix[i, j] == 0:
                collision_pairs.append((i, j))
    return collision_pairs


def _extract_collision_args(
    args: Tuple[Any, ...],
    kwargs: Dict[str, Any],
) -> Tuple[Optional[Dict[str, STLData]], Plane, np.ndarray, float]:
    if kwargs:
        stl_data = kwargs.get('stl_data')
        plane = kwargs.get('plane')
        adj_matrix = kwargs.get('adj_matrix')
        safety_margin = kwargs.get('safety_margin')
        if plane is None or adj_matrix is None or safety_margin is None:
            raise TypeError('plane, adj_matrix, and safety_margin are required')
        return stl_data, plane, adj_matrix, float(safety_margin)

    if len(args) == 3:
        plane, adj_matrix, safety_margin = args
        return None, plane, adj_matrix, float(safety_margin)
    if len(args) == 4:
        stl_data, plane, adj_matrix, safety_margin = args
        return stl_data, plane, adj_matrix, float(safety_margin)

    raise TypeError('expected (plane, adj_matrix, safety_margin) or (stl_data, plane, adj_matrix, safety_margin)')


def _normalize_collision_response(response: Tuple[Any, ...]) -> Tuple[bool, List[Any], List[str]]:
    if len(response) == 2:
        has_collision, collision_links = response
        return bool(has_collision), [], list(collision_links)
    if len(response) == 3:
        has_collision, results, collision_links = response
        return bool(has_collision), list(results), list(collision_links)
    raise ValueError('collision response must have length 2 or 3')


def _maybe_apply_passive_dip_mapping(angles: np.ndarray) -> np.ndarray:
    normalized_angles = np.asarray(angles, dtype=float)
    if normalized_angles.shape == (len(JOINT_ORDER),):
        return np.asarray(apply_passive_dip_mapping(normalized_angles), dtype=float)
    return normalized_angles


def _rounded_distance(value: float) -> float:
    return round(float(value), 10)


def gen_adj_matrix() -> np.ndarray:
    joint_pairs = list(ADJACENT_JOINT_PAIRS)

    for i in range(len(NON_INTERFERENCE_GROUP)):
        for j in range(i + 1, len(NON_INTERFERENCE_GROUP)):
            joint_pairs.append((NON_INTERFERENCE_GROUP[i], NON_INTERFERENCE_GROUP[j]))

    adj_matrix = np.zeros((len(COLLISION_JOINT_LIST), len(COLLISION_JOINT_LIST)), dtype=int)
    for joint1, joint2 in joint_pairs:
        idx1 = COLLISION_JOINT_INDEX[joint1]
        idx2 = COLLISION_JOINT_INDEX[joint2]
        adj_matrix[idx1, idx2] = 1
        adj_matrix[idx2, idx1] = 1

    return adj_matrix


def get_plane_from_normal(base_link_stl: STLData, n: np.ndarray = PLANE_NORMAL, p0: np.ndarray = PLANE_ORIGIN) -> Plane:
    n_unit = _validate_horizontal_plane_normal(n)
    p0 = np.asarray(p0, dtype=float).reshape(3)
    d = -float(np.dot(n_unit, p0))

    points = _get_stl_points(base_link_stl)
    aabb_min = np.min(points, axis=0)
    aabb_max = np.max(points, axis=0)

    min_x, min_y, min_z = aabb_min
    max_x, max_y, max_z = aabb_max
    aabb_vertices = np.array([
        [min_x, min_y, min_z],
        [max_x, min_y, min_z],
        [max_x, max_y, min_z],
        [min_x, max_y, min_z],
        [min_x, min_y, max_z],
        [max_x, min_y, max_z],
        [max_x, max_y, max_z],
        [min_x, max_y, max_z],
    ])

    return Plane(
        n=n_unit,
        p0=p0,
        d=d,
        aabb_min=aabb_min,
        aabb_max=aabb_max,
        aabb_vertices=aabb_vertices,
    )


def dist_segment_to_segment(P1: np.ndarray, P2: np.ndarray, Q1: np.ndarray, Q2: np.ndarray) -> float:
    P1 = _as_point3(P1)
    P2 = _as_point3(P2)
    Q1 = _as_point3(Q1)
    Q2 = _as_point3(Q2)

    u = P2 - P1
    v = Q2 - Q1
    w = P1 - Q1

    a = np.dot(u, u)
    b = np.dot(u, v)
    c = np.dot(v, v)
    d_param = np.dot(u, w)
    e = np.dot(v, w)

    denom = a * c - b * b
    s_numer = 0.0
    s_denom = denom
    t_numer = 0.0
    t_denom = denom

    if denom < EPS:
        s_numer = 0.0
        s_denom = 1.0
        t_numer = e
        t_denom = c
    else:
        s_numer = b * e - c * d_param
        t_numer = a * e - b * d_param
        if s_numer < 0.0:
            s_numer = 0.0
            t_numer = e
            t_denom = c
        elif s_numer > s_denom:
            s_numer = s_denom
            t_numer = e + b
            t_denom = c

    if t_numer < 0.0:
        t_numer = 0.0
        if -d_param < 0.0:
            s_numer = 0.0
        elif -d_param > a:
            s_numer = s_denom
        else:
            s_numer = -d_param
            s_denom = a
    elif t_numer > t_denom:
        t_numer = t_denom
        if (-d_param + b) < 0.0:
            s_numer = 0.0
        elif (-d_param + b) > a:
            s_numer = s_denom
        else:
            s_numer = -d_param + b
            s_denom = a

    sc = 0.0 if abs(s_numer) < EPS else s_numer / s_denom
    tc = 0.0 if abs(t_numer) < EPS else t_numer / t_denom

    return float(np.linalg.norm(w + sc * u - tc * v))


def dist_point_to_segment(P: np.ndarray, A: np.ndarray, B: np.ndarray) -> float:
    P = _as_point3(P)
    A = _as_point3(A)
    B = _as_point3(B)

    vec_ab = B - A
    vec_ap = P - A
    denom = np.dot(vec_ab, vec_ab)
    t = 0.0 if denom <= EPS else np.dot(vec_ap, vec_ab) / denom
    t = max(0.0, min(1.0, t))

    nearest = A + t * vec_ab
    return float(np.linalg.norm(P - nearest))


def dist_point_to_triangle(P: np.ndarray, v0: np.ndarray, v1: np.ndarray, v2: np.ndarray) -> float:
    P = _as_point3(P)
    v0 = _as_point3(v0)
    v1 = _as_point3(v1)
    v2 = _as_point3(v2)

    e1 = v1 - v0
    e2 = v2 - v0
    normal = np.cross(e1, e2)
    normal_norm = np.linalg.norm(normal)

    if normal_norm < EPS:
        return min(
            dist_point_to_segment(P, v0, v1),
            dist_point_to_segment(P, v1, v2),
            dist_point_to_segment(P, v2, v0),
        )

    signed_height = np.dot(normal, P - v0) / normal_norm
    projected = P - signed_height * (normal / normal_norm)
    projected_vec = projected - v0

    mat = np.array([
        [np.dot(e1, e1), np.dot(e1, e2)],
        [np.dot(e1, e2), np.dot(e2, e2)],
    ])
    rhs = np.array([np.dot(projected_vec, e1), np.dot(projected_vec, e2)])

    try:
        u, v = np.linalg.solve(mat, rhs)
    except np.linalg.LinAlgError:
        u = v = -1.0

    if u >= -EPS and v >= -EPS and (u + v) <= 1 + EPS:
        return abs(float(signed_height))

    return min(
        dist_point_to_segment(P, v0, v1),
        dist_point_to_segment(P, v0, v2),
        dist_point_to_segment(P, v1, v2),
    )


def dist_segment_to_triangle(
    p1: np.ndarray,
    p2: np.ndarray,
    v0: np.ndarray,
    v1: np.ndarray,
    v2: np.ndarray,
) -> float:
    p1 = _as_point3(p1)
    p2 = _as_point3(p2)
    v0 = _as_point3(v0)
    v1 = _as_point3(v1)
    v2 = _as_point3(v2)

    segment_dir = p2 - p1
    e1 = v1 - v0
    e2 = v2 - v0
    s = p1 - v0
    p = np.cross(segment_dir, e2)
    q = np.cross(s, e1)
    delta = np.dot(segment_dir, np.cross(e1, e2))

    if abs(delta) > EPS:
        t = np.dot(s, np.cross(e1, e2)) / delta
        u = np.dot(s, p) / delta
        v = np.dot(e2, q) / delta

        if 0.0 <= t <= 1.0 and u >= 0.0 and v >= 0.0 and (u + v) <= 1.0:
            return 0.0

    distances = np.array([
        dist_point_to_triangle(p1, v0, v1, v2),
        dist_point_to_triangle(p2, v0, v1, v2),
        dist_point_to_segment(v0, p1, p2),
        dist_point_to_segment(v1, p1, p2),
        dist_point_to_segment(v2, p1, p2),
        dist_segment_to_segment(v0, v1, p1, p2),
        dist_segment_to_segment(v0, v2, p1, p2),
        dist_segment_to_segment(v1, v2, p1, p2),
    ])
    return float(np.min(distances))


def dist_segment_to_plane(plane: Plane, p1: np.ndarray, p2: np.ndarray) -> Tuple[float, bool]:
    n = plane.n
    if abs(n[0]) > EPS or abs(n[2]) > EPS:
        raise ValueError('dist_segment_to_plane requires a horizontal plane')

    p1 = _as_point3(p1)
    p2 = _as_point3(p2)

    d1 = float(np.dot(n, p1) + plane.d)
    d2 = float(np.dot(n, p2) + plane.d)

    p1_on_plane = abs(d1) <= EPS
    p2_on_plane = abs(d2) <= EPS
    segment_crosses_plane = (d1 < -EPS and d2 > EPS) or (d1 > EPS and d2 < -EPS)

    if p1_on_plane or p2_on_plane or segment_crosses_plane:
        delta_d = d2 - d1
        if abs(delta_d) < EPS:
            intersection = p1
        else:
            t = -d1 / delta_d
            intersection = p1 + t * (p2 - p1)

        x_valid = plane.aabb_min[0] - EPS <= intersection[0] <= plane.aabb_max[0] + EPS
        z_valid = plane.aabb_min[2] - EPS <= intersection[2] <= plane.aabb_max[2] + EPS
        if x_valid and z_valid:
            return 0.0, True

    quad_vertices = _get_plane_quad_vertices(plane)
    dist1 = dist_segment_to_triangle(p1, p2, quad_vertices[0], quad_vertices[1], quad_vertices[2])
    dist2 = dist_segment_to_triangle(p1, p2, quad_vertices[1], quad_vertices[2], quad_vertices[3])
    return min(dist1, dist2), False



def segment_to_segment_aabb(P1: np.ndarray, P2: np.ndarray, r1:float, Q1: np.ndarray, Q2: np.ndarray,r2:float,safety_margin:float)-> bool:
    P_pad = r1+safety_margin
    segP_min_x = min(P1[0], P2[0])-P_pad
    segP_max_x = max(P1[0], P2[0])+P_pad
    segP_min_y = min(P1[1], P2[1])-P_pad
    segP_max_y = max(P1[1], P2[1])+P_pad
    segP_min_z = min(P1[2], P2[2])-P_pad
    segP_max_z = max(P1[2], P2[2])+P_pad

    segQ_min_x = min(Q1[0], Q2[0])-r2
    segQ_max_x = max(Q1[0], Q2[0])+r2
    segQ_min_y = min(Q1[1], Q2[1])-r2
    segQ_max_y = max(Q1[1], Q2[1])+r2
    segQ_min_z = min(Q1[2], Q2[2])-r2
    segQ_max_z = max(Q1[2], Q2[2])+r2
    
    # 包围盒不重叠->一定不相交->is_x/y/z_overlap = false
    is_x_overlap = not (segQ_max_x < segP_min_x or segQ_min_x > segP_max_x)
    is_y_overlap = not (segQ_max_y < segP_min_y or segQ_min_y > segP_max_y)
    is_z_overlap = not (segQ_max_z < segP_min_z or segQ_min_z > segP_max_z)

    return is_x_overlap and is_y_overlap and is_z_overlap

def segment_to_plane_aabb(plane: Plane, P1: np.ndarray, P2: np.ndarray, r:float, safety_margin:float)-> bool:
    pad = r+safety_margin
    segP_min_x = min(P1[0], P2[0])-pad
    segP_max_x = max(P1[0], P2[0])+pad
    segP_min_y = min(P1[1], P2[1])-pad
    segP_max_y = max(P1[1], P2[1])+pad
    segP_min_z = min(P1[2], P2[2])-pad   
    segP_max_z = max(P1[2], P2[2])+pad

    quad_vertices = _get_plane_quad_vertices(plane)
    plane_min_x = min(quad_vertices[0][0], quad_vertices[1][0], quad_vertices[2][0], quad_vertices[3][0])
    plane_max_x = max(quad_vertices[0][0], quad_vertices[1][0], quad_vertices[2][0], quad_vertices[3][0])
    plane_min_y = min(quad_vertices[0][1], quad_vertices[1][1], quad_vertices[2][1], quad_vertices[3][1])
    plane_max_y = max(quad_vertices[0][1], quad_vertices[1][1], quad_vertices[2][1], quad_vertices[3][1])
    plane_min_z = min(quad_vertices[0][2], quad_vertices[1][2], quad_vertices[2][2], quad_vertices[3][2])
    plane_max_z = max(quad_vertices[0][2], quad_vertices[1][2], quad_vertices[2][2], quad_vertices[3][2])

    is_x_overlap = not (plane_max_x < segP_min_x or plane_min_x > segP_max_x)
    is_y_overlap = not (plane_max_y < segP_min_y or plane_min_y > segP_max_y)
    is_z_overlap = not (plane_max_z < segP_min_z or plane_min_z > segP_max_z)

    return is_x_overlap and is_y_overlap and is_z_overlap
    


def is_pose_collision(
    joints_info: Dict[str, JointData],
    *args: Any,
    **kwargs: Any,
) -> Tuple[bool, List[str]]:
    _, plane, adj_matrix, safety_margin = _extract_collision_args(args, kwargs)

    for i, j in _get_collision_pair_indices(adj_matrix):
        link1_name = COLLISION_JOINT_LIST[i]
        link2_name = COLLISION_JOINT_LIST[j]
        link1 = joints_info[link1_name]
        link2 = joints_info[link2_name]
        if not segment_to_segment_aabb(link1.p1, link1.p2,link1.r, link2.p1, link2.p2,link2.r,safety_margin):
            continue
        dist = dist_segment_to_segment(link1.p1, link1.p2, link2.p1, link2.p2)
        if dist - (link1.r + link2.r) < safety_margin:
            return True, [link1_name, link2_name]

    for link_name in PLANE_COLLISION_JOINTS:
        link = joints_info[link_name]
        if not segment_to_plane_aabb(plane, link.p1, link.p2,link.r,safety_margin):
            continue
        dist_to_plane, is_intersect = dist_segment_to_plane(plane, link.p1, link.p2)
        if is_intersect or (dist_to_plane - link.r < safety_margin):
            return True, [link_name, 'plane']

    return False, []


def is_pose_collision_detail(
    joints_info: Dict[str, JointData],
    *args: Any,
    **kwargs: Any,
) -> Tuple[bool, List[Dict[str, Any]], List[str]]:
    _, plane, adj_matrix, safety_margin = _extract_collision_args(args, kwargs)

    collision_flag = False
    collision_results: List[Dict[str, Any]] = []
    collision_links: List[str] = []

    for i, j in _get_collision_pair_indices(adj_matrix):
        link1_name = COLLISION_JOINT_LIST[i]
        link2_name = COLLISION_JOINT_LIST[j]
        link1 = joints_info[link1_name]
        link2 = joints_info[link2_name]

        dist = dist_segment_to_segment(link1.p1, link1.p2, link2.p1, link2.p2)
        if dist - (link1.r + link2.r) < safety_margin:
            collision_flag = True
            collision_results.append(
                {
                    'type': 'link_link',
                    'link1': link1_name,
                    'link2': link2_name,
                    'distance': _rounded_distance(dist),
                }
            )
            collision_links.extend([link1_name, link2_name])

    for link_name in PLANE_COLLISION_JOINTS:
        link = joints_info[link_name]
        dist_to_plane, is_intersect = dist_segment_to_plane(plane, link.p1, link.p2)
        if is_intersect or (dist_to_plane - link.r < safety_margin):
            collision_flag = True
            collision_results.append(
                {
                    'type': 'link_plane',
                    'link': link_name,
                    'distance': _rounded_distance(dist_to_plane),
                    'is_intersect': bool(is_intersect),
                }
            )
            collision_links.append(link_name)

    return collision_flag, collision_results, collision_links


def binary_search_collision(
    start_angles: np.ndarray,
    target_angles: np.ndarray,
    joints_info: Dict[str, JointData],
    stl_data: Dict[str, STLData],
    plane: Plane,
    adj_matrix: np.ndarray,
    angle_map: Dict[str, List[int]],
    finger_funs: Dict[str, List[Callable]],
    safety_margin: float,
    max_iter: int = 10,
    tol: float = 0.1,
) -> Tuple[np.ndarray, List[str]]:
    start_angles = np.asarray(start_angles, dtype=float)
    target_angles = np.asarray(target_angles, dtype=float)

    if start_angles.shape != target_angles.shape:
        raise ValueError('start_angles and target_angles must have the same shape')
    if max_iter <= 0:
        raise ValueError('max_iter must be greater than 0')
    if tol <= 0:
        raise ValueError('tol must be greater than 0')

    from .pose_evaluator import evaluate_pose as evaluate_runtime_pose

    safe_angles = start_angles.copy()
    latest_collision_links: List[str] = []

    t_low, t_high = 0.0, 1.0
    for _ in range(max_iter):
        if t_high - t_low < tol:
            break

        t_mid = (t_low + t_high) / 2.0
        mid_angles = start_angles + (target_angles - start_angles) * t_mid
        evaluated_angles = _maybe_apply_passive_dip_mapping(mid_angles)
        joints_info, stl_data, has_collision, collision_links = evaluate_runtime_pose(
            angles=evaluated_angles,
            joints_info=joints_info,
            finger_funs=finger_funs,
            stl_data=stl_data,
            plane=plane,
            adj_matrix=adj_matrix,
            angle_map=angle_map,
            safety_margin=safety_margin,
        )

        if has_collision:
            t_high = t_mid
            if collision_links:
                latest_collision_links = list(collision_links)
        else:
            t_low = t_mid
            safe_angles = evaluated_angles.copy()

    return safe_angles, latest_collision_links


def binary_search_collision_path(
    start_angles: np.ndarray,
    target_angles: np.ndarray,
    joints_info: Dict[str, JointData],
    stl_data: Dict[str, STLData],
    plane: Plane,
    adj_matrix: np.ndarray,
    angle_map: Dict[str, List[int]],
    finger_funs: Dict[str, List[Callable]],
    safety_margin: float,
    max_iter: int = 25,
    tol: float = 1e-6,
    num_steps: int = 10,
) -> Tuple[bool, np.ndarray, List[str]]:
    start_angles = np.asarray(start_angles, dtype=float)
    target_angles = np.asarray(target_angles, dtype=float)

    if start_angles.shape != target_angles.shape:
        raise ValueError('start_angles and target_angles must have the same shape')
    if max_iter <= 0:
        raise ValueError('max_iter must be greater than 0')
    if tol <= 0:
        raise ValueError('tol must be greater than 0')
    if num_steps <= 0:
        raise ValueError('num_steps must be greater than 0')

    def evaluate_at(t_value: float) -> Tuple[bool, np.ndarray, List[str]]:
        sampled_angles = start_angles + (target_angles - start_angles) * t_value
        evaluated_angles = _maybe_apply_passive_dip_mapping(sampled_angles)
        updated_joints = update_joint_transforms(joints_info, evaluated_angles, angle_map, finger_funs)
        updated_joints = cal_capsule_param(updated_joints)
        response = is_pose_collision(updated_joints, plane, adj_matrix, safety_margin)
        has_collision, _, collision_links = _normalize_collision_response(response)
        return has_collision, evaluated_angles, collision_links

    last_safe_t = 0.0
    _, last_safe_angles, _ = evaluate_at(0.0)

    for step in range(num_steps + 1):
        t_value = step / num_steps
        has_collision, evaluated_angles, collision_links = evaluate_at(t_value)
        if has_collision:
            if step == 0:
                return True, evaluated_angles, collision_links

            t_low = last_safe_t
            t_high = t_value
            latest_collision_links = list(collision_links)
            for _ in range(max_iter):
                if t_high - t_low < tol:
                    break
                t_mid = (t_low + t_high) / 2.0
                mid_collision, mid_angles, mid_links = evaluate_at(t_mid)
                if mid_collision:
                    t_high = t_mid
                    if mid_links:
                        latest_collision_links = list(mid_links)
                else:
                    t_low = t_mid
                    last_safe_angles = mid_angles.copy()
            return True, last_safe_angles, latest_collision_links

        last_safe_t = t_value
        last_safe_angles = evaluated_angles.copy()

    return False, last_safe_angles, []


def path_collision_check(
    start_angles: np.ndarray,
    target_angles: np.ndarray,
    joints_info: Dict[str, JointData],
    stl_data: Dict[str, STLData],
    plane: Plane,
    adj_matrix: np.ndarray,
    angle_map: Dict[str, List[int]],
    finger_funs: Dict[str, List[Callable]],
    safety_margin: float,
) -> Tuple[bool, Optional[np.ndarray], Optional[List[str]]]:
    has_collision, safe_angles, collision_links = binary_search_collision_path(
        start_angles=start_angles,
        target_angles=target_angles,
        joints_info=joints_info,
        stl_data=stl_data,
        plane=plane,
        adj_matrix=adj_matrix,
        angle_map=angle_map,
        finger_funs=finger_funs,
        safety_margin=safety_margin,
    )
    if has_collision:
        return True, safe_angles, collision_links
    return False, None, None
