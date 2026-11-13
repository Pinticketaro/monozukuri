"""Build the mock (a rough 3D shape to judge form and size).
A person makes the final model in Fusion or similar (docs/handoff.md). The STEP files can be the starting point.

Output
  out/<ver>/parts/*.stl         … mesh per part (for renders, sections, and the review page)
  out/<ver>/scene.json          … part names, colors, opacity (read by render_model.py and slices.py)
  out/<ver>/step/NN_<key>.step  … solid per part (when CadQuery is installed; skip with --no-step)
  out/<ver>/step/assembly_<ver>.step … all parts in one file with names and colors (opens in Fusion as one component per part)
  out/<ver>/step/index.json     … list of the STEP files (used to show them in the "Export" section of the review page)
Usage: python tools/mock.py [v03] [--no-step]

Template example (all laser cut): an open-top tray of five 3mm acrylic plates (bottom, front, back, left and right sides)
  joined with tabs and slots.
  Orientation: the front faces -Y, width is X, height is Z. The outline is centered at X=0, Y=0; the underside of the bottom plate is Z=0.
  Plates are joined by pushing a tab (a projection on the edge of a plate) through a slot (a hole) in the other plate. The front and back
  plates run end_margin past the side plates, so the slots that take the side plates' tabs keep an edge outside them.
  Tabs and slots in the mock are nominal (no kerf or slot_fit compensation; that goes into the laser cutting files).
  All plates use the fab value t_bottom as their thickness (cut from the same sheet; for a plate of another thickness, add t_<name> to fab).
  Rewrite the inside of build() for your own shape. Draw shapes with the tools in geom.py (one definition gives both STL and STEP).
  Add a part as (display name, shape, color, opacity, ASCII key[, options]). The key is used for the file name and the STEP part name
  (ASCII STEP part names do not get garbled in Fusion and other tools). Options:
  {"print": False} (parts that are not 3D printed: contents, off-the-shelf parts, laser-cut plates), {"up": "-z"} (print orientation).
  notes can hold text warnings, and also question candidates for things the user should decide (on the review page they become questions answered with buttons):
    {"q": "Add a divider?", "type": "yesno", "why": "Keeps small items apart"}
    {"q": "Front plate height", "type": "options", "options": ["Same as the back", {"label": "Lower", "note": "extra detail"}], "why": "…"}
  Outlines: RRect (rounded rectangle), Circle (circle), Poly (polygon). Solids: slab (extrusion + holes), prism (extrusion along X, Y or Z),
  cyl (cylinder), box (cuboid). Laser plates: tab (adds a tab to a plate and cuts a slot of the same size in the receiving plate).
  Combine: + add, - subtract, & intersect, .translate(x, y, z), .rotate_z(angle), .rotate_x(angle), .rotate_y(angle)
  (to lean a plate, tilt the standing plate with rotate_x or rotate_y). Do not model fine details (inner corner radii of slots, engraving, etc.).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import common  # noqa: E402
from geom import RRect, prism, slab, tab  # noqa: E402


# ---------- Rewrite this for your own shape
def build(prm):
    P, col = prm.P, prm.meta.get("colors", {})
    parts, notes = [], []

    def spots(a, b, w):
        """Tab centers along the edge a..b: one in the middle of a short edge (under 6× the tab width), two on a long edge"""
        n = 2 if b - a >= 6 * w else 1
        return [a + (b - a) * (i + 0.5) / n for i in range(n)]

    t = P.t_bottom                                   # sheet thickness (all plates come from the same sheet)
    W, D, H, m, e, tw = P.outer_w, P.outer_d, P.wall_h, P.margin, P.end_margin, P.tab_w
    x0, x1, y0, y1 = -W / 2 + m, W / 2 - m, -D / 2 + m, D / 2 - m   # left and right ends of the front/back plates; front face, back face
    xs = (x0 + e, x1 - e - t)                        # X of the left face of the left and right side plates
    zb = t                                           # bottom of the walls (top of the bottom plate)

    bottom = slab(RRect(W, D, P.corner_r), 0, t)
    # The front and back plates extrude an (x, z) outline along Y, the side plates a (y, z) outline along X
    # (to change a plate's shape, rewrite the points)
    fb = [(x0, zb), (x1, zb), (x1, zb + H), (x0, zb + H)]
    front, back = prism(fb, "y", y0, t), prism(fb, "y", y1 - t, t)
    sd = [(y0 + t, zb), (y1 - t, zb), (y1 - t, zb + H), (y0 + t, zb + H)]
    sides = [prism(sd, "x", x, t) for x in xs]

    # Tabs into the bottom plate (from the lower edge of each plate)
    for xc in spots(x0, x1, tw):
        front, bottom = tab(front, bottom, xc - tw / 2, y0, 0, tw, t, t)
        back, bottom = tab(back, bottom, xc - tw / 2, y1 - t, 0, tw, t, t)
    for k, x in enumerate(xs):
        for yc in spots(y0 + t, y1 - t, tw):
            sides[k], bottom = tab(sides[k], bottom, x, yc - tw / 2, 0, t, tw, t)
    # Tabs from the side plates into the front and back plates (from the front and back edges of each side plate)
    for k, x in enumerate(xs):
        for zc in spots(zb, zb + H, tw):
            sides[k], front = tab(sides[k], front, x, y0, zc - tw / 2, t, t, tw)
            sides[k], back = tab(sides[k], back, x, y1 - t, zc - tw / 2, t, t, tw)

    pc, sc = col.get("plate", "#bcd6e4"), col.get("side", "#9fc3d6")
    for name, s, c, key in [("Bottom plate", bottom, pc, "bottom"), ("Front plate", front, pc, "front"), ("Back plate", back, pc, "back"),
                            ("Left side plate", sides[0], sc, "side_left"), ("Right side plate", sides[1], sc, "side_right")]:
        parts.append((name, s, c, 0.85, key, {"print": False}))

    # Problems that follow directly from the dimensions
    if m < t:
        notes.append(f"The edge distance of the bottom plate slots {m:g}mm is smaller than the sheet thickness {t:g}mm (acrylic cracks easily)")
    if e < t:
        notes.append(f"The edge distance of the front and back plate slots {e:g}mm is smaller than the sheet thickness {t:g}mm (acrylic cracks easily)")
    if tw < 3 * t:
        notes.append(f"The tab width {tw:g}mm is narrower than 3× the sheet thickness = {3 * t:g}mm (tabs break easily)")
    if tw > H:
        notes.append(f"The tab width {tw:g}mm is larger than the wall height {H:g}mm (the side plate tabs do not fit in the front and back plates)")
    else:
        ev = min(min(zc - tw / 2 - zb, zb + H - (zc + tw / 2)) for zc in spots(zb, zb + H, tw))
        if ev < t:
            notes.append(f"The top/bottom edge distance of the front and back plate slots (for the side plate tabs) {ev:g}mm is smaller "
                         f"than the sheet thickness {t:g}mm (acrylic cracks easily)")
    plates = {"bottom plate": (W, D), "front and back plates": (x1 - x0, H + t), "side plates": (y1 - y0, H + t)}   # bounding rectangle with tabs
    lx, ly = P.laser_x, P.laser_y
    big = [f"{n} ({a:g}×{b:g}mm)" for n, (a, b) in plates.items()
           if max(a, b) > max(lx, ly) or min(a, b) > min(lx, ly)]
    if big:
        notes.append(f"Plates that do not fit the laser work area {lx:g}×{ly:g}mm: " + ", ".join(big))
    notes.append(f"Outer size W{W:g}×D{D:g}×H{H + t:g}mm, inside W{xs[1] - xs[0] - t:g}×D{y1 - y0 - 2 * t:g}×depth {H:g}mm. "
                 f"5 plates ({t:g}mm acrylic)")
    fit = getattr(P, "slot_fit", 0.0)
    notes.append(f"Slot width = sheet thickness + slot_fit = {t + fit:.2f}mm (used in the laser cutting files; the mock keeps the sheet "
                 f"thickness. Decide slot_fit with the slot comb)")
    notes.append({"q": "Front plate height", "type": "options",
                  "options": ["Same as the back plate (current shape)", {"label": "Lower", "note": "the top of the side plates slopes from front to back"}],
                  "why": "A lower front shows what is inside and makes items easier to take out. The same height keeps the plate shapes simple"})
    notes.append({"q": "Add a divider?", "type": "yesno",
                  "why": "Keeps small items apart. It adds one plate and more slots in the front and back plates"})
    return parts, notes


if __name__ == "__main__":
    common.run_mock(build)
