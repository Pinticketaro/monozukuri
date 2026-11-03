# Handoff to modeling

The mock is a rough solid for settling shape and proportions. The shape used for manufacturing (fillets, seams, screw mounts, tolerances, print orientation) is decided by a person during modeling.

## What to hand over
- `docs/dims_vNN.md`: list of dimensions, fabrication values (measured or initial), and notes found in the mock
- `docs/fusion_params_vNN.csv`: list to copy into Fusion user parameters (name, value, unit, comment)
- `docs/checklist.md`: checks for modeling and before the final build
- Exterior view, plan and section from `out/vNN/`
- Link to the review page: check that no feedback is left unaddressed
- `docs/decisions.md`
- `out/vNN/step/assembly_vNN.step`: the mock shape as solids (when CadQuery is installed). It opens in Fusion with one component per part. Rounded corners and holes are real arcs and cylinders, so you can add extrudes and fillets directly. The dimension values are the same as in fusion_params

The mock STEP is only a starting point. It has no seams, screw mounts or tolerances, so the modeler decides whether to rebuild from the parameters (fusion_params) or add to the STEP.

## Decided in modeling (not in the mock)
- How to split the parts and the shape of the seams (does each part fit the printer's build volume)
- How to hold screws, inserts and nuts
- Fit tolerances: `clr_*` in the dimension sheet (values measured with coupons. If still "initial", make the coupons first)
<!-- fdm -->
- Print orientation and supports (the `mock.py` notes list faces that likely need support)
<!-- /fdm -->
<!-- laser -->
- Laser kerf compensation (`kerf`; if you compensate, the offset is k/2)
<!-- /laser -->
- Corner rounds and chamfers

## After modeling
1. Export as STL or STEP and put it in `out/vNN/model/`
2. Add it to the review page as a "Model (Fusion)" version. Include a comparison with the mock
3. Where dimensions differ from the mock, update the params file too (so the starting point for the next round does not drift)
