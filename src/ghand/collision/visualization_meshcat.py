# SPDX-FileCopyrightText: 2025-2026 GLITech
# SPDX-License-Identifier: Apache-2.0

"""Meshcat-based visualization drop-in replacement for src/collision_detect/visualization.py."""

import copy
from typing import Dict, List, Optional, Sequence
import time
import numpy as np
import trimesh

try:
    import meshcat
    from meshcat import geometry as g
except ImportError as exc:
    raise ImportError(
        "meshcat is required. Install it via: pip install meshcat"
    ) from exc

from . import angle_mapping as ang_mp
from . import pose_evaluator as pose_eval
from .datatypes import ANGLE_MAP, LINK_NAMES, JointData, Plane, STLData
from .mesh_utils import create_capsule_mesh, create_trimesh_from_joint
from .passive_dip_mapping import apply_passive_dip_mapping
from .runtime_loader import load_collision_runtime
from .transforms import CAPSULE_LINK_NAMES

PLOT_LINK_NAMES = list(LINK_NAMES)

MESHCAT_CAMERA_TARGET = np.array([0.0, -0.01, 0.02], dtype=float)
MESHCAT_CAMERA_POSITION = [0, 0.30, 0.53]
MESHCAT_CAMERA_FOV = 62


def _translation_matrix(xyz: Sequence[float]) -> np.ndarray:
    transform = np.eye(4)
    transform[:3, 3] = np.asarray(xyz, dtype=float)
    return transform


def _set_default_camera(vis: meshcat.Visualizer) -> None:
    vis['/Cameras/default/rotated'].set_object(
        g.PerspectiveCamera(fov=MESHCAT_CAMERA_FOV, near=0.001, far=100.0)
    )
    vis['/Cameras/default'].set_transform(
        _translation_matrix(MESHCAT_CAMERA_TARGET)
    )
    vis['/Cameras/default/rotated/<object>'].set_property(
        'position',
        MESHCAT_CAMERA_POSITION,
    )


def add_xy_grid(
    scene,
    x_range: Sequence[float] = (-0.1, 0.2),
    y_range: Sequence[float] = (-0.2, 0.1),
    z_height: float = -0.05,
    step: float = 0.05,
):
    """No-op for API compatibility 鈥?Meshcat displays a built-in grid by default."""
    print('Meshcat visualizer uses its built-in grid; add_xy_grid is a no-op.')


def _trimesh_to_meshcat(mesh_obj: trimesh.Trimesh):
    vertices = np.asarray(mesh_obj.vertices, dtype=np.float32)
    faces = np.asarray(mesh_obj.faces, dtype=np.uint32)
    geom = g.TriangularMeshGeometry(vertices, faces)

    color_int = 0xAAAAAA
    alpha = 1.0
    if hasattr(mesh_obj.visual, 'vertex_colors') and mesh_obj.visual.vertex_colors is not None:
        cols = np.asarray(mesh_obj.visual.vertex_colors)
        if cols.ndim == 2 and cols.shape[1] >= 3:
            if cols.max() > 1.0:
                cols = cols / 255.0
            rgba = cols[0]
            r = int(np.clip(rgba[0] * 255, 0, 255))
            g_ = int(np.clip(rgba[1] * 255, 0, 255))
            b = int(np.clip(rgba[2] * 255, 0, 255))
            color_int = (r << 16) | (g_ << 8) | b
            alpha = float(np.clip(rgba[3] if cols.shape[1] > 3 else 1.0, 0.0, 1.0))

    return geom, color_int, alpha


def _plane_quad_vertices(plane: Plane) -> np.ndarray:
    y_value = float(plane.p0[1])
    return np.array(
        [
            [plane.aabb_min[0], y_value, plane.aabb_min[2]],
            [plane.aabb_min[0], y_value, plane.aabb_max[2]],
            [plane.aabb_max[0], y_value, plane.aabb_max[2]],
            [plane.aabb_max[0], y_value, plane.aabb_min[2]],
        ],
        dtype=float,
    )


def _plane_center(plane: Plane) -> np.ndarray:
    return np.mean(_plane_quad_vertices(plane), axis=0)


