"""Generate robust glTF 2.0 binary (GLB) concept massing models.

The generated files are lightweight visual planning models only. They are not
architectural, structural, engineering, construction, or permit models.
"""

from __future__ import annotations

import json
import logging
import os
import re
import struct
from pathlib import Path
from typing import Any

import numpy as np

from .plan_generator import PlanGenerator

logger = logging.getLogger(__name__)


class Model3DGenerator:
    """Generate a valid GLB containing one closed box mass per concept floor."""

    _MAX_FLOORS = 50
    _MIN_AREA_SQM = 20.0
    _MAX_AREA_SQM = 1_000_000.0

    def __init__(self, output_dir: str = "output") -> None:
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate_model(self, spec: dict[str, Any], project_id: str | int) -> str:
        """Write a concept GLB and return a valid fallback on generation failure."""
        safe_id = self._safe_id(project_id)
        filepath = Path(self.output_dir) / f"model_{safe_id}.glb"
        try:
            self._build_glb(spec, filepath)
            return str(filepath)
        except (OSError, TypeError, ValueError, ArithmeticError, OverflowError, struct.error) as error:
            logger.exception("3D model generation failed for project %s: %s", safe_id, error)
            return self._generate_fallback_model(safe_id)

    def generate_dollhouse_model(self, spec: dict[str, Any], project_id: str | int) -> str:
        """Write an open-roof, room-aware cutaway GLB concept preview.

        This is a visual floor-programme aid: room blocks, simplified walls and
        furniture cues are intentionally schematic and never represent a
        structural, fire, accessibility, services or construction model.
        """
        safe_id = self._safe_id(project_id)
        filepath = Path(self.output_dir) / f"dollhouse_{safe_id}.glb"
        try:
            self._build_dollhouse_glb(spec, filepath)
            return str(filepath)
        except (OSError, TypeError, ValueError, ArithmeticError, OverflowError, struct.error) as error:
            logger.exception("Dollhouse generation failed for project %s: %s", safe_id, error)
            return self._generate_fallback_model(f"{safe_id}-dollhouse")

    def _build_dollhouse_glb(self, spec: dict[str, Any], filepath: Path) -> None:
        floors = self._number_as_int(spec.get("floors"), default=1, minimum=1, maximum=self._MAX_FLOORS)
        floor_height = self._number_as_float(spec.get("ceiling_height"), default=3.05, minimum=2.5, maximum=5.0)
        wall_height = max(2.25, floor_height - 0.42)
        wall_thickness = 0.12
        materials = self._dollhouse_materials()
        meshes: list[dict[str, Any]] = []
        planner = PlanGenerator(self.output_dir)

        def add_box(name: str, material: int, x1: float, y1: float, z1: float, x2: float, y2: float, z2: float) -> None:
            positions, normals, indices = self._box_geometry(x1, y1, z1, x2, y2, z2)
            meshes.append({"name": name, "material": material, "positions": positions, "normals": normals, "indices": indices})

        all_extents: list[tuple[float, float, float, float]] = []
        for floor_number in range(1, floors + 1):
            design = dict(spec.get("design_studio")) if isinstance(spec.get("design_studio"), dict) else {}
            design["active_floor"] = floor_number
            floor_spec = dict(spec)
            floor_spec["design_studio"] = design
            rooms = planner.layout_rooms(floor_spec)
            if not rooms:
                continue
            min_x = min(float(room["x"]) for room in rooms)
            min_z = min(float(room["y"]) for room in rooms)
            max_x = max(float(room["x"]) + float(room["w"]) for room in rooms)
            max_z = max(float(room["y"]) + float(room["h"]) for room in rooms)
            width, depth = max(1.0, max_x - min_x), max(1.0, max_z - min_z)
            centre_x, centre_z = min_x + width / 2, min_z + depth / 2
            x1, x2 = -width / 2, width / 2
            z1, z2 = -depth / 2, depth / 2
            base = (floor_number - 1) * floor_height
            all_extents.append((x1, x2, z1, z2))
            add_box(f"Floor {floor_number} dollhouse slab", 1, x1 - .14, base - .10, z1 - .14, x2 + .14, base, z2 + .14)
            # Back and left enclosure retain a readable cutaway from the front-right camera.
            add_box(f"Floor {floor_number} back shell wall", 0, x1, base, z2 - wall_thickness, x2, base + wall_height, z2)
            add_box(f"Floor {floor_number} left shell wall", 0, x1, base, z1, x1 + wall_thickness, base + wall_height, z2)
            for room_index, room in enumerate(rooms, start=1):
                raw_x, raw_z = float(room["x"]), float(room["y"])
                room_w, room_d = float(room["w"]), float(room["h"])
                rx1, rz1 = raw_x - centre_x, raw_z - centre_z
                rx2, rz2 = rx1 + room_w, rz1 + room_d
                room_type = str(room.get("type") or "room").split("_", 1)[0]
                room_label = str(room.get("label") or f"Room {room_index}")[:60]
                floor_material = {"living": 2, "dining": 2, "bedroom": 3, "bathroom": 4, "ensuite": 4, "wc": 4, "kitchen": 1}.get(room_type, 1)
                add_box(f"Floor {floor_number} {room_label} floor finish", floor_material, rx1 + .04, base, rz1 + .04, rx2 - .04, base + .045, rz2 - .04)
                # Two legible wall directions create room demarcation while the front and right remain open.
                add_box(f"Floor {floor_number} {room_label} rear room wall", 0, rx1, base, rz2 - wall_thickness, rx2, base + wall_height, rz2)
                add_box(f"Floor {floor_number} {room_label} left room wall", 0, rx1, base, rz1, rx1 + wall_thickness, base + wall_height, rz2)
                self._append_dollhouse_furniture(add_box, floor_number, room_label, room_type, base, rx1, rz1, rx2, rz2)

        if not all_extents:
            raise ValueError("No rooms were available for dollhouse generation")
        overall_x1 = min(extent[0] for extent in all_extents)
        overall_x2 = max(extent[1] for extent in all_extents)
        overall_z1 = min(extent[2] for extent in all_extents)
        overall_z2 = max(extent[3] for extent in all_extents)
        add_box("Dollhouse landscape plinth", 6, overall_x1 - 1.0, -0.22, overall_z1 - 1.0, overall_x2 + 1.0, -0.12, overall_z2 + 1.0)
        self._write_bytes(filepath, self._build_glb_bytes(
            meshes, materials, model_purpose="early-planning cutaway floor-programme visualization only"
        ))

    @staticmethod
    def _append_dollhouse_furniture(add_box: Any, floor_number: int, room_label: str, room_type: str, base: float, x1: float, z1: float, x2: float, z2: float) -> None:
        """Add abstract furniture cues only; they are not fit-out or clearance layouts."""
        width, depth = x2 - x1, z2 - z1
        if width < .9 or depth < .9:
            return
        cx, cz = (x1 + x2) / 2, (z1 + z2) / 2
        prefix = f"Floor {floor_number} {room_label}"
        if room_type == "bedroom":
            add_box(f"{prefix} bed cue", 5, cx - width * .22, base + .05, cz - depth * .20, cx + width * .22, base + .38, cz + depth * .20)
        elif room_type in {"living", "family"}:
            add_box(f"{prefix} sofa cue", 5, cx - width * .25, base + .05, z1 + depth * .15, cx + width * .25, base + .34, z1 + depth * .28)
            add_box(f"{prefix} table cue", 5, cx - width * .10, base + .05, cz - depth * .10, cx + width * .10, base + .24, cz + depth * .10)
        elif room_type in {"kitchen", "dining"}:
            add_box(f"{prefix} counter cue", 5, x1 + width * .18, base + .05, z1 + depth * .18, x1 + width * .82, base + .34, z1 + depth * .32)
        elif room_type in {"bathroom", "ensuite", "wc"}:
            add_box(f"{prefix} fixture cue", 5, cx - width * .16, base + .05, cz - depth * .18, cx + width * .16, base + .22, cz + depth * .18)

    def _generate_fallback_model(self, project_id: str | int) -> str:
        """Write a small, valid one-storey fallback massing GLB."""
        filepath = Path(self.output_dir) / f"model_{self._safe_id(project_id)}_fallback.glb"
        positions, normals, indices = self._box_geometry(-1.0, 0.0, -1.0, 1.0, 2.8, 1.0)
        payload = self._build_glb_bytes([
            {
                "name": "Fallback concept massing",
                "positions": positions,
                "normals": normals,
                "indices": indices,
            }
        ])
        self._write_bytes(filepath, payload)
        return str(filepath)

    @staticmethod
    def _safe_id(value: str | int) -> str:
        return re.sub(r"[^A-Za-z0-9_-]", "", str(value))[:48] or "project"

    def _build_glb(self, spec: dict[str, Any], filepath: Path) -> None:
        """Build a layered modern-tropical concept massing scene.

        Each requested level retains its own robust, closed floor-box mesh. A
        small set of additional typed-box components adds legible plinth, facade
        bands, glazing, entrance, roof/parapet and optional balcony cues. These
        are visual design-study components, not a construction model or a wall,
        window, structural or quantity schedule.
        """
        floors = self._number_as_int(spec.get("floors"), default=1, minimum=1, maximum=self._MAX_FLOORS)
        area = self._number_as_float(
            spec.get("area_sqm"), default=100.0, minimum=self._MIN_AREA_SQM, maximum=self._MAX_AREA_SQM
        )
        floor_height = self._number_as_float(spec.get("ceiling_height"), default=3.2, minimum=2.5, maximum=6.0)
        footprint_area = area / floors
        width = self._positive_sqrt(footprint_area * 1.25)
        depth = footprint_area / width
        half_width, half_depth = width / 2.0, depth / 2.0
        total_height = floors * floor_height
        materials = self._modern_materials()
        meshes: list[dict[str, Any]] = []

        def add_box(name: str, material: int, x1: float, y1: float, z1: float, x2: float, y2: float, z2: float) -> None:
            positions, normals, indices = self._box_geometry(x1, y1, z1, x2, y2, z2)
            meshes.append({"name": name, "material": material, "positions": positions, "normals": normals, "indices": indices})

        # Ground and plinth establish a deliberate base for the concept scene.
        add_box("Landscaped concept plinth", 5, -half_width - 1.0, -0.16, -half_depth - 1.0, half_width + 1.0, -0.02, half_depth + 1.0)
        add_box("Raised entry plinth", 1, -half_width - 0.22, -0.02, -half_depth - 0.22, half_width + 0.22, 0.22, half_depth + 0.22)

        window_depth = 0.10
        facade_z = -half_depth - window_depth / 2 - 0.012
        rear_facade_z = half_depth + window_depth / 2 + 0.012
        for floor_index in range(floors):
            base = floor_index * floor_height + 0.22
            top = base + floor_height
            positions, normals, indices = self._box_geometry(-half_width, base, -half_depth, half_width, top, half_depth)
            meshes.append({
                "name": f"Floor {floor_index + 1} concept massing",
                "material": 0,
                "positions": positions,
                "normals": normals,
                "indices": indices,
            })
            # Horizontal shadow band distinguishes the storeys in standard GLB viewers.
            add_box(f"Floor {floor_index + 1} shadow band", 2, -half_width - 0.05, base - 0.08, -half_depth - 0.06, half_width + 0.05, base + 0.08, half_depth + 0.06)

            # Glazing on both longitudinal faces makes the facade cue legible
            # from the default viewer camera as well as during user orbiting.
            window_y = base + floor_height * 0.46
            window_h = min(1.45, floor_height * 0.44)
            window_w = min(max(0.9, width * 0.18), 2.1)
            for face_name, face_z in (("front", facade_z), ("rear", rear_facade_z)):
                for panel_index, centre_x in enumerate((-width * 0.27, 0.0, width * 0.27), start=1):
                    add_box(
                        f"Floor {floor_index + 1} {face_name} glazing panel {panel_index}",
                        3,
                        centre_x - window_w / 2,
                        window_y - window_h / 2,
                        face_z - window_depth / 2,
                        centre_x + window_w / 2,
                        window_y + window_h / 2,
                        face_z + window_depth / 2,
                    )
            # Side glazing ensures the model remains expressive from all orbit angles.
            side_window_span = min(max(0.9, depth * 0.20), 1.8)
            for face_name, face_x in (("west", -half_width - window_depth / 2 - 0.012), ("east", half_width + window_depth / 2 + 0.012)):
                for panel_index, centre_z in enumerate((-depth * 0.24, depth * 0.24), start=1):
                    add_box(
                        f"Floor {floor_index + 1} {face_name} glazing panel {panel_index}",
                        3,
                        face_x - window_depth / 2,
                        window_y - window_h / 2,
                        centre_z - side_window_span / 2,
                        face_x + window_depth / 2,
                        window_y + window_h / 2,
                        centre_z + side_window_span / 2,
                    )
            # Vertical timber/terracotta screens articulate both long facades.
            accent_w = min(0.7, width * 0.10)
            for face_name, face_z, x1, x2 in (
                ("front", facade_z, half_width - accent_w, half_width - 0.04),
                ("rear", rear_facade_z, -half_width + 0.04, -half_width + accent_w),
            ):
                add_box(
                    f"Floor {floor_index + 1} {face_name} facade screen",
                    4,
                    x1,
                    base + 0.20,
                    face_z - 0.05,
                    x2,
                    top - 0.14,
                    face_z + 0.05,
                )

        # A protected front entry provides human scale on the ground level.
        door_w = min(1.35, width * 0.18)
        door_h = min(2.45, floor_height * 0.72)
        add_box("Recessed front entry", 4, -door_w / 2, 0.23, facade_z - 0.08, door_w / 2, 0.23 + door_h, facade_z + 0.05)
        canopy_depth = min(1.15, depth * 0.18)
        add_box("Entry canopy", 2, -width * 0.22, floor_height * 0.78, -half_depth - canopy_depth, width * 0.22, floor_height * 0.92, -half_depth + 0.10)

        features = {str(item).lower() for item in spec.get("special_features", []) if isinstance(item, str)}
        if floors > 1 or "balcony" in features:
            balcony_level = min(total_height - floor_height + floor_height * 0.12, total_height - 0.35) + 0.22
            balcony_depth = min(1.35, depth * 0.22)
            rail_y1, rail_y2 = balcony_level + 0.16, balcony_level + 0.86
            for face_name, face_z, slab_z1, slab_z2, rail_z1, rail_z2 in (
                ("Front", facade_z, -half_depth - balcony_depth, -half_depth + 0.03, -half_depth - balcony_depth - 0.025, -half_depth - balcony_depth + 0.035),
                ("Rear", rear_facade_z, half_depth - 0.03, half_depth + balcony_depth, half_depth + balcony_depth - 0.035, half_depth + balcony_depth + 0.025),
            ):
                add_box(f"{face_name} balcony slab", 1, -width * 0.30, balcony_level, slab_z1, width * 0.30, balcony_level + 0.16, slab_z2)
                add_box(f"{face_name} balcony glass rail", 3, -width * 0.30, rail_y1, rail_z1, width * 0.30, rail_y2, rail_z2)

        # Flat roof, overhang and parapet give a clear, climate-responsive silhouette.
        roof_base = total_height + 0.22
        add_box("Roof overhang", 2, -half_width - 0.28, roof_base, -half_depth - 0.28, half_width + 0.28, roof_base + 0.18, half_depth + 0.28)
        parapet_h = 0.46
        parapet_t = 0.16
        add_box("Front roof parapet", 2, -half_width - 0.28, roof_base + 0.18, -half_depth - 0.28, half_width + 0.28, roof_base + 0.18 + parapet_h, -half_depth - 0.28 + parapet_t)
        add_box("Rear roof parapet", 2, -half_width - 0.28, roof_base + 0.18, half_depth + 0.12, half_width + 0.28, roof_base + 0.18 + parapet_h, half_depth + 0.28)
        add_box("West roof parapet", 2, -half_width - 0.28, roof_base + 0.18, -half_depth - 0.12, -half_width - 0.12, roof_base + 0.18 + parapet_h, half_depth + 0.12)
        add_box("East roof parapet", 2, half_width + 0.12, roof_base + 0.18, -half_depth - 0.12, half_width + 0.28, roof_base + 0.18 + parapet_h, half_depth + 0.12)

        self._write_bytes(filepath, self._build_glb_bytes(meshes, materials))

    @staticmethod
    def _dollhouse_materials() -> list[dict[str, Any]]:
        """Muted original concept materials for a readable cutaway preview."""
        return [
            {"name": "Warm concept walls", "baseColorFactor": [0.92, 0.91, 0.86, 1.0], "metallicFactor": 0.0, "roughnessFactor": 0.92},
            {"name": "Light oak concept floor", "baseColorFactor": [0.71, 0.57, 0.40, 1.0], "metallicFactor": 0.0, "roughnessFactor": 0.84},
            {"name": "Living concept finish", "baseColorFactor": [0.71, 0.79, 0.71, 1.0], "metallicFactor": 0.0, "roughnessFactor": 0.88},
            {"name": "Bedroom concept finish", "baseColorFactor": [0.67, 0.77, 0.87, 1.0], "metallicFactor": 0.0, "roughnessFactor": 0.88},
            {"name": "Wet-room concept finish", "baseColorFactor": [0.82, 0.88, 0.90, 1.0], "metallicFactor": 0.0, "roughnessFactor": 0.68},
            {"name": "Furniture cue", "baseColorFactor": [0.38, 0.24, 0.15, 1.0], "metallicFactor": 0.0, "roughnessFactor": 0.72},
            {"name": "Landscape base", "baseColorFactor": [0.38, 0.58, 0.37, 1.0], "metallicFactor": 0.0, "roughnessFactor": 1.0},
        ]

    @staticmethod
    def _modern_materials() -> list[dict[str, Any]]:
        """Return restrained concept-only facade materials, without texture assets."""
        return [
            {"name": "Warm render", "baseColorFactor": [0.83, 0.84, 0.79, 1.0], "metallicFactor": 0.0, "roughnessFactor": 0.88},
            {"name": "Sandstone plinth", "baseColorFactor": [0.52, 0.47, 0.40, 1.0], "metallicFactor": 0.0, "roughnessFactor": 0.96},
            {"name": "Charcoal trim", "baseColorFactor": [0.09, 0.14, 0.13, 1.0], "metallicFactor": 0.08, "roughnessFactor": 0.56},
            {"name": "Blue-grey glazing", "baseColorFactor": [0.06, 0.30, 0.40, 1.0], "metallicFactor": 0.16, "roughnessFactor": 0.22},
            {"name": "Timber accent", "baseColorFactor": [0.45, 0.23, 0.12, 1.0], "metallicFactor": 0.0, "roughnessFactor": 0.72},
            {"name": "Landscape base", "baseColorFactor": [0.31, 0.47, 0.31, 1.0], "metallicFactor": 0.0, "roughnessFactor": 1.0},
        ]

    @staticmethod
    def _box_geometry(
        x1: float,
        y1: float,
        z1: float,
        x2: float,
        y2: float,
        z2: float,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return properly wound, per-face box position, normal, and index arrays.

        Vertices are deliberately not shared between faces so that each face has
        a stable outward normal in GLB viewers. Arrays are explicitly typed for
        predictable, portable binary serialization.
        """
        bounds = np.asarray((x1, y1, z1, x2, y2, z2), dtype=np.float64)
        if not np.isfinite(bounds).all() or not (x2 > x1 and y2 > y1 and z2 > z1):
            raise ValueError("Box bounds must be finite and have positive dimensions")

        faces = (
            # front, back, west, east, roof, base — winding points outwards
            ([(x1, y1, z1), (x1, y2, z1), (x2, y2, z1), (x2, y1, z1)], (0.0, 0.0, -1.0)),
            ([(x1, y1, z2), (x2, y1, z2), (x2, y2, z2), (x1, y2, z2)], (0.0, 0.0, 1.0)),
            ([(x1, y1, z1), (x1, y1, z2), (x1, y2, z2), (x1, y2, z1)], (-1.0, 0.0, 0.0)),
            ([(x2, y1, z1), (x2, y2, z1), (x2, y2, z2), (x2, y1, z2)], (1.0, 0.0, 0.0)),
            ([(x1, y2, z1), (x1, y2, z2), (x2, y2, z2), (x2, y2, z1)], (0.0, 1.0, 0.0)),
            ([(x1, y1, z1), (x2, y1, z1), (x2, y1, z2), (x1, y1, z2)], (0.0, -1.0, 0.0)),
        )
        positions = np.asarray([vertex for corners, _ in faces for vertex in corners], dtype=np.float32)
        normals = np.asarray([normal for _, normal in faces for _ in range(4)], dtype=np.float32)
        indices = np.asarray(
            [index for face_index in range(6) for index in (face_index * 4, face_index * 4 + 1, face_index * 4 + 2, face_index * 4, face_index * 4 + 2, face_index * 4 + 3)],
            dtype=np.uint32,
        )
        if positions.shape != (24, 3) or normals.shape != (24, 3) or indices.shape != (36,):
            raise ValueError("Box geometry has an unexpected shape")
        return positions, normals, indices

    def _build_glb_bytes(
        self,
        floor_meshes: list[dict[str, Any]],
        materials: list[dict[str, Any]] | None = None,
        model_purpose: str = "early-planning concept massing only",
    ) -> bytes:
        """Serialize typed geometry arrays to a complete, aligned GLB 2.0 file."""
        if not floor_meshes:
            raise ValueError("At least one floor mesh is required")

        materials = materials or self._modern_materials()
        binary = bytearray()
        buffer_views: list[dict[str, int]] = []
        accessors: list[dict[str, Any]] = []
        meshes: list[dict[str, Any]] = []
        nodes: list[dict[str, Any]] = []

        def append_array(array: np.ndarray, target: int) -> int:
            contiguous = np.ascontiguousarray(array)
            if not np.isfinite(contiguous).all():
                raise ValueError("Geometry contains non-finite values")
            binary.extend(b"\x00" * ((-len(binary)) % 4))
            offset = len(binary)
            binary.extend(contiguous.tobytes(order="C"))
            buffer_views.append({"buffer": 0, "byteOffset": offset, "byteLength": contiguous.nbytes, "target": target})
            return len(buffer_views) - 1

        for floor_index, floor in enumerate(floor_meshes):
            positions = np.asarray(floor["positions"], dtype=np.float32)
            normals = np.asarray(floor["normals"], dtype=np.float32)
            indices = np.asarray(floor["indices"], dtype=np.uint32)
            if positions.ndim != 2 or positions.shape[1] != 3 or normals.shape != positions.shape or indices.ndim != 1:
                raise ValueError("Geometry arrays have invalid dimensions")
            if indices.size == 0 or int(indices.max()) >= len(positions):
                raise ValueError("Geometry indices are outside the vertex range")

            position_view = append_array(positions, 34962)  # ARRAY_BUFFER
            normal_view = append_array(normals, 34962)  # ARRAY_BUFFER
            index_view = append_array(indices, 34963)  # ELEMENT_ARRAY_BUFFER
            position_accessor = len(accessors)
            accessors.append({
                "bufferView": position_view,
                "componentType": 5126,
                "count": len(positions),
                "type": "VEC3",
                "min": positions.min(axis=0).astype(float).tolist(),
                "max": positions.max(axis=0).astype(float).tolist(),
            })
            normal_accessor = len(accessors)
            accessors.append({"bufferView": normal_view, "componentType": 5126, "count": len(normals), "type": "VEC3"})
            index_accessor = len(accessors)
            accessors.append({"bufferView": index_view, "componentType": 5125, "count": len(indices), "type": "SCALAR"})
            name = str(floor.get("name") or f"Floor {floor_index + 1} concept massing")
            material_index = int(floor.get("material", 0))
            if not 0 <= material_index < len(materials):
                raise ValueError("Mesh references an unknown concept material")
            meshes.append({
                "name": name,
                "primitives": [{
                    "attributes": {"POSITION": position_accessor, "NORMAL": normal_accessor},
                    "indices": index_accessor,
                    "material": material_index,
                    "mode": 4,
                }],
            })
            nodes.append({"name": name, "mesh": floor_index})

        document = {
            "asset": {
                "version": "2.0",
                "generator": "Buildwise GH",
                "extras": {
                    "buildwise": {
                        "modelPurpose": model_purpose,
                        "notForConstructionOrPermit": True,
                        "units": "metres",
                    }
                },
            },
            "scene": 0,
            "scenes": [{"name": "Buildwise concept massing", "nodes": list(range(len(nodes)))}],
            "nodes": nodes,
            "meshes": meshes,
            "materials": [{
                "name": str(material["name"]),
                "pbrMetallicRoughness": {
                    "baseColorFactor": material["baseColorFactor"],
                    "metallicFactor": material["metallicFactor"],
                    "roughnessFactor": material["roughnessFactor"],
                },
                **({"alphaMode": "BLEND", "doubleSided": True} if material["baseColorFactor"][3] < 1.0 else {}),
            } for material in materials],
            "accessors": accessors,
            "bufferViews": buffer_views,
            "buffers": [{"byteLength": len(binary)}],
        }
        json_chunk = json.dumps(document, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        json_chunk += b" " * ((-len(json_chunk)) % 4)
        binary_chunk = bytes(binary) + b"\x00" * ((-len(binary)) % 4)
        total_length = 12 + 8 + len(json_chunk) + 8 + len(binary_chunk)
        if total_length > 0xFFFFFFFF:
            raise ValueError("GLB exceeds the glTF 2.0 file-size limit")
        return (
            struct.pack("<4sII", b"glTF", 2, total_length)
            + struct.pack("<II", len(json_chunk), 0x4E4F534A)
            + json_chunk
            + struct.pack("<II", len(binary_chunk), 0x004E4942)
            + binary_chunk
        )

    @staticmethod
    def _write_bytes(filepath: Path, payload: bytes) -> None:
        """Atomically replace an artifact only after its full GLB is prepared."""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = filepath.with_suffix(f"{filepath.suffix}.tmp")
        try:
            temporary_path.write_bytes(payload)
            os.replace(temporary_path, filepath)
        finally:
            if temporary_path.exists():
                temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _number_as_int(value: Any, default: int, minimum: int, maximum: int) -> int:
        try:
            return min(max(int(value), minimum), maximum)
        except (TypeError, ValueError, OverflowError):
            return default

    @staticmethod
    def _number_as_float(value: Any, default: float, minimum: float, maximum: float) -> float:
        try:
            parsed = float(value)
            if not np.isfinite(parsed):
                return default
            return min(max(parsed, minimum), maximum)
        except (TypeError, ValueError, OverflowError):
            return default

    @staticmethod
    def _positive_sqrt(value: float) -> float:
        if not np.isfinite(value) or value <= 0:
            raise ValueError("Building footprint must be positive")
        return float(np.sqrt(value))
