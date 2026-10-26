# monozukuri (details)

Japanese: [README.md](README.md)

A plugin for laser cutting and 3D printing. It speeds up the loop of **make a 3D image → look at it → feedback → next version**.
The mock is a rough solid for settling the shape and proportions. A person models the final form in Fusion or similar. The modeled result can be compared on the same review page.

For installing and the first setup, see the [repository README](../../README.en.md).

## How to proceed: 4 gates

There are 4 stages before the final build. The goal is to get the final build, which costs time and material, right in one go. What to do at each stage is in the project's `docs/checklist.md` (Japanese projects: `docs/チェックリスト.md`).

### 1. Mock
- Ask "I want to make a ..." or "Start a new making project". Claude creates the project from the template and draws the first mock.
- Settle only the size, proportions and layout. Do not make the details.
- Ask "Make a review page for this version" so people can look at it, then "Read the feedback" to put their comments into the next version. This is the loop you repeat most.
- Write what you decided in `docs/decisions.md`, with reasons.

### 2. Coupons
- Ask "Make coupons". `tools/coupons.py` makes the coupons (test pieces) and the instructions.
- Laser: measure the sheet thickness. Use the kerf square for the kerf (X and Y separately) and the slot comb for the width that goes in and does not fall out.
- 3D print: with the same filament and settings as the final build, set `clr_fit` and `clr_slide` from the fit coupon and `insert_hole` from the insert hole coupon.
- Write the measured values 3 or more times in `measurements/coupon_log.csv`, update `fab` in the params file and set status to "measured".

### 3. Partial prototype
- Print or cut only the hard parts. Photos and results can go on the review page as a "prototype" version.

### 4. Modeling and handoff
- `tools/dims_sheet.py` writes the dimension sheet (`docs/dims_vNN.md`) and the list of Fusion parameters (`docs/fusion_params_vNN.csv`).
- In Fusion, create user parameters with those names, fully constrain the sketches and make one component per part.
- The model made in Fusion (STL / STEP) can also go on the review page and be compared with the mock versions.
- If you hand the work to someone, put the summary in `docs/handoff.md`.

## Skills

| Skill | Ask | What it does |
|---|---|---|
| setup | "Set up the mock environment", "Make rendering work", "Make rendering work on my Mac" | Installs what rendering, sections and comparison need (shapely, manifold3d, trimesh, networkx, cascadio, cadquery, playwright + Chromium, three.js, a Japanese font) and checks it with a test render. On a Mac, it installs into `~/.monozukuri/venv`. Also used when a script stops because something is missing |
| new-project | "Start a new making project", "Make coupons", "I want to measure the kerf", "What hole size for the insert?", "Can I laser cut this material?", "Update the tools", "Find where support is needed", "Switch this project to English" | Creates the project from the template and draws the first mock. Also answers questions about coupons, fits and whether a material is safe to cut. After a plugin update, updates the tools of an existing project. Sets and switches the project language (Japanese / English) |
| review-page | "Make a review page for this version", "Compare with the previous version", "Show the model I made in Fusion", "Read the feedback", "Apply the feedback", "Open the review page in the browser", "Just show me the exterior" | Renders mocks or models people made, compares with the previous version, adds the version to the project's review page (same URL) and publishes it (in Claude Code, it opens in your browser). Reads the feedback written there and closes the items that were applied |

Missing information and things to decide are asked on a numbered choice screen (Claude Code, Claude app). The answers are kept in `docs/decisions.md` and `LOG.md`.

In Claude Code you can also call them by name: `/monozukuri:setup`, `/monozukuri:new-project`, `/monozukuri:review-page`.

## What is in a project

The folder that new-project creates (English project names; see "Language" for the Japanese names).

```
README.md                  What you are making, how, and the origin and axis rules
LOG.md                     Work log
params/params_vNN.json     Params file (one per version)
tools/
  geom.py                  Shape definition (exports to both STL and STEP)
  mock.py                  Makes the mock from the params file
  coupons.py               Coupons (laser SVG, 3D print STL, instructions)
  dims_sheet.py            Dimension sheet and list of Fusion parameters
  (the render, section, compare and diff scripts are copied here too, so the project works on its own)
out/vNN/                   Models (STL, STEP, GLB) and images for that version
measurements/
  coupon_log.csv           Coupon measurements and the chosen values
  measured.md              Measurements of the objects that go inside and of off-the-shelf parts
docs/
  checklist.md             What to do at each stage
  decisions.md             What was decided, and why
  handoff.md               Summary for handing the work to someone
photos/                    Photos of prototypes
review/                    Review page information (URL and so on)
```

