"""Build the mock (a rough 3D shape to judge form and size).
A person makes the final model in Fusion or similar (docs/handoff.md). The STEP files can be the starting point.

Output
  out/<ver>/parts/*.stl         … mesh per part (for renders, sections, and the review page)
  out/<ver>/scene.json          … part names, colors, opacity (read by render_model.py and slices.py)
  out/<ver>/step/NN_<key>.step  … solid per part (when CadQuery is installed; skip with --no-step)
  out/<ver>/step/assembly_<ver>.step … all parts in one file with names and colors (opens in Fusion as one component per part)
  out/<ver>/step/index.json     … list of the STEP files (used to show them in the "Export" section of the review page)
Usage: python3 tools/mock.py [v03] [--no-step]

Template example: a box with a PLA frame between two acrylic plates, holding an object inside.
  Rewrite the inside of build() for your own shape. Draw shapes with the tools in geom.py (one definition gives both STL and STEP).
  Add a part as (display name, shape, color, opacity, ASCII key[, options]). The key is used for the file name and the STEP part name
  (ASCII STEP part names do not get garbled in Fusion and other tools). Options:
  {"print": False} (parts that are not 3D printed: contents, off-the-shelf parts, laser-cut plates), {"up": "-z"} (print orientation).
  For 3D-printed parts, downward faces that may need support (shallower than overhang_deg) are listed as warnings automatically.
  notes can hold text warnings, and also question candidates for things the user should decide (on the review page they become questions answered with buttons):
    {"q": "Add a retainer?", "type": "yesno", "why": "The can falls out when upside down"}
    {"q": "Lug position", "type": "options", "options": ["Top edge", {"label": "Middle", "note": "extra detail"}], "why": "…"}
  Outlines: RRect (rounded rectangle), Circle (circle), Poly (polygon). Solids: slab (extrusion + holes), cyl (cylinder), box (cuboid).
  Combine: + add, - subtract, & intersect, .translate(x, y, z). Do not model fine details (fillets, threads, etc.).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import common  # noqa: E402
from geom import Circle, RRect, box, cyl, slab  # noqa: E402


# ---------- Rewrite this for your own shape
def build(prm):
    P, col = prm.P, prm.meta.get("colors", {})
    parts, notes = [], []
    W, D = P.outer_w, P.outer_d
    holes_xy = [(sx * (W / 2 - P.hole_inset), sy * (D / 2 - P.hole_inset)) for sx in (-1, 1) for sy in (-1, 1)]
    holes = [Circle(P.screw_clear, x, y) for x, y in holes_xy]
    outer = RRect(W, D, P.corner_r)

    z = 0.0
    parts.append(("Bottom plate", slab(outer, z, P.t_bottom, holes), col.get("plate", "#bcd6e4"), 0.75, "bottom_plate", {"print": False}))
    z += P.t_bottom

    inner = RRect(W - 2 * P.wall, D - 2 * P.wall, max(0.5, P.corner_r - P.wall))
    frame = slab(outer, z, P.frame_h, [inner] + holes)
    # If it does not fit the build area, split it into left and right (for the visual check only; the joint shape is decided during modeling)
    if W > P.bed_x or D > P.bed_y:
        right = box(0, -D, z - 1, W, 2 * D, P.frame_h + 2)
        parts.append(("Frame (left)", frame - right, col.get("frame", "#d9d4cb"), 1.0, "frame_left"))
        parts.append(("Frame (right)", frame & right, col.get("frame", "#d9d4cb"), 1.0, "frame_right"))
        notes.append(f"The frame {W:g}×{D:g} is larger than the printer area {P.bed_x:g}×{P.bed_y:g}, so it is shown split into left and right")
    else:
        parts.append(("Frame", frame, col.get("frame", "#d9d4cb"), 1.0, "frame"))

    parts.append(("Contents", slab(RRect(P.content_w, P.content_d, 2), z + 1.0, P.content_h), col.get("content", "#2b2f2d"), 1.0, "content",
                  {"print": False}))
    if P.content_w > W - 2 * P.wall or P.content_d > D - 2 * P.wall:
        notes.append("The contents are larger than the inside of the frame")
    if 1.0 + P.content_h > P.frame_h:
        notes.append("The contents are taller than the frame (they hit the top plate)")
    if P.hole_inset < 1.5 * P.screw_clear:
        notes.append(f"The screw holes are close to the edge ({P.hole_inset:g}mm). For acrylic, keep at least 1.5× the hole diameter = {1.5 * P.screw_clear:.1f}mm (ACRYLITE)")
    if hasattr(P, "boss_d") and P.wall < P.boss_d:
        notes.append(f"The wall thickness {P.wall:g}mm is thinner than the insert boss diameter {P.boss_d:g}mm")
    z += P.frame_h

    parts.append(("Top plate", slab(outer, z, P.t_top, [RRect(P.window_w, P.window_d, 4)] + holes),
                  col.get("plate", "#bcd6e4"), 0.6, "top_plate", {"print": False}))
    z += P.t_top

    heads = None
    for x, y in holes_xy:
        c = cyl(x, y, 5.5, z, 2.0)
        heads = c if heads is None else heads + c
    parts.append(("Screw heads", heads, col.get("screw", "#8a8d91"), 1.0, "screw_heads", {"print": False}))
    return parts, notes


if __name__ == "__main__":
    common.run_mock(build)
