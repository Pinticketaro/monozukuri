# {{NAME}}

{{SUMMARY}}

## How this repository works

Settle the shape and size with the mock, collect feedback on the review page, and make the next version. Once the shape is settled, a person models it in Fusion or similar from the dimension sheet and images.

Work through 4 gates: **mock → coupon → partial prototype → final** (`docs/checklist.md`).

1. **Change dimensions**: copy `params/params_vNN.json` as the next version and edit it (change one condition per version where possible)
2. **Make the mock and drawings**: see "Commands" below
3. **Put it on the review page to view and comment**: `review/` (the review page of the monozukuri plugin)
4. **Apply the feedback to the next version**, record it in `LOG.md`, and commit
5. **Set the fabrication values with coupons**: make them with `tools/coupons.py`, cut / print them → `measurements/coupon_log.csv` → update `fab` in the params file and set its status to "measured"
6. **Hand off once the shape is settled**: give `docs/dims_vNN.md`, `docs/fusion_params_vNN.csv` and the images to the modeler (`docs/handoff.md`). The modeled result (STL / STEP) can be viewed on the same review page

## Commands

```
python3 tools/mock.py vNN                     # mock → out/vNN/parts/*.stl, out/vNN/scene.json, out/vNN/step/*.step (when CadQuery is installed)
python3 tools/render_model.py --scene out/vNN/scene.json --out out/vNN/preview.png --glb out/vNN/model.glb
python3 tools/slices.py --scene out/vNN/scene.json --plan out/vNN/plan.png --section out/vNN/section.png
python3 tools/compare.py out/vPP/preview.png out/vNN/preview.png --out out/vNN/compare.png --labels vPP vNN --lang en
python3 tools/params_diff.py params/params_vPP.json params/params_vNN.json --json out/vNN/params_diff.json
python3 tools/dims_sheet.py vNN               # dimension sheet for handoff → docs/dims_vNN.md and docs/fusion_params_vNN.csv
python3 tools/coupons.py vNN                  # coupons → out/coupons/ (laser SVG / 3D print STL depending on the process, plus coupons.md)
```

The mock STEP (`out/vNN/step/assembly_vNN.step`) opens in Fusion with one component per part, so it can be the starting point for modeling. You can also save STL / STEP as a ZIP from "Export" on the review page.

To view a model made in Fusion or similar: `python3 tools/render_model.py frame.step:#d9d4cb top.stl:#bcd6e4:0.6 --out out/vNN/model_preview.png`

Requirements: `pip install -r tools/requirements.txt`, three.js (installed by the monozukuri setup)

## Folders

| Folder | Contents |
|---|---|
| `params/` | Dimensions per version (`params` = shape dimensions, `fab` = fabrication values set with coupons. Write numbers only here) |
| `tools/` | Scripts for the mock, rendering, sections, comparison and the dimension sheet |
| `out/` | Output per version (images are kept; STL, STEP and GLB can be regenerated, so they are not in Git) |
| `review/` | Review page (for publishing) |
| `docs/` | Decisions, handoff, dimension sheets |
| `measurements/` | Measured values of real objects, coupon log |
| `photos/` | Photos of prototypes, test prints and cuts (with a ruler in the shot) |
| `LOG.md` | Build log |

## Rules

- **Units are mm; origin and axes**: {{ORIGIN}}. Keep them the same in every app and script
- **Version number**: add `vNN` to params files, outputs and images (`out/v03/preview.png`)
- **Commit = build log**: "what changed → how it looked / how it went → what to try next"
- **Tag when you make a real object**: `proto-1`, `cut-test-1`, etc.
- **The mock is for checking looks and proportions.** Make the manufacturing data from the modeled result
- **Published numbers are only initial values.** For fabrication values (`fab` in the params file), use values measured with coupons
- **After importing, measure one dimension** (to catch unit mix-ups: 25.4x, 1000x)
