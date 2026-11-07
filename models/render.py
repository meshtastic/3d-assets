#!/usr/bin/env python3
# /// script
# requires-python = "==3.13.*"  # one Python everywhere, so every machine builds the same models
# dependencies = ["trimesh>=4.0", "numpy", "pillow", "pygltflib"]
# ///
"""Render a device model's GLB to a PNG for review, on any platform.

Orthographic, with a key light over the viewer's shoulder and an ambient fill,
on a light gray background, like the old SceneKit render.swift.

usage: render.py <in.glb> <out.png> [size] [three-quarter|front|side|back|back-three-quarter]
"""

import sys

import numpy as np
import trimesh
from PIL import Image

VIEWS = {
    "front": (0, 0, 1),
    "side": (1, 0, 0),
    "back": (0, 0, -1),
    "back-three-quarter": (-0.55, 0.25, -1.0),
    "three-quarter": (0.55, 0.25, 1.0),
}
BACKGROUND = 0.93
KEY, FILL = 0.55, 0.45
SUPERSAMPLE = 3


def triangles(path):
    """World-space triangles and their linear base colors from every mesh in the GLB."""
    scene = trimesh.load(path, force="scene")
    tris, colors = [], []
    for name in scene.graph.nodes_geometry:
        transform, geom_name = scene.graph[name]
        mesh = scene.geometry[geom_name]
        v = trimesh.transformations.transform_points(mesh.vertices, transform)
        color = (0.8, 0.8, 0.8)
        material = getattr(mesh.visual, "material", None)
        factor = getattr(material, "baseColorFactor", None)
        if factor is not None:
            color = np.asarray(factor[:3], dtype=float)
            if color.max() > 1:
                color = color / 255.0
        tris.append(v[mesh.faces])
        colors.append(np.tile(color, (len(mesh.faces), 1)))
    return np.concatenate(tris), np.concatenate(colors)


def basis(direction):
    """Camera right, up and forward (toward the model) for a view direction."""
    back = np.asarray(direction, dtype=float)
    back /= np.linalg.norm(back)
    up = np.array([0.0, 1.0, 0.0])
    right = np.cross(up, back)
    if np.linalg.norm(right) < 1e-6:
        right = np.array([1.0, 0.0, 0.0])
    right /= np.linalg.norm(right)
    return right, np.cross(back, right), -back


def render(path, out, size=600, view="three-quarter"):
    tris, colors = triangles(path)
    lo, hi = tris.reshape(-1, 3).min(0), tris.reshape(-1, 3).max(0)
    center, extent = (lo + hi) / 2, (hi - lo).max()
    right, up, forward = basis(VIEWS.get(view, VIEWS["three-quarter"]))

    # Flat shading: the key comes from over the viewer's shoulder whichever way the camera faces.
    normals = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    lengths = np.linalg.norm(normals, axis=1)
    keep = lengths > 1e-14
    tris, colors, normals = tris[keep], colors[keep], normals[keep] / lengths[keep, None]
    light = -forward + 0.6 * up + 0.5 * right
    light /= np.linalg.norm(light)
    lambert = np.abs(normals @ light)
    shade = np.clip(colors * (FILL + KEY * lambert)[:, None], 0, 1)
    shade = shade ** (1 / 2.2)  # linear to sRGB, near enough for review

    px = size * SUPERSAMPLE
    scale = px / (extent * 1.24)
    rel = tris - center
    sx = rel @ right * scale + px / 2
    sy = px / 2 - rel @ up * scale
    depth = rel @ forward

    image = np.full((px, px, 3), BACKGROUND)
    zbuf = np.full((px, px), np.inf)
    for i in range(len(tris)):
        x, y, z = sx[i], sy[i], depth[i]
        x0, x1 = max(int(np.floor(x.min())), 0), min(int(np.ceil(x.max())), px - 1)
        y0, y1 = max(int(np.floor(y.min())), 0), min(int(np.ceil(y.max())), px - 1)
        if x0 > x1 or y0 > y1:
            continue
        area = (x[1] - x[0]) * (y[2] - y[0]) - (x[2] - x[0]) * (y[1] - y[0])
        if abs(area) < 1e-12:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        w0 = ((x[1] - gx) * (y[2] - gy) - (x[2] - gx) * (y[1] - gy)) / area
        w1 = ((x[2] - gx) * (y[0] - gy) - (x[0] - gx) * (y[2] - gy)) / area
        w2 = 1 - w0 - w1
        inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not inside.any():
            continue
        zz = w0 * z[0] + w1 * z[1] + w2 * z[2]
        region = zbuf[y0:y1 + 1, x0:x1 + 1]
        nearer = inside & (zz < region)
        region[nearer] = zz[nearer]
        image[y0:y1 + 1, x0:x1 + 1][nearer] = shade[i]

    Image.fromarray((image * 255).astype(np.uint8)).resize((size, size), Image.LANCZOS).save(out)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__.strip().splitlines()[-1])
    render(sys.argv[1], sys.argv[2],
           int(sys.argv[3]) if len(sys.argv) > 3 else 600,
           sys.argv[4] if len(sys.argv) > 4 else "three-quarter")