def _add_palm_plane(
    vis: meshcat.Visualizer,
    plane: Plane,
    translation: np.ndarray | None = None,
    path_prefix: str = 'palm_plane',
) -> None:
    if plane.aabb_min is None or plane.aabb_max is None or plane.p0 is None:
        print('Skipped palm plane visualization: plane boundary data is incomplete.')
        return

    translation = np.zeros(3, dtype=float) if translation is None else np.asarray(translation, dtype=float)
    quad = _plane_quad_vertices(plane) + translation
    center = _plane_center(plane) + translation

    surface_mesh = trimesh.Trimesh(
        vertices=quad,
        faces=np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int64),
        process=False,
    )
    surface_mesh.visual.vertex_colors = [0.25, 0.55, 1.0, 0.18]
    surface_geom, surface_color, surface_alpha = _trimesh_to_meshcat(surface_mesh)
    vis[path_prefix]['surface'].set_object(
        surface_geom,
        g.MeshPhongMaterial(
            color=surface_color,
            transparent=True,
            opacity=surface_alpha,
            side=2,
        ),
    )

    edge_vertices = np.asarray(
        [
            quad[0], quad[1],
            quad[1], quad[2],
            quad[2], quad[3],
            quad[3], quad[0],
        ],
        dtype=np.float32,
    ).T
    vis[path_prefix]['boundary'].set_object(
        g.LineSegments(
            g.PointsGeometry(edge_vertices),
            g.LineBasicMaterial(color=0x003B8E, linewidth=4.0),
        )
    )

    center_marker = trimesh.creation.icosphere(radius=0.003, subdivisions=2)
    center_marker.apply_translation(center)
    center_marker.visual.vertex_colors = [1.0, 0.0, 0.0, 1.0]
    center_geom, center_color, center_alpha = _trimesh_to_meshcat(center_marker)
    vis[path_prefix]['center'].set_object(
        center_geom,
        g.MeshPhongMaterial(
            color=center_color,
            transparent=center_alpha < 1.0,
            opacity=center_alpha,
        ),
    )
    print(f'Added palm plane: center={center.tolist()}, boundary_vertices={quad.tolist()}')


def _add_pose_geometry(
    vis: meshcat.Visualizer,
    joints_info: Dict[str, JointData],
    stl_data: Dict[str, STLData],
    collision_links: Optional[List[str]],
    translation: np.ndarray,
    plot_finger: bool,
    plot_capsule: bool,
    mesh_color: List[float],
    capsule_color: List[float],
    label: str,
    path_prefix: str,
) -> None:
    collision_links = collision_links or []
    collision_link_set = set(collision_links)
    translation = np.asarray(translation, dtype=float)
    total_faces = 0
    capsule_count = 0
    highlighted_mesh_links: List[str] = []
    highlighted_capsule_links: List[str] = []

    if plot_finger:
        for link_name in PLOT_LINK_NAMES:
            if link_name not in joints_info or link_name not in stl_data:
                continue
            is_collision_link = link_name in collision_link_set
            current_mesh_color = (
                [1.0, 0.0, 0.0, 0.85]
                if is_collision_link
                else list(mesh_color)
            )
            if is_collision_link:
                highlighted_mesh_links.append(link_name)
            mesh_obj = create_trimesh_from_joint(
                joints_info[link_name], stl_data[link_name], current_mesh_color
            )
            mesh_obj.apply_translation(translation)
            geom, color_int, alpha = _trimesh_to_meshcat(mesh_obj)
            material = g.MeshPhongMaterial(
                color=color_int, transparent=alpha < 1.0, opacity=alpha
            )
            vis[path_prefix][link_name].set_object(geom, material)
            total_faces += len(mesh_obj.faces)

    if plot_capsule:
        for link_name in CAPSULE_LINK_NAMES:
            if link_name not in joints_info:
                continue
            data = joints_info[link_name]
            if data.p1 is None or data.p2 is None or data.r is None:
                continue
            is_collision_link = link_name in collision_link_set
            current_capsule_color = (
                [1.0, 0.0, 0.0, 0.7]
                if is_collision_link
                else list(capsule_color)
            )
            if is_collision_link:
                highlighted_capsule_links.append(link_name)
            mesh_obj = create_capsule_mesh(data.p1, data.p2, data.r, current_capsule_color)
            mesh_obj.apply_translation(translation)
            geom, color_int, alpha = _trimesh_to_meshcat(mesh_obj)
            material = g.MeshPhongMaterial(
                color=color_int, transparent=alpha < 1.0, opacity=alpha
            )
            vis[path_prefix][f"capsule_{link_name}"].set_object(geom, material)
            capsule_count += 1

    print(f'Added pose "{label}": {total_faces} mesh faces, {capsule_count} capsules.')


def visualize_scene(
    joints_info: Dict[str, JointData],
    stl_data: Dict[str, STLData],
    collision_links: Optional[List[str]] = None,
    plane: Plane | None = None,
    plot_finger: bool = True,
    plot_capsule: bool = True,
    plot_plane: bool = True,
):
    """Visualize a single hand pose in a meshcat scene."""
    print('\nPreparing single-pose meshcat visualization...')
    vis = meshcat.Visualizer()
    vis["/Background"].set_property("top_color", [1, 1, 1])
    vis["/Background"].set_property("bottom_color", [1, 1, 1])
    vis["/Grid"].set_property("visible", True)
    _set_default_camera(vis)

    if plot_plane and plane is not None:
        _add_palm_plane(vis, plane)

    _add_pose_geometry(
        vis,
        joints_info,
        stl_data,
        collision_links,
        np.zeros(3, dtype=float),
        plot_finger,
        plot_capsule,
        mesh_color=[0.6, 0.6, 0.6, 1.0],
        capsule_color=[0.0, 1.0, 0.0, 0.25],
        label='current pose',
        path_prefix='current_pose',
    )

    print(f'Open the viewer at: {vis.url()}')
    vis.open()
    time.sleep(3.0)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


