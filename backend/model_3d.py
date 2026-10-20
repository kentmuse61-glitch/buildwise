"""Generate safe, lightweight GLB concept massing models.

The primary generator builds a small scene graph of watertight conceptual
building components. It is intentionally a visual planning model only: it is
not an architectural, engineering, construction, or permit model.
"""

from __future__ import annotations

import json
import logging
import os
import re
import struct
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class Model3DGenerator:
    """Generate a conceptual GLB with a robust solid-geometry pipeline.

    ``manifold3d`` produces watertight solid components and ``trimesh``
    serializes the scene to standard GLB. Imports are kept inside generation
    so a broken optional runtime still returns the small standards-compliant
    fallback instead of preventing the API from starting.
    """

    _WALL_THICKNESS_M = 0.22
    _COMPONENT_COLORS = {
        "front_wall": (183, 197, 178, 255),
        "rear_wall": (174, 188, 169, 255),
        "side_wall": (164, 178, 160, 255),
        "slab": (100, 108, 100, 255),
        "roof": (70, 82, 71, 255),
        "balcony": (128, 139, 126, 255),
    }

    def __init__(self, output_dir: str = "output") -> None:
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate_model(self, spec: dict[str, Any], project_id: str | int) -> str:
        """Write a GLB model, using a cube fallback if primary generation fails."""
        safe_id = self._safe_id(project_id)
        filepath = os.path.join(self.output_dir, f"model_{safe_id}.glb")
        try:
            self._build_glb(spec, filepath)
            return filepath
        except (ImportError, OSError, TypeError, ValueError, ArithmeticError, struct.error) as error:
            logger.exception("3D model generation failed for project %s: %s", safe_id, error)
            return self._generate_fallback_model(safe_id)

    def _generate_fallback_model(self, project_id: str | int) -> str:
        """Write a valid one-storey cube when richer geometry is unavailable."""
        filepath = os.path.join(self.output_dir, f"model_{self._safe_id(project_id)}_fallback.glb")
        positions: list[tuple[float, float, float]] = []
        normals: list[tuple[float, float, float]] = []
        indices: list[int] = []
        self._append_box(positions, normals, indices, -1.0, 0.0, -1.0, 1.0, 2.5, 1.0)
        self._write_glb_file(filepath, positions, normals, indices, "FallbackConceptBuilding")
        return filepath

    @staticmethod
    def _safe_id(value: str | int) -> str:
        return re.sub(r"[^A-Za-z0-9_-]", "", str(value))[:48] or "project"

    def _build_glb(self, spec: dict[str, Any], filepath: str) -> None:
        """Build a small visual massing scene with door/window recesses.

        Geometry comes only from normalized concept inputs. It is deliberately
        not derived from surveys, structural calculations, or regulatory data.
        """
        import manifold3d as manifold
        import numpy as np
        import trimesh

        floors = self._number_as_int(spec.get("floors"), default=1, minimum=1, maximum=50)
        area = self._number_as_float(spec.get("area_sqm"), default=100.0, minimum=20.0, maximum=1_000_000.0)
        ceiling_height = self._number_as_float(spec.get("ceiling_height"), default=3.2, minimum=2.5, maximum=6.0)
        footprint_area = area / floors
        width = math_sqrt(footprint_area * 1.25)
        depth = footprint_area / width
        if width <= self._WALL_THICKNESS_M * 3 or depth <= self._WALL_THICKNESS_M * 3:
            raise ValueError("Concept footprint is too small for a 3D shell")

        scene = trimesh.Scene()
        scene.metadata.update({
            "generator": "Buildwise GH",
            "model_purpose": "early-planning concept massing only",
            "not_for_construction_or_permit": True,
            "units": "metres",
        })
        half_width, half_depth = width / 2, depth / 2
        wall = self._WALL_THICKNESS_M

        # A ground slab and a roof cap help the viewer read this as a building
        # while each level remains independently identifiable in the GLB scene.
        foundation = manifold.Manifold.cube((width + wall, 0.22, depth + wall), center=True).translate((0, -0.11, 0))
        self._append_scene_component(scene, foundation, "foundation_slab_concept", "slab", np, trimesh)

        for floor in range(floors):
            base = floor * ceiling_height
            floor_number = floor + 1
            front_wall = manifold.Manifold.cube((width, ceiling_height, wall), center=True).translate((0, base + ceiling_height / 2, half_depth - wall / 2))
            rear_wall = manifold.Manifold.cube((width, ceiling_height, wall), center=True).translate((0, base + ceiling_height / 2, -half_depth + wall / 2))
            west_wall = manifold.Manifold.cube((wall, ceiling_height, depth - 2 * wall), center=True).translate((-half_width + wall / 2, base + ceiling_height / 2, 0))
            east_wall = manifold.Manifold.cube((wall, ceiling_height, depth - 2 * wall), center=True).translate((half_width - wall / 2, base + ceiling_height / 2, 0))

            front_wall = self._cut_front_openings(front_wall, floor, width, depth, base, ceiling_height, manifold)
            rear_wall = self._cut_rear_openings(rear_wall, width, depth, base, ceiling_height, manifold)
            self._append_scene_component(scene, front_wall, f"floor_{floor_number}_front_wall_concept", "front_wall", np, trimesh)
            self._append_scene_component(scene, rear_wall, f"floor_{floor_number}_rear_wall_concept", "rear_wall", np, trimesh)
            self._append_scene_component(scene, west_wall, f"floor_{floor_number}_west_wall_concept", "side_wall", np, trimesh)
            self._append_scene_component(scene, east_wall, f"floor_{floor_number}_east_wall_concept", "side_wall", np, trimesh)

            if floor < floors - 1:
                slab = manifold.Manifold.cube((width, 0.18, depth), center=True).translate((0, base + ceiling_height, 0))
                self._append_scene_component(scene, slab, f"floor_{floor_number}_ceiling_slab_concept", "slab", np, trimesh)

        roof_base = floors * ceiling_height
        roof = manifold.Manifold.cube((width + 0.40, 0.26, depth + 0.40), center=True).translate((0, roof_base + 0.13, 0))
        self._append_scene_component(scene, roof, "roof_slab_concept", "roof", np, trimesh)
        if self._has_balcony(spec):
            balcony = manifold.Manifold.cube((max(width * 0.35, 1.6), 0.18, 1.25), center=True).translate((0, roof_base - ceiling_height + 0.10, half_depth + 0.52))
            self._append_scene_component(scene, balcony, "front_balcony_concept", "balcony", np, trimesh)

        if not scene.geometry:
            raise ValueError("No concept geometry was generated")
        glb = scene.export(file_type="glb")
        if not isinstance(glb, bytes) or len(glb) < 20:
            raise ValueError("GLB serialization returned no usable model")
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        Path(filepath).write_bytes(self._finalize_concept_glb(glb))

    @staticmethod
    def _finalize_concept_glb(glb: bytes) -> bytes:
        """Add portable buffer targets and immutable concept-model metadata.

        Trimesh deliberately omits optional WebGL buffer targets. They are
        useful for validators and browsers, so add them to this internally
        generated GLB without accepting or parsing any user-supplied model.
        """
        if len(glb) < 20:
            raise ValueError("GLB is incomplete")
        magic, version, declared_length = struct.unpack("<4sII", glb[:12])
        json_length, json_type = struct.unpack("<II", glb[12:20])
        json_end = 20 + json_length
        if magic != b"glTF" or version != 2 or declared_length != len(glb) or json_type != 0x4E4F534A or json_end + 8 > len(glb):
            raise ValueError("GLB serialization is not valid glTF 2.0")
        bin_length, bin_type = struct.unpack("<II", glb[json_end:json_end + 8])
        bin_start = json_end + 8
        bin_end = bin_start + bin_length
        if bin_type != 0x004E4942 or bin_end != len(glb):
            raise ValueError("GLB binary chunk is incomplete")

        document = json.loads(glb[20:json_end].decode("utf-8"))
        accessors = document.get("accessors", [])
        buffer_views = document.get("bufferViews", [])
        for mesh in document.get("meshes", []):
            for primitive in mesh.get("primitives", []):
                for accessor_index in primitive.get("attributes", {}).values():
                    view_index = accessors[accessor_index].get("bufferView")
                    if view_index is not None:
                        buffer_views[view_index]["target"] = 34962  # ARRAY_BUFFER
                index_accessor = primitive.get("indices")
                if index_accessor is not None:
                    view_index = accessors[index_accessor].get("bufferView")
                    if view_index is not None:
                        buffer_views[view_index]["target"] = 34963  # ELEMENT_ARRAY_BUFFER
        asset = document.setdefault("asset", {})
        extras = asset.setdefault("extras", {})
        extras["buildwise"] = {
            "modelPurpose": "early-planning concept massing only",
            "notForConstructionOrPermit": True,
            "units": "metres",
        }

        json_chunk = json.dumps(document, separators=(",", ":")).encode("utf-8")
        json_chunk += b" " * ((-len(json_chunk)) % 4)
        binary_chunk = glb[bin_start:bin_end]
        total_length = 12 + 8 + len(json_chunk) + 8 + len(binary_chunk)
        return (
            struct.pack("<4sII", b"glTF", 2, total_length)
            + struct.pack("<II", len(json_chunk), 0x4E4F534A)
            + json_chunk
            + struct.pack("<II", len(binary_chunk), 0x004E4942)
            + binary_chunk
        )

    def _cut_front_openings(self, wall_solid: Any, floor: int, width: float, depth: float, base: float, height: float, manifold: Any) -> Any:
        """Cut visual entry/window openings through the front facade component."""
        cutter_depth = self._WALL_THICKNESS_M + 0.06
        z = depth / 2 - self._WALL_THICKNESS_M / 2
        if floor == 0:
            door_width = min(1.20, width * 0.20)
            door_height = min(2.20, height * 0.82)
            door = manifold.Manifold.cube((door_width, door_height, cutter_depth), center=True).translate((0, base + door_height / 2, z))
            wall_solid = wall_solid - door
        window_width = min(1.55, width * 0.18)
        window_height = min(1.20, height * 0.38)
        sill = min(1.20, height - window_height - 0.25)
        for x in (-width * 0.28, width * 0.28):
            opening = manifold.Manifold.cube((window_width, window_height, cutter_depth), center=True).translate((x, base + sill + window_height / 2, z))
            wall_solid = wall_solid - opening
        return wall_solid

    def _cut_rear_openings(self, wall_solid: Any, width: float, depth: float, base: float, height: float, manifold: Any) -> Any:
        """Cut two modest concept windows through the rear facade component."""
        cutter_depth = self._WALL_THICKNESS_M + 0.06
        z = -depth / 2 + self._WALL_THICKNESS_M / 2
        window_width = min(1.35, width * 0.16)
        window_height = min(1.05, height * 0.34)
        sill = min(1.25, height - window_height - 0.25)
        for x in (-width * 0.25, width * 0.25):
            opening = manifold.Manifold.cube((window_width, window_height, cutter_depth), center=True).translate((x, base + sill + window_height / 2, z))
            wall_solid = wall_solid - opening
        return wall_solid

    def _append_scene_component(self, scene: Any, solid: Any, name: str, color_name: str, np: Any, trimesh: Any) -> None:
        """Convert one manifold solid to a colored, named GLB scene component."""
        mesh_data = solid.to_mesh()
        vertices = np.asarray(mesh_data.vert_properties, dtype=np.float64)[:, :3]
        faces = np.asarray(mesh_data.tri_verts, dtype=np.int64)
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False, validate=False)
        if mesh.is_empty or not mesh.is_watertight or mesh.volume <= 0:
            raise ValueError(f"Concept component {name!r} is not a closed solid")
        color = np.asarray(self._COMPONENT_COLORS[color_name], dtype=np.uint8)
        # Vertex colors preserve materials without an image/texture dependency.
        mesh.visual.vertex_colors = np.tile(color, (len(mesh.vertices), 1))
        scene.add_geometry(mesh, node_name=name, geom_name=name)

    @staticmethod
    def _has_balcony(spec: dict[str, Any]) -> bool:
        features = spec.get("special_features")
        return isinstance(features, list) and any(str(feature).lower() == "balcony" for feature in features)

    @staticmethod
    def _number_as_int(value: Any, default: int, minimum: int, maximum: int) -> int:
        try:
            return min(max(int(value), minimum), maximum)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _number_as_float(value: Any, default: float, minimum: float, maximum: float) -> float:
        try:
            parsed = float(value)
            if not parsed == parsed:  # NaN
                return default
            return min(max(parsed, minimum), maximum)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _append_box(
        positions: list[tuple[float, float, float]],
        normals: list[tuple[float, float, float]],
        indices: list[int],
        x1: float,
        y1: float,
        z1: float,
        x2: float,
        y2: float,
        z2: float,
    ) -> None:
        faces = [
            ([(x1, y1, z1), (x1, y2, z1), (x2, y2, z1), (x2, y1, z1)], (0.0, 0.0, -1.0)),
            ([(x1, y1, z2), (x2, y1, z2), (x2, y2, z2), (x1, y2, z2)], (0.0, 0.0, 1.0)),
            ([(x1, y1, z1), (x1, y1, z2), (x1, y2, z2), (x1, y2, z1)], (-1.0, 0.0, 0.0)),
            ([(x2, y1, z1), (x2, y2, z1), (x2, y2, z2), (x2, y1, z2)], (1.0, 0.0, 0.0)),
            ([(x1, y2, z1), (x1, y2, z2), (x2, y2, z2), (x2, y2, z1)], (0.0, 1.0, 0.0)),
            ([(x1, y1, z1), (x2, y1, z1), (x2, y1, z2), (x1, y1, z2)], (0.0, -1.0, 0.0)),
        ]
        for corners, normal in faces:
            start = len(positions)
            positions.extend(corners)
            normals.extend([normal] * 4)
            indices.extend((start, start + 1, start + 2, start, start + 2, start + 3))

    def _write_glb_file(
        self,
        filepath: str,
        positions: list[tuple[float, float, float]],
        normals: list[tuple[float, float, float]],
        indices: list[int],
        model_name: str,
    ) -> None:
        """Write a standards-compliant fallback GLB with normals and a material."""
        if len(positions) != len(normals) or not positions or not indices:
            raise ValueError("GLB geometry is incomplete")
        if len(positions) > 65535:
            raise ValueError("Model exceeds supported vertex limit")

        position_bytes = struct.pack("<" + "f" * (len(positions) * 3), *(value for point in positions for value in point))
        normal_bytes = struct.pack("<" + "f" * (len(normals) * 3), *(value for normal in normals for value in normal))
        index_bytes = struct.pack("<" + "H" * len(indices), *indices)
        binary_raw = position_bytes + normal_bytes + index_bytes
        min_position = [min(point[axis] for point in positions) for axis in range(3)]
        max_position = [max(point[axis] for point in positions) for axis in range(3)]

        gltf = {
            "asset": {"version": "2.0", "generator": "Buildwise GH"},
            "scene": 0,
            "scenes": [{"nodes": [0]}],
            "nodes": [{"mesh": 0, "name": model_name}],
            "meshes": [{"name": model_name, "primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1}, "indices": 2, "material": 0}]}],
            "materials": [{
                "name": "ConceptBuildingMaterial",
                "pbrMetallicRoughness": {"baseColorFactor": [0.72, 0.79, 0.70, 1.0], "metallicFactor": 0.0, "roughnessFactor": 0.82},
            }],
            "accessors": [
                {"bufferView": 0, "componentType": 5126, "count": len(positions), "type": "VEC3", "min": min_position, "max": max_position},
                {"bufferView": 1, "componentType": 5126, "count": len(normals), "type": "VEC3"},
                {"bufferView": 2, "componentType": 5123, "count": len(indices), "type": "SCALAR"},
            ],
            "bufferViews": [
                {"buffer": 0, "byteOffset": 0, "byteLength": len(position_bytes), "target": 34962},
                {"buffer": 0, "byteOffset": len(position_bytes), "byteLength": len(normal_bytes), "target": 34962},
                {"buffer": 0, "byteOffset": len(position_bytes) + len(normal_bytes), "byteLength": len(index_bytes), "target": 34963},
            ],
            "buffers": [{"byteLength": len(binary_raw)}],
        }
        json_chunk = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
        json_chunk += b" " * ((-len(json_chunk)) % 4)
        binary_chunk = binary_raw + b"\x00" * ((-len(binary_raw)) % 4)
        total_length = 12 + 8 + len(json_chunk) + 8 + len(binary_chunk)

        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        with open(filepath, "wb") as output:
            output.write(struct.pack("<4sII", b"glTF", 2, total_length))
            output.write(struct.pack("<II", len(json_chunk), 0x4E4F534A))
            output.write(json_chunk)
            output.write(struct.pack("<II", len(binary_chunk), 0x004E4942))
            output.write(binary_chunk)


def math_sqrt(value: float) -> float:
    """Keep dimensions valid before they reach the geometry library."""
    if value <= 0:
        raise ValueError("Building footprint must be positive")
    return value ** 0.5
