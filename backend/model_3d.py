"""Generate robust glTF 2.0 binary (GLB) concept massing models."""

from __future__ import annotations

import json
import logging
import os
import re
import struct
from typing import Any

logger = logging.getLogger(__name__)


class Model3DGenerator:
    """Generate a lightweight, dependency-free GLB model from a building brief."""

    def __init__(self, output_dir: str = "output") -> None:
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate_model(self, spec: dict[str, Any], project_id: str | int) -> str:
        """Write a GLB model, using a cube fallback if model generation fails."""
        safe_id = self._safe_id(project_id)
        filepath = os.path.join(self.output_dir, f"model_{safe_id}.glb")
        try:
            self._build_glb(spec, filepath)
            return filepath
        except (OSError, TypeError, ValueError, ArithmeticError, struct.error) as error:
            logger.exception("3D model generation failed for project %s: %s", safe_id, error)
            return self._generate_fallback_model(safe_id)

    def _generate_fallback_model(self, project_id: str | int) -> str:
        """Write a valid one-storey cube model when project geometry is invalid."""
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
        floors = self._number_as_int(spec.get("floors"), default=1, minimum=1, maximum=50)
        area = self._number_as_float(spec.get("area_sqm"), default=100.0, minimum=20.0, maximum=1_000_000.0)
        ceiling_height = self._number_as_float(spec.get("ceiling_height"), default=3.2, minimum=2.5, maximum=6.0)
        footprint_area = area / floors
        width = math_sqrt(footprint_area * 1.25)
        depth = footprint_area / width
        half_width, half_depth = width / 2, depth / 2

        positions: list[tuple[float, float, float]] = []
        normals: list[tuple[float, float, float]] = []
        indices: list[int] = []
        # A box per floor preserves level lines in common GLB viewers while
        # remaining small enough for immediate download.
        for floor in range(floors):
            base = floor * ceiling_height
            self._append_box(positions, normals, indices, -half_width, base, -half_depth, half_width, base + ceiling_height, half_depth)
        if not positions or not indices:
            raise ValueError("No model geometry was generated")
        self._write_glb_file(filepath, positions, normals, indices, f"ConceptBuilding_{floors}F")

    @staticmethod
    def _append_box(
        positions: list[tuple[float, float, float]],
        normals: list[tuple[float, float, float]],
        indices: list[int],
        x1: float, y1: float, z1: float, x2: float, y2: float, z2: float,
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

    def _write_glb_file(
        self,
        filepath: str,
        positions: list[tuple[float, float, float]],
        normals: list[tuple[float, float, float]],
        indices: list[int],
        model_name: str,
    ) -> None:
        """Write a standards-compliant GLB with positions, normals and material."""
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
    """Keep the module dependency-free while validating positive geometry."""
    if value <= 0:
        raise ValueError("Building footprint must be positive")
    return value ** 0.5
