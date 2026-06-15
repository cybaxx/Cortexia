#!/usr/bin/env python3
"""Export fsaverage5 cortical surface + subcortical markers as a Three.js-compatible GLB.

Generates:
- Left + right pial surface meshes with per-vertex Schaefer network colors
- Subcortical sphere markers (amygdala, hippocampus) at MNI coordinates
- Merged into a single GLB with vertex color attributes

Usage:
    source .venv/bin/activate
    python scripts/export_brain_mesh.py [--output frontend/public/brain.glb]
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

import numpy as np

BACKEND_DIR = Path(__file__).resolve().parent.parent

# ROI colors (RGBA normalized) — matching the frontend's existing color scheme
ROI_COLORS: dict[str, tuple[float, float, float, float]] = {
    "fear_salience": (0.91, 0.52, 0.42, 1.0),     # coral (matches rejected color)
    "deliberation": (0.29, 0.69, 0.82, 1.0),        # cyan-blue (analytical)
    "social_default": (0.60, 0.75, 0.38, 1.0),       # green (social)
    "reward_limbic": (0.96, 0.72, 0.26, 1.0),        # amber (reward)
    "attention": (0.55, 0.65, 0.90, 1.0),            # light blue (vigilance)
    "action_motor": (0.78, 0.55, 0.85, 1.0),         # purple (motor)
    "subcortical": (0.95, 0.35, 0.35, 1.0),          # red (amygdala/hippocampus)
    "unassigned": (0.25, 0.25, 0.30, 0.15),          # dim gray (rest of brain)
}

# Schaefer network → ROI mapping (from tribe_neural/constants.py)
NETWORK_PARCELLATION: dict[str, str] = {
    "_SalVentAttn_": "fear_salience",
    "_Cont_": "deliberation",
    "_Default_": "social_default",
    "_Limbic_": "reward_limbic",
    "_DorsAttn_": "attention",
    "_SomMot_": "action_motor",
}

# Approximate MNI → fsaverage surface vertex indices for subcortical highlights
# These are rough approximations for visual markers
SUBCORTICAL_SPHERES = [
    {"name": "Left Amygdala", "mni": [-23, -5, -20], "radius": 4.0},
    {"name": "Right Amygdala", "mni": [23, -5, -20], "radius": 4.0},
    {"name": "Left Hippocampus", "mni": [-26, -20, -14], "radius": 4.5},
    {"name": "Right Hippocampus", "mni": [26, -20, -14], "radius": 4.5},
]


def fetch_surfaces():
    """Load fsaverage5 pial surfaces and Schaefer atlas."""
    from nilearn import datasets
    from nilearn.surface import vol_to_surf

    data_dir = str(BACKEND_DIR / "tribe_data" / "nilearn")
    Path(data_dir).mkdir(parents=True, exist_ok=True)

    print("Fetching fsaverage5 surfaces...")
    fsav = datasets.fetch_surf_fsaverage("fsaverage5", data_dir=data_dir)

    print("Fetching Schaefer 400-parcel atlas...")
    schaefer = datasets.fetch_atlas_schaefer_2018(
        n_rois=400, resolution_mm=1, data_dir=data_dir,
    )

    print("Projecting Schaefer atlas to surface...")
    sch_lh = np.rint(vol_to_surf(schaefer["maps"], fsav["pial_left"])).astype(int)
    sch_rh = np.rint(vol_to_surf(schaefer["maps"], fsav["pial_right"])).astype(int)

    return fsav, schaefer, sch_lh, sch_rh


def load_surface_gifti(path: str) -> tuple[np.ndarray, np.ndarray]:
    """Load GIFTI surface file, return (vertices N×3, faces M×3)."""
    import nibabel as nib

    img = nib.load(path)
    verts = img.darrays[0].data  # N×3 float
    faces = img.darrays[1].data  # M×3 int
    return verts.astype(np.float32), faces.astype(np.int32)


def build_vertex_colors(
    sch_labels: np.ndarray,
    schaefer_names: list[str],
) -> np.ndarray:
    """Map each vertex to an RGBA color based on Schaefer network membership."""
    num_verts = len(sch_labels)
    colors = np.tile(np.array(ROI_COLORS["unassigned"][:3]), (num_verts, 1))

    for idx, name in enumerate(schaefer_names):
        network = None
        for key, roi in NETWORK_PARCELLATION.items():
            if key in str(name):
                network = roi
                break
        if network:
            mask = sch_labels == idx
            colors[mask] = ROI_COLORS[network][:3]

    return colors.astype(np.float32)


def write_glb(
    path: str,
    lh_verts: np.ndarray,
    lh_faces: np.ndarray,
    lh_colors: np.ndarray,
    rh_verts: np.ndarray,
    rh_faces: np.ndarray,
    rh_colors: np.ndarray,
    spheres: list[dict],
):
    """Write a GLB file with two meshes (LH + RH) + sphere markers.

    Uses a minimal binary GLTF/GLB writer. Three.js can load this directly.
    """
    # Merge hemispheres: offset right face indices by left vertex count
    all_verts = np.vstack([lh_verts, rh_verts])
    rh_faces_offset = rh_faces + len(lh_verts)
    all_faces = np.vstack([lh_faces, rh_faces_offset])
    all_colors = np.vstack([lh_colors, rh_colors])

    # Build sphere meshes at subcortical locations
    sphere_verts_list = [all_verts]
    sphere_faces_list = [all_faces]
    sphere_colors_list = [all_colors]
    sphere_mesh_names = ["cortex"]
    sphere_mesh_ranges = [(0, len(all_verts), 0, len(all_faces))]

    for s in spheres:
        sv, sf = _make_sphere(
            np.array(s["mni"], dtype=np.float32),
            s["radius"],
            ROI_COLORS["subcortical"][:3],
        )
        v_offset = sum(len(v) for v in sphere_verts_list)
        f_offset = sum(len(f) for f in sphere_faces_list)
        sphere_verts_list.append(sv)
        sphere_faces_list.append(sf + v_offset)
        sphere_colors_list.append(np.tile(np.array(ROI_COLORS["subcortical"][:3]), (len(sv), 1)).astype(np.float32))
        sphere_mesh_names.append(s["name"])
        sphere_mesh_ranges.append((v_offset, v_offset + len(sv), f_offset, f_offset + len(sf)))

    final_verts = np.vstack(sphere_verts_list)
    final_faces = np.vstack(sphere_faces_list)
    final_colors = np.vstack(sphere_colors_list)

    # Pack vertices: [x, y, z, r, g, b] interleaved
    vertex_data = np.hstack([
        final_verts,
        final_colors,
    ]).astype(np.float32).tobytes()

    # Flatten faces to uint32
    face_data = final_faces.astype(np.uint32).tobytes()

    # Write minimal GLB
    _write_glb_file(path, vertex_data, face_data, len(final_verts), len(final_faces),
                    final_verts.min(axis=0), final_verts.max(axis=0))

    print(f"Wrote {path}")
    print(f"  Vertices: {len(final_verts):,}")
    print(f"  Triangles: {len(final_faces):,}")
    print(f"  Bounds: {final_verts.min(axis=0)} → {final_verts.max(axis=0)}")


def _make_sphere(center: np.ndarray, radius: float, color: tuple, segments: int = 16):
    """Create a UV sphere mesh at the given center."""
    verts = []
    faces = []
    for i in range(segments):
        lat0 = np.pi * (-0.5 + i / segments)
        lat1 = np.pi * (-0.5 + (i + 1) / segments)
        for j in range(segments * 2):
            lon0 = 2 * np.pi * j / (segments * 2)
            lon1 = 2 * np.pi * (j + 1) / (segments * 2)

            v0 = center + radius * np.array([
                np.cos(lat0) * np.cos(lon0),
                np.sin(lat0),
                np.cos(lat0) * np.sin(lon0),
            ])
            v1 = center + radius * np.array([
                np.cos(lat1) * np.cos(lon0),
                np.sin(lat1),
                np.cos(lat1) * np.sin(lon0),
            ])
            v2 = center + radius * np.array([
                np.cos(lat0) * np.cos(lon1),
                np.sin(lat0),
                np.cos(lat0) * np.sin(lon1),
            ])
            v3 = center + radius * np.array([
                np.cos(lat1) * np.cos(lon1),
                np.sin(lat1),
                np.cos(lat1) * np.sin(lon1),
            ])
            idx = len(verts)
            verts.extend([v0, v1, v2, v3])
            faces.extend([[idx, idx+2, idx+1], [idx+1, idx+2, idx+3]])

    return np.array(verts, dtype=np.float32), np.array(faces, dtype=np.int32)


def _write_glb_file(
    path: str,
    vertex_data: bytes,
    index_data: bytes,
    num_verts: int,
    num_faces: int,
    vmin: np.ndarray,
    vmax: np.ndarray,
):
    """Write a minimal GLB (binary glTF 2.0) file.

    Layout: 12-byte header + JSON chunk + BIN chunk.
    """
    # Track byte offsets
    json_str = json.dumps({
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{
            "primitives": [{
                "attributes": {
                    "POSITION": 0,
                    "COLOR_0": 1,
                },
                "indices": 2,
                "mode": 4,  # TRIANGLES
            }],
        }],
        "accessors": [
            {  # 0: POSITION
                "bufferView": 0,
                "componentType": 5126,  # FLOAT
                "count": num_verts,
                "type": "VEC3",
                "max": vmax.tolist(),
                "min": vmin.tolist(),
            },
            {  # 1: COLOR_0
                "bufferView": 1,
                "componentType": 5126,
                "count": num_verts,
                "type": "VEC3",
            },
            {  # 2: indices
                "bufferView": 2,
                "componentType": 5125,  # UNSIGNED_INT
                "count": num_faces * 3,
                "type": "SCALAR",
            },
        ],
        "bufferViews": [
            {  # 0: position interleaved data
                "buffer": 0,
                "byteOffset": 0,
                "byteLength": len(vertex_data),
                "byteStride": 24,  # 6 floats × 4 bytes = x,y,z,r,g,b
            },
            {  # 1: color — same buffer, offset by 12 bytes (skip xyz)
                "buffer": 0,
                "byteOffset": 12,
                "byteLength": len(vertex_data),
                "byteStride": 24,
            },
            {  # 2: indices
                "buffer": 0,
                "byteOffset": len(vertex_data),
                "byteLength": len(index_data),
            },
        ],
        "buffers": [{
            "byteLength": len(vertex_data) + len(index_data),
        }],
    }, separators=(",", ":"))

    # Pad JSON to 4-byte alignment with space (0x20)
    json_bytes = json_str.encode("utf-8")
    while len(json_bytes) % 4 != 0:
        json_bytes += b" "

    # GLB header: magic, version, total length
    total_len = 12 + 8 + len(json_bytes) + 8 + len(vertex_data) + len(index_data)
    header = struct.pack("<I", 0x46546C67)  # "glTF" magic
    header += struct.pack("<I", 2)            # version
    header += struct.pack("<I", total_len)

    # JSON chunk
    json_chunk = struct.pack("<I", len(json_bytes))
    json_chunk += struct.pack("<I", 0x4E4F534A)  # "JSON"
    json_chunk += json_bytes

    # BIN chunk
    bin_data = vertex_data + index_data
    bin_chunk = struct.pack("<I", len(bin_data))
    bin_chunk += struct.pack("<I", 0x004E4942)  # "BIN\0"
    bin_chunk += bin_data

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(header)
        f.write(json_chunk)
        f.write(bin_chunk)


def main():
    parser = argparse.ArgumentParser(description="Export brain mesh as GLB for Three.js")
    parser.add_argument(
        "--output",
        default=str(BACKEND_DIR.parent / "frontend" / "public" / "brain.glb"),
        help="Output GLB path",
    )
    parser.add_argument("--decimate", type=int, default=0,
                        help="Target vertex count for decimation (0 = no decimation)")
    args = parser.parse_args()

    print("Loading surfaces...")
    fsav, schaefer, sch_lh, sch_rh = fetch_surfaces()

    print("Loading left pial surface...")
    lh_verts, lh_faces = load_surface_gifti(fsav["pial_left"])
    print(f"  LH: {len(lh_verts):,} vertices, {len(lh_faces):,} faces")

    print("Loading right pial surface...")
    rh_verts, rh_faces = load_surface_gifti(fsav["pial_right"])
    print(f"  RH: {len(rh_verts):,} vertices, {len(rh_faces):,} faces")

    print("Building vertex colors from Schaefer atlas...")
    sch_names = schaefer["labels"]
    lh_colors = build_vertex_colors(sch_lh, sch_names)
    rh_colors = build_vertex_colors(sch_rh, sch_names)

    if args.decimate > 0 and args.decimate < len(lh_verts):
        print(f"Decimating from {len(lh_verts):,} to ~{args.decimate:,} vertices...")
        lh_verts, lh_faces, lh_colors = _decimate(lh_verts, lh_faces, lh_colors, args.decimate)
        rh_verts, rh_faces, rh_colors = _decimate(rh_verts, rh_faces, rh_colors, args.decimate)

    # Convert MNI sphere coordinates to approximate fsaverage surface space
    # fsaverage5 origin is roughly centered, we keep spheres at MNI coords
    # since fsaverage is in MNI305 space (similar to MNI)

    output_path = args.output
    write_glb(output_path, lh_verts, lh_faces, lh_colors, rh_verts, rh_faces, rh_colors, SUBCORTICAL_SPHERES)

    print(f"\nDone! Mesh exported to {output_path}")
    print("The GLB includes:")
    print("  - Left + right cortical surface with Schaefer network vertex colors")
    print("  - Subcortical sphere markers for amygdala and hippocampus")
    print("  - Ready for Three.js / React Three Fiber loading")


def _decimate(
    verts: np.ndarray,
    faces: np.ndarray,
    colors: np.ndarray,
    target: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Simple vertex decimation by merging nearest neighbors."""
    step = max(1, len(verts) // target)
    # Keep every Nth vertex, remap faces
    keep_idx = np.arange(0, len(verts), step)
    keep_set = set(keep_idx)

    # Build old→new vertex index map
    old_to_new = {old: new for new, old in enumerate(keep_idx)}
    old_to_new_map = np.full(len(verts), -1, dtype=np.int32)
    old_to_new_map[keep_idx] = np.arange(len(keep_idx))

    # Filter faces where all vertices are kept
    valid_faces = []
    for face in faces:
        if all(v in keep_set for v in face):
            valid_faces.append([old_to_new_map[v] for v in face])

    new_verts = verts[keep_idx]
    new_colors = colors[keep_idx]
    new_faces = np.array(valid_faces, dtype=np.int32)

    print(f"  Decimated: {len(verts):,} → {len(new_verts):,} vertices, "
          f"{len(faces):,} → {len(new_faces):,} faces")
    return new_verts, new_faces, new_colors


if __name__ == "__main__":
    main()
