"""Create a dependency-light glTF 2.0 binary massing model (GLB)."""

from __future__ import annotations

import json
import os
import re
import struct
from typing import Any


class Model3DGenerator:
    def __init__(self, output_dir: str = "output") -> None:
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate_model(self, spec: dict[str, Any], project_id: str | int) -> str:
        safe_id = re.sub(r"[^A-Za-z0-9_-]", "", str(project_id))[:48] or "project"
        filepath = os.path.join(self.output_dir, f"model_{safe_id}.glb")
        self._build_glb(spec, filepath)
        return filepath

    def _build_glb(self, spec: dict[str, Any], filepath: str) -> None:
        floors = min(max(int(spec.get("floors", 1)), 1), 50)
        total_area = max(20.0, float(spec.get("area_sqm", 100.0)))
        footprint_area = total_area / floors
        width = (footprint_area * 1.25) ** 0.5
        depth = footprint_area / width
        height = floors * 3.2
        half_w, half_d = width / 2, depth / 2

        faces = [
            ([(-half_w, 0, -half_d), (-half_w, height, -half_d), (half_w, height, -half_d), (half_w, 0, -half_d)], (0, 0, -1)),
            ([(-half_w, 0, half_d), (half_w, 0, half_d), (half_w, height, half_d), (-half_w, height, half_d)], (0, 0, 1)),
            ([(-half_w, 0, -half_d), (-half_w, 0, half_d), (-half_w, height, half_d), (-half_w, height, -half_d)], (-1, 0, 0)),
            ([(half_w, 0, -half_d), (half_w, height, -half_d), (half_w, height, half_d), (half_w, 0, half_d)], (1, 0, 0)),
            ([(-half_w, height, -half_d), (-half_w, height, half_d), (half_w, height, half_d), (half_w, height, -half_d)], (0, 1, 0)),
            ([(-half_w, 0, -half_d), (half_w, 0, -half_d), (half_w, 0, half_d), (-half_w, 0, half_d)], (0, -1, 0)),
        ]

        positions: list[tuple[float, float, float]] = []
        normals: list[tuple[float, float, float]] = []
        indices: list[int] = []
        for corners, normal in faces:
            base = len(positions)
            positions.extend(corners)
            normals.extend([normal] * 4)
            indices.extend((base, base + 1, base + 2, base, base + 2, base + 3))

        position_bytes = struct.pack("<" + "f" * (len(positions) * 3), *(v for xyz in positions for v in xyz))
        normal_bytes = struct.pack("<" + "f" * (len(normals) * 3), *(v for xyz in normals for v in xyz))
        index_bytes = struct.pack("<" + "H" * len(indices), *indices)
        binary = position_bytes + normal_bytes + index_bytes

        xs = [point[0] for point in positions]
        ys = [point[1] for point in positions]
        zs = [point[2] for point in positions]
        json_chunk = {
            "asset": {"version": "2.0", "generator": "Construction AI Ghana"},
            "scene": 0,
            "scenes": [{"nodes": [0]}],
            "nodes": [{"mesh": 0, "name": f"ConceptBuilding_{floors}F"}],
            "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1}, "indices": 2, "material": 0, "mode": 4}]}],
            "materials": [{
                "name": "Concept exterior",
                "doubleSided": True,
                "pbrMetallicRoughness": {
                    "baseColorFactor": [0.78, 0.72, 0.60, 1.0],
                    "metallicFactor": 0.0,
                    "roughnessFactor": 0.88,
                },
            }],
            "accessors": [
                {"bufferView": 0, "componentType": 5126, "count": len(positions), "type": "VEC3", "min": [min(xs), min(ys), min(zs)], "max": [max(xs), max(ys), max(zs)]},
                {"bufferView": 1, "componentType": 5126, "count": len(normals), "type": "VEC3"},
                {"bufferView": 2, "componentType": 5123, "count": len(indices), "type": "SCALAR", "min": [min(indices)], "max": [max(indices)]},
            ],
            "bufferViews": [
                {"buffer": 0, "byteOffset": 0, "byteLength": len(position_bytes), "target": 34962},
                {"buffer": 0, "byteOffset": len(position_bytes), "byteLength": len(normal_bytes), "target": 34962},
                {"buffer": 0, "byteOffset": len(position_bytes) + len(normal_bytes), "byteLength": len(index_bytes), "target": 34963},
            ],
            "buffers": [{"byteLength": len(binary)}],
        }
        json_bytes = json.dumps(json_chunk, separators=(",", ":")).encode("utf-8")
        json_bytes += b" " * ((-len(json_bytes)) % 4)
        binary += b"\x00" * ((-len(binary)) % 4)
        total_length = 12 + 8 + len(json_bytes) + 8 + len(binary)

        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        with open(filepath, "wb") as output:
            output.write(struct.pack("<4sII", b"glTF", 2, total_length))
            output.write(struct.pack("<II", len(json_bytes), 0x4E4F534A))
            output.write(json_bytes)
            output.write(struct.pack("<II", len(binary), 0x004E4942))
            output.write(binary)