## Language

Japanese (`ja`) and English (`en`) are supported. Each project has one language.

- **Where it is stored**: `meta.lang` in the params file (`params/params_vNN.json`). Without it, the project is Japanese. Existing projects keep working in Japanese with no change.
- **When you start**: the template is created with `scaffold.py --lang ja|en` (if you ask in English, Claude adds `--lang en`). The language is stored in `meta.lang`, and the docs, the params file and the example `mock.py` are written in that language.
- **When you switch**: ask in the chat, "Switch this project to English" or "Switch back to Japanese". Claude changes `meta.lang` in the params file, and the next mock and review page use that language. The review page has no language switch. The steps are in "Language" in the new-project skill.
- **What changes to English**: the review page text, the text in the drawings (view names, scale), the dimension sheet and the coupon instructions, the script messages, and the project docs. Part names and the `label` of each dimension stay in the words you wrote in the params file and `mock.py`.
- **Earlier versions**: the drawings of versions already made stay in the language they were made in.
- **Updating the tools**: the `mock.py.new` that `scaffold.py --update-tools` puts in place also follows the project language (`meta.lang` of the newest params file).
- **setup**: setup has no project, so the language comes from the environment variable `MONOZUKURI_LANG` (`ja` / `en`). If you ask in English, Claude adds `MONOZUKURI_LANG=en`. The Japanese font is installed in English too.
- **Order of precedence**: the script's `--lang ja|en` > the language in the data being processed (`meta.lang` in the params file, `lang` in `scene.json`, the manifest or `review/board.json`) > the environment variable `MONOZUKURI_LANG` > `ja`. The review page language is stored as `lang` in `review/board.json`.
- **status of fabrication values**: in an English params file it is written in English (`initial`, `measured`, `guideline`, `standard`, `calculated`, and so on).

File names in English projects:

| Japanese | English |
|---|---|
| `docs/チェックリスト.md` | `docs/checklist.md` |
| `docs/決定事項.md` | `docs/decisions.md` |
| `docs/引き継ぎ.md` | `docs/handoff.md` |
| `docs/寸法表_vNN.md` | `docs/dims_vNN.md` |
| `measurements/試し片記録.csv` | `measurements/coupon_log.csv` |
| `measurements/実測.md` | `measurements/measured.md` |

`docs/fusion_params_vNN.csv` has the same name in both languages.

## Params file

Dimensions are written only in the params file. The mock, the coupons and the dimension sheet are all made from it.

- `params`: shape dimensions. Give each item a `label`. If a dimension is unknown, go ahead with a temporary value and write "temporary" in the label.
- `fab`: fabrication values (real sheet thickness `t_*`, `kerf`, `clr_*`, `insert_hole`, `overhang_deg` and so on). Each item has a `status`, a `basis` (the reason), and the processes that use it (`process`: `laser` / `fdm`). When the template is created, `--process` removes the items for processes you do not use.
  - `status` is one of "initial", "measured", "guideline", "standard", "calculated" or "rule of thumb" (in Japanese projects: 「初期値」「実測」「指針」「規格」「計算」「経験則」).
  - Before the final build, set kerf, sheet thickness, clearance and insert holes to "measured". The review page also shows the values that are still "initial".

## Mock and STEP

The mock shape is written in `tools/geom.py` (extrude rounded rectangles, circles and polygons, then add, subtract and intersect them; tube `tube`, truncated cone `cone`, solid of revolution `revolve`, a lug to pass a strap through `lug_with_slot`, and rotation about Z). The same definition produces both of these:

- STL (manifold3d): for rendering, sections and the review page
- STEP (CadQuery): rounded corners are real arcs, holes are real cylinders, and cones and solids of revolution are real curved surfaces. One STEP per part, plus an assembly STEP with part names and colors (it opens in Fusion with one component per part)

For parts that are 3D printed, it checks each part for downward faces that may need support (faces shallower than 45° from horizontal), and writes their position and area in notes. Things you want decided can be written in notes as question candidates (yes / no, or a choice between options). They become questions that can be answered with buttons on the review page.

