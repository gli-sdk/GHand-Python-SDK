import numpy as np
import trimesh
from stl import mesh
from typing import List

from .datatypes import JointData, STLData


def load_stl(stl_path: str) -> mesh.Mesh:
    """
    Load an STL file from disk.

    Args:
        stl_path (str): Path to the STL file.

    Returns:
        mesh.Mesh: Loaded STL mesh object.
    """
    return mesh.Mesh.from_file(stl_path)


def create_trimesh_from_joint(
    joint_data: JointData,
    stl_item: STLData,
    color: List[float] = None,
) -> trimesh.Trimesh:
    """
    Build a trimesh object for visualization from joint and STL data.

    Args:
        joint_data (JointData): Runtime joint data for the current link.
        stl_item (STLData): STL data associated with the link.
        color (List[float]): RGBA color. Defaults to gray.

    Returns:
        trimesh.Trimesh: Transformed mesh object.
    """
    if color is None:
        color = [150 / 255, 150 / 255, 150 / 255, 1.0]

    vertices = stl_item.raw_data.points.reshape(-1, 3)
    num_faces = len(stl_item.raw_data.vectors)
    faces = np.arange(num_faces * 3).reshape(num_faces, 3)

    vertices_homo = np.hstack([vertices, np.ones((vertices.shape[0], 1))]).T
    vertices_transformed = (joint_data.trans_matrix @ vertices_homo).T[:, :3]

    mesh_obj = trimesh.Trimesh(vertices=vertices_transformed, faces=faces)
    mesh_obj.visual.vertex_colors = color
    return mesh_obj


def create_capsule_mesh(
    p1: np.ndarray,
    p2: np.ndarray,
    radius: float,
    color: List[float] = None,
) -> trimesh.Trimesh:
    """
    Create a capsule mesh for visualization.

    Args:
        p1 (np.ndarray): Capsule start point.
        p2 (np.ndarray): Capsule end point.
        radius (float): Capsule radius.
        color (List[float]): RGBA color. Defaults to semi-transparent green.

    Returns:
        trimesh.Trimesh: Capsule mesh object.
    """
    if color is None:
        color = [0.0, 1.0, 0.0, 0.25]

    p1 = p1.flatten()
    p2 = p2.flatten()
    direction = p2 - p1
    length = np.linalg.norm(direction)

    if length < 1e-6:
        return trimesh.creation.icosphere(radius=radius, subdivisions=2).apply_translation(p1)

    cylinder = trimesh.creation.cylinder(radius=radius, height=length, sections=16)
    sphere1 = trimesh.creation.icosphere(radius=radius, subdivisions=2)
    sphere2 = trimesh.creation.icosphere(radius=radius, subdivisions=2)

    cylinder.apply_translation([0, 0, length / 2])
    direction_unit = direction / length

    z_axis = np.array([0, 0, 1])
    if np.allclose(direction_unit, z_axis):
        rotation = np.eye(3)
    elif np.allclose(direction_unit, -z_axis):
        rotation = np.diag([1, -1, -1])
    else:
        v = np.cross(z_axis, direction_unit)
        s = np.linalg.norm(v)
        c = np.dot(z_axis, direction_unit)
        vx = np.array(
            [
                [0, -v[2], v[1]],
                [v[2], 0, -v[0]],
                [-v[1], v[0], 0],
            ]
        )
        rotation = np.eye(3) + vx + vx @ vx * ((1 - c) / (s**2))

    transform = np.eye(4)
    transform[:3, :3] = rotation
    transform[:3, 3] = p1

    cylinder.apply_transform(transform)
    sphere1.apply_transform(transform)

    transform_sphere2 = transform.copy()
    transform_sphere2[:3, 3] = p2
    sphere2.apply_transform(transform_sphere2)

    capsule = trimesh.util.concatenate([cylinder, sphere1, sphere2])
    capsule.visual.vertex_colors = color
    return capsule
