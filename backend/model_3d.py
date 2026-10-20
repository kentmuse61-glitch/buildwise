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
        """Build one correctly oriented closed box for every requested floor.

        Each floor is a separate named mesh/node in the resulting GLB. Keeping
        the floors distinct makes level changes legible in standard GLB viewers
        while retaining a compact and robust concept-massing representation.
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

        floor_meshes: list[dict[str, Any]] = []
        for floor_index in range(floors):
            base = floor_index * floor_height
            positions, normals, indices = self._box_geometry(
                -half_width,
                base,
                -half_depth,
                half_width,
                base + floor_height,
                half_depth,
            )
            floor_meshes.append({
                "name": f"Floor {floor_index + 1} concept massing",
                "positions": positions,
                "normals": normals,
                "indices": indices,
            })

        self._write_bytes(filepath, self._build_glb_bytes(floor_meshes))

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

    def _build_glb_bytes(self, floor_meshes: list[dict[str, Any]]) -> bytes:
        """Serialize typed geometry arrays to a complete, aligned GLB 2.0 file."""
        if not floor_meshes:
            raise ValueError("At least one floor mesh is required")

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
            meshes.append({
                "name": name,
                "primitives": [{
                    "attributes": {"POSITION": position_accessor, "NORMAL": normal_accessor},
                    "indices": index_accessor,
                    "material": 0,
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
                        "modelPurpose": "early-planning concept massing only",
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
                "name": "ConceptMassingMaterial",
                "pbrMetallicRoughness": {
                    "baseColorFactor": [0.72, 0.79, 0.70, 1.0],
                    "metallicFactor": 0.0,
                    "roughnessFactor": 0.82,
                },
            }],
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