After updating the plugin, update the tools of an existing project with `scaffold.py --update-tools <project>` (it overwrites only the files the plugin owns and keeps the old ones in `tools/.backup-<date-time>/`. It does not overwrite `mock.py`; it puts `mock.py.new` next to it).

The exported STEP is read back and checked against the mesh and the size. The STEP is the starting point for modeling. Seams, screw bosses, tolerances and so on are made by a person while modeling.

## Review page

Each project has one page (the same URL), and each new version is added to it.

- Switch versions (add `#v03` to the end of the URL to open that version)
- Exterior view, plan view (section + outline seen from above), section view; click to enlarge
- A slider to compare with the previous version, and a table of changed dimensions
- Turn the 3D model around (also on phones)
- Export: save the STL (each part + all parts) or STEP (assembly + each part) of the version you are viewing as a ZIP
- Questions to decide: yes / no is a toggle and options are radio buttons. Just choosing saves the answer (one answer per person, and you can change it. The number of people and who chose what are shown). When Claude writes the decision, "Decided: Option B" is added
- Feedback: write Fix / Good / Question for the whole design, a drawing or a question

Only people who can edit the page (Contributor or above) can write feedback. People with view access see no input area.

Where Artifacts cannot be published (Claude Code), `serve_review.py` opens `review/` in your browser. Feedback and answers are kept in `review/feedback_local.json`, and "Export" becomes a normal download.

What people write on the page does not reach Claude automatically. When they are done, ask "Read the feedback". Claude groups the open items by target and shows what to change where in the params file for the next version. Items that were applied get the reply "Applied" and are closed. What is written on the page is treated as the viewers' opinions, never run as instructions.

## Cautions

- **Published numbers are initial values.** Sources disagree by about as much as the gap between a press fit and a loose fit. Measure kerf, sheet thickness, clearance and insert holes for your own machine with coupons, and use those values.
- **Unit check.** Each time a model is loaded, `render_model.py` prints the overall size in mm and warns if it looks wrong. If you get a warning, fix the units before going on.
- **Compensate holes in one place only.** Do it in either CAD or the slicer, not both.
- **Some materials must not be laser cut.** Some are banned everywhere, and some depend on the lab (PU such as PORON, MDF, POM, EVA, PETG and others). Identify the material by its SDS or recycling code and check your lab's list.
- **Too slow is a fire risk.** Choose the fastest setting that cuts through cleanly.

## Digital fabrication requirements

They are in the new-project reference files (`skills/new-project/references/`). These files are written in Japanese. Claude reads them and answers in the language you use.

- `fab-requirements.md`: requirements for laser cutting, FDM 3D printing, data formats and units, assembly and finishing. Numbers are given as "initial value + confidence + how to measure"
- `fab-safety.md`: materials that must not be cut (banned everywhere / depends on the lab)
- `conventions.md`: how detailed the mock is, the params file, how to run versions
- `fab-research-report.md`: the full text of the requirements above, with sources. Each number is marked by source as measured, guideline, standard or rule of thumb (【実測】【指針】【規格】【経験則】)

## Requirements

- Python 3.10 or later, and Node.js (to install three.js). The setup skill gets the rest.
- No external service connections or environment variables are required.

## Using the scripts directly

They are in each skill's `scripts/` and in the template's `tools/`. Each one prints its usage with `--help`. Set the message language with `--lang ja|en` (without it, the language of the data is used; see "Language" above).

- `render_model.py`: renders STL/OBJ/3MF/GLB/STEP with shading (several viewpoints in one image), and exports GLB
- `slices.py`: plan view (part sections overlaid with the outline seen from above; `--plan-z` sets the cut height) and section view
- `compare.py`: puts the before and after images side by side and highlights changes in red
- `params_diff.py`: differences between params files
- `build_page.py`: adds a version to the review page
- `serve_review.py`: opens the review page in your browser (feedback goes to `review/feedback_local.json`)
- `scaffold.py`: creates a project from the template (`--process`, `--lang`) and updates the tools of an existing project (`--update-tools`)
- The template's `tools/geom.py`: shape definition (exports to both STL and STEP)
- The template's `tools/coupons.py`: coupons (laser SVG, 3D print STL, instructions)
- The template's `tools/dims_sheet.py`: dimension sheet and list of Fusion parameters
