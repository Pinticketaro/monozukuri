"""Build the mock (a rough 3D shape to judge form and size).
A person makes the final model in Fusion or similar (docs/handoff.md). The STEP files can be the starting point.

Output
  out/<ver>/parts/*.stl         … mesh per part (for renders, sections, and the review page)
  out/<ver>/scene.json          … part names, colors, opacity (read by render_model.py and slices.py)
  out/<ver>/step/NN_<key>.step  … solid per part (when CadQuery is installed; skip with --no-step)
  out/<ver>/step/assembly_<ver>.step … all parts in one file with names and colors (opens in Fusion as one component per part)
  out/<ver>/step/index.json     … list of the STEP files (used to show them in the "Export" section of the review page)
Usage: python3 tools/mock.py [v03] [--no-step]

Template example (all 3D printed): a case for a 350ml can. A tube with a bottom, with lugs on the left and right for a strap.
  Rewrite the inside of build() for your own shape. Draw shapes with the tools in geom.py (one definition gives both STL and STEP).
  Add a part as (display name, shape, color, opacity, ASCII key[, options]). The key is used for the file name and the STEP part name
  (ASCII STEP part names do not get garbled in Fusion and other tools). Options:
  {"print": False} (parts that are not 3D printed: contents, off-the-shelf parts, laser-cut plates), {"up": "-z"} (print orientation).
  For 3D-printed parts, downward faces that may need support (shallower than overhang_deg) are listed as warnings automatically.
  notes can hold text warnings, and also question candidates for things the user should decide (on the review page they become questions answered with buttons):
    {"q": "Add a retainer?", "type": "yesno", "why": "The can falls out when upside down"}
    {"q": "Lug position", "type": "options", "options": ["Top edge", {"label": "Middle", "note": "extra detail"}], "why": "…"}
  Outlines: RRect (rounded rectangle), Circle (circle), Poly (polygon). Solids: slab (extrusion + holes), cyl (cylinder), box (cuboid),
  tube (tube), cone (truncated cone), revolve (solid of revolution), lug_with_slot (lug with a slot for a strap).
  Combine: + add, - subtract, & intersect, .translate(x, y, z), .rotate_z(angle). Do not model fine details (fillets, threads, etc.).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import common  # noqa: E402
from geom import cone, cyl, lug_with_slot, tube  # noqa: E402


# ---------- Rewrite this for your own shape
def build(prm):
    P, col = prm.P, prm.meta.get("colors", {})
    parts, notes = [], []
    r_in = P.can_d / 2 + P.can_gap
    r_out = r_in + P.wall
    H = P.sleeve_h

    # Tube + bottom (with a drain hole in the bottom)
    body = tube(0, 0, 2 * r_out, 2 * r_in, 0, H) + cyl(0, 0, 2 * r_out, 0, P.bottom_t)
    body = body - cyl(0, 0, P.drain_d, -1, P.bottom_t + 2)
    # Lugs (left and right): each has a slot the strap passes through from top to bottom. They are sunk into the tube wall to join it
    lug_z0 = H - P.lug_top_gap - P.lug_h
    for ang in (0, 180):
        body = body + lug_with_slot(r=r_out, angle=ang, w=P.lug_w, out=P.lug_out, h=P.lug_h, z0=lug_z0,
                                    slot_w=P.strap_w + 2 * P.strap_clr, slot_t=P.strap_t + 2 * P.strap_clr,
                                    embed=min(2.0, P.wall))
    parts.append(("Case", body, col.get("body", "#d9d4cb"), 1.0, "case"))

    # Contents (for checking): can body + tapered shoulder
    z = P.bottom_t
    can_body_h = P.can_h - P.can_neck_h
    can = cyl(0, 0, P.can_d, z, can_body_h) + cone(0, 0, P.can_d, P.can_top_d, z + can_body_h, P.can_neck_h)
    parts.append(("Can (contents)", can, col.get("content", "#b23a3a"), 1.0, "can", {"print": False}))

    # Problems that follow directly from the dimensions
    if hasattr(P, "clr_slide") and P.can_gap < P.clr_slide:
        notes.append(f"The gap to the can {P.can_gap:g}mm is smaller than the removable-fit clearance {P.clr_slide:g}mm (the can may not go in)")
    if P.wall < 0.8:
        notes.append(f"The wall {P.wall:g}mm is thinner than 2× the 0.4mm nozzle = 0.8mm")
    outer_x = 2 * (r_out + P.lug_out)
    if outer_x > P.bed_x or 2 * r_out > P.bed_y or H > P.bed_z:
        notes.append(f"The outer size {outer_x:.0f}×{2 * r_out:.0f}×{H:g} is larger than the printer area {P.bed_x:g}×{P.bed_y:g}×{P.bed_z:g}")
    exposed = P.bottom_t + P.can_h - H
    notes.append(f"The can sticks out {exposed:.0f}mm above the tube ({exposed / P.can_h * 100:.0f}% of the can height)")
    return parts, notes


if __name__ == "__main__":
    common.run_mock(build)