def visualize_pose_comparison_scene(
    static_joints_info: Dict[str, JointData],
    static_stl_data: Dict[str, STLData],
    static_collision_links: Optional[List[str]],
    safe_joints_info: Dict[str, JointData],
    safe_stl_data: Dict[str, STLData],
    safe_collision_links: Optional[List[str]] = None,
    plot_finger: bool = True,
    plot_capsule: bool = True,
    separation: float = 0.18,
):
    """Visualize static-collision and safe poses side by side in one meshcat scene."""
    print('\nPreparing side-by-side meshcat visualization...')
    vis = meshcat.Visualizer()
    vis["/Background"].set_property("top_color", [1, 1, 1])
    vis["/Background"].set_property("bottom_color", [1, 1, 1])
    vis["/Grid"].set_property("visible", True)
    _set_default_camera(vis)

    _add_pose_geometry(
        vis,
        static_joints_info,
        static_stl_data,
        static_collision_links,
        np.array([-separation / 2.0, 0.0, 0.0], dtype=float),
        plot_finger,
        plot_capsule,
        mesh_color=[0.72, 0.72, 0.72, 1.0],
        capsule_color=[1.0, 0.65, 0.0, 0.25],
        label='static collision pose',
        path_prefix='static_pose',
    )
    if safe_joints_info is not None and safe_stl_data is not None:
        _add_pose_geometry(
            vis,
            safe_joints_info,
            safe_stl_data,
            safe_collision_links,
            np.array([separation / 2.0, 0.0, 0.0], dtype=float),
            plot_finger,
            plot_capsule,
            mesh_color=[0.55, 0.7, 0.92, 1.0],
            capsule_color=[0.0, 0.8, 0.2, 0.25],
            label='safe pose',
            path_prefix='safe_pose',
        )

    print(f'Open the viewer at: {vis.url()}')
    vis.open()
    time.sleep(3.0)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


def plot_single_pose(
    sdk_angles: list[float],
    safety_margin: float = 0.0,
    plot_finger: bool = True,
    plot_capsule: bool = True,
    plot_plane: bool = True,
) -> None:
    runtime = load_collision_runtime()
    internal_angles = ang_mp.sdk_degrees_to_internal_radians(sdk_angles)
    internal_angles = apply_passive_dip_mapping(internal_angles)
    static_joints_info, static_stl_data, _, static_collision_links = pose_eval.evaluate_pose(
        angles=internal_angles,
        joints_info=copy.deepcopy(runtime.joints_template),
        finger_funs=runtime.finger_funs,
        stl_data=runtime.stl_data,
        plane=runtime.plane,
        adj_matrix=runtime.adj_matrix,
        angle_map=ANGLE_MAP,
        safety_margin=safety_margin,
        transform_stl=True,
    )

    visualize_scene(
        static_joints_info,
        static_stl_data,
        static_collision_links,
        plane=runtime.plane,
        plot_finger=plot_finger,
        plot_capsule=plot_capsule,
        plot_plane=plot_plane,
    )


def plot_pose_compare(
    sdk_angles: list[float],
    safe_sdk_angles: list[float] | None,
    safety_margin: float = 0.0,
    plot_finger: bool = True,
    plot_capsule: bool = True,
) -> None:
    runtime = load_collision_runtime()

    internal_angles = ang_mp.sdk_degrees_to_internal_radians(sdk_angles)
    internal_angles = apply_passive_dip_mapping(internal_angles)
    static_joints_info, static_stl_data, _, static_collision_links = pose_eval.evaluate_pose(
        angles=internal_angles,
        joints_info=copy.deepcopy(runtime.joints_template),
        finger_funs=runtime.finger_funs,
        stl_data=runtime.stl_data,
        plane=runtime.plane,
        adj_matrix=runtime.adj_matrix,
        angle_map=ANGLE_MAP,
        safety_margin=safety_margin,
        transform_stl=True,
    )

    safe_joints_info = None
    safe_stl_data = None
    safe_collision_links = None
    if safe_sdk_angles is not None:
        safe_full_angles = np.asarray(ang_mp.sdk_degrees_to_internal_radians(safe_sdk_angles), dtype=float)
        safe_full_angles = apply_passive_dip_mapping(safe_full_angles)
        safe_joints_info, safe_stl_data, _, safe_collision_links = pose_eval.evaluate_pose(
            angles=safe_full_angles,
            joints_info=copy.deepcopy(runtime.joints_template),
            finger_funs=runtime.finger_funs,
            stl_data=runtime.stl_data,
            plane=runtime.plane,
            adj_matrix=runtime.adj_matrix,
            angle_map=ANGLE_MAP,
            safety_margin=safety_margin,
            transform_stl=True,
        )

    visualize_pose_comparison_scene(
        static_joints_info,
        static_stl_data,
        static_collision_links,
        safe_joints_info,
        safe_stl_data,
        safe_collision_links,
        plot_finger=plot_finger,
        plot_capsule=plot_capsule,
    )
