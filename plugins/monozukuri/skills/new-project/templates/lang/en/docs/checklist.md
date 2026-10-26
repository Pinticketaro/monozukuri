# Checklist (by stage)

Published numbers are only initial values. Measure the values for your own machine with coupons before the final build.
Reasons and sources: `references/fab-requirements.md` in the monozukuri plugin (new-project skill).
<!-- Items that do not apply to the process (laser / 3D print) were removed when the project was created -->

## 1. Mock
- [ ] Checked size, proportions and layout, and got feedback on the review page
- [ ] Wrote the decisions in `docs/decisions.md` with reasons

## 2. Coupons (`python3 tools/coupons.py`)
<!-- laser -->
Laser
- [ ] Measured the thickness of the sheet you will use at the 4 corners and the center, and replaced `t_*`
- [ ] Varied power and speed, and chose the fastest setting that cuts through cleanly (too slow is a fire risk)
- [ ] Measured kerf k (full width) on the kerf square, separately for X and Y → `kerf`
- [ ] On the slot comb, chose the width that goes in and does not fall out (on the same sheet as the final build)
- [ ] Identified the material by SDS / recycling code and checked that your lab's list allows it (PU such as PORON, MDF, POM, EVA and PETG depend on the lab)
<!-- /laser -->
<!-- fdm -->

3D print (with the same filament and settings as the final build)
- [ ] Set `clr_fit` and `clr_slide` with the fit coupon
- [ ] Set `insert_hole` with the insert hole coupon (4.0-4.4)
- [ ] Compensated holes in **only one** place: CAD or the slicer
- [ ] Chose an orientation and shape that reduce the faces that need support (listed in the `mock.py` notes)
<!-- /fdm -->

Record
- [ ] Wrote 3 or more measurements, the chosen value and where it goes in `measurements/coupon_log.csv`
- [ ] Updated the `fab` values in the params file and set the status to "measured"

## 3. Modeling (Fusion or similar)
- [ ] Created user parameters with the names in `docs/dims_vNN.md` and `docs/fusion_params_vNN.csv`
- [ ] Fully constrained the sketches and made one component per part
- [ ] Changed dimensions to check that the model follows (flex test)
- [ ] Every interface dimension traces back to a measured value or a datasheet
- [ ] Put the exported model on the review page and checked that the overall size (mm) matches a known dimension (no 25.4x or 1000x mix-up)

## 4. Partial prototype
- [ ] Cut / printed one corner of the case (USB cutout, one screw boss, one corner of the contents) and fitted it to the real parts
- [ ] The thickest USB-C cable went all the way in

## 5. Before the final build
<!-- laser -->
Laser
- [ ] Closed paths, no duplicate lines, text converted to paths, everything inside the page, colors mapped to settings, inner cuts first, lines at least 0.5mm apart
- [ ] After importing into the laser software, checked the size of the largest outline
- [ ] Screw holes in acrylic: center to edge at least 1.5x the hole diameter
<!-- /laser -->
<!-- fdm -->

3D print
- [ ] Overhangs within 45°, bridges within 5mm, walls 0.8mm or more, bed-side edges chamfered, horizontal screw holes teardrop-shaped
- [ ] Fits the build volume (if not, the split and seam were checked with a partial prototype)
- [ ] The material suits the temperature where it will be used (PLA deforms at about 57°C)
<!-- /fdm -->

## 6. Assembly and finishing
- [ ] Screw holes are JIS B 1001 class 2-3 (3.4-3.6 for M3), washers on acrylic, not overtightened
- [ ] Checked the worst-case stack-up of sheet and foam thicknesses, and let the foam take up the variation. The compression is set by the boss height
<!-- laser -->
- [ ] No alcohol or CA glue on acrylic edges
<!-- /laser -->
- [ ] If painting, masked the mating faces and insert holes, and installed the inserts after painting

## 7. Record
- [ ] Committed the files sent for fabrication, the params file and the coupon log, and added a tag
