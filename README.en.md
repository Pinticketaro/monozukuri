# monozukuri

Japanese: [README.md](README.md)

A Claude plugin for laser cutting and 3D printing. It speeds up the loop of **rough 3D mock → review page → feedback → next version**.
The mock is a rough solid for settling the shape and proportions. A person models the final form in Fusion or similar. The modeled result (STL / STEP) can be compared on the same review page.

It works in English and Japanese. The language is set per project, and you switch it in the chat (see "Language" below).

## Install

### Claude app (desktop and web)

1. In the left sidebar, open **Customize** → **Plugins**
2. Choose **Add marketplace** and enter `Pinticketaro/monozukuri`
3. Select **monozukuri** in the list and press **Install**

If you do not use the marketplace, download [monozukuri.plugin](https://github.com/Pinticketaro/monozukuri/raw/main/dist/monozukuri.plugin) and attach it to a chat to add it. Plugins are available on paid plans (Pro, Max, Team, Enterprise).

### Claude Code (terminal)

```
/plugin install monozukuri --marketplace Pinticketaro/monozukuri
```

Commands that start with `/plugin` work only in Claude Code. They do not work in the Claude app's input box.

### On Windows

- **We recommend the Claude app.** Rendering and other processing run in Claude's cloud workspace (Linux), so the steps are the same as on a Mac. Ask "Set up the mock environment" in each new conversation.
- **To run on your own PC, Claude Code in WSL (Linux inside Windows) is the most reliable.** Keep projects in a WSL folder (under `~/`).
- **To use Claude Code directly on Windows**, install the following (not fully tested yet; please report problems in an Issue):
  - [Git for Windows](https://git-scm.com/downloads/win) (it includes Git Bash, which Claude Code uses to run commands; setup does not run without it)
  - Python 3.10 or later (from python.org; tick "Add python.exe to PATH") and Node.js
  - If `python3` does not work, tell Claude "use python instead of python3"
- Keep projects in a short path that OneDrive does not sync (for example `C:\work\`). Syncing and very long paths can make writes fail.

## First time only

1. **Start a new conversation**: plugins load when a conversation starts. A conversation that was already open before you added the plugin cannot use it.
2. **Ask "Set up the mock environment"**: this installs what rendering needs and checks it with a test render.

## How it works

Ask in plain words and the matching skill runs. In Claude Code you can also call them by name: `/monozukuri:setup`, `/monozukuri:new-project`, `/monozukuri:review-page`.

There are 4 stages (gates) before the final build. The goal is to get the final build, which costs time and material, right in one go.

| Stage | Ask | What happens |
| --- | --- | --- |
| 1. Mock and review page | "I want to make a ...", "Make a review page for this version", "Read the feedback" | Settle the shape and size with a rough mock. People look at it on the review page, and their comments go into the next version. This is the loop you repeat most |
| 2. Coupons | "Make coupons", "I want to measure the kerf" | Measure the kerf, fits and insert holes of your own machine with small test pieces (coupons). Put the measured values back in the params file |
| 3. Partial prototype | "I only want to test this part" | Print or cut only the hard parts |
| 4. Final build and handoff | "Export the parameters for Fusion" | Hand off to a person for modeling, with STEP and a list of Fusion parameters |

If you are not sure, ask "What should I do next?". Claude checks the project checklist and tells you.

## What it can do (v0.5.0)

| Skill | Ask | What it does |
| --- | --- | --- |
| setup | "Set up the mock environment", "Make rendering work on my Mac" | Installs what rendering, sections and comparison need (shapely, manifold3d, trimesh, networkx, cascadio, cadquery, playwright + Chromium, three.js, a Japanese font) in one go, and checks it with a test render. On a Mac, it installs into a virtual environment outside the project (`~/.monozukuri/venv`) |
| new-project | "Start a new making project", "Make coupons", "Update the tools", "Switch this project to English" | Creates the project: a params file (shape dimensions + fabrication values with confidence), a mock generator (STL and STEP from one shape definition; the STEP has real arcs, cylinders and cones, and opens in Fusion with one component per part), a coupon generator, scripts for rendering, sections, comparison and the dimension sheet, a stage checklist, handoff docs and Git settings. Then it draws the first mock. It narrows the fabrication values and steps to the process (laser / 3D print / both), and flags faces that may need support in 3D printing. It sets and switches the project language (Japanese / English) |
| review-page | "Make a review page for this version", "Read the feedback", "Open the review page in the browser" | Renders mocks or models people made (STL / OBJ / STEP), compares them with the previous version, adds the version to the project's review page and publishes it (in Claude Code, it opens in your browser). Claude reads the feedback and answers written on the page, and adds a reply or "Decided" once they are applied |

### Changes in 0.5.0

- English support. Each project is in Japanese or English. Ask in the chat ("Switch this project to English") to change it. The review page, drawings, dimension files and docs are in English too. The page has no language switch
- A project you start in English is created in English, and the doc file names are English too (`docs/checklist.md` and so on)
- Existing projects keep working in Japanese with no change. To switch one to English, update the plugin and then ask "Update the tools" (the English drawings and messages come from the new tools)

### Changes in 0.4.0

- The plan view overlays the outline seen from above, so lugs and bumps that are not at the cut height also show. The top and front views have no large shadows, each view fills its frame, and a scale reference is added
- Template: `--process` (laser / 3D print / both) narrows the fabrication values. Tools for tubes, truncated cones, solids of revolution and strap lugs. Faces that may need support in 3D printing are listed in notes automatically
- Write things you want decided as question candidates in the mock's notes, and they can be answered on the review page with yes / no or by choosing an option. Missing information is asked on a numbered choice screen
- The review page can be opened in your browser from Claude Code (feedback is kept in `review/feedback_local.json`). Export (downloads) is turned on at every publish, and where it cannot work, "Export" shows as unavailable
- **For existing projects, ask "Update the tools" after updating the plugin** (`tools/` is copied into each project. `mock.py` is not overwritten; the new template is put in `mock.py.new`)

### On the review page

- Switch versions (add `#v03` to the end of the URL to open that version)
- Exterior view, plan view and section view, a slider to compare with the previous version, and a table of changed dimensions
- Turn the 3D model around (also on phones)
- Save the STL / STEP of the version you are viewing as a ZIP
- In Claude Code, open it in your browser ("Open the review page in the browser")
- Answer "Questions to decide" with yes / no or by choosing an option
- Write feedback (Fix / Good / Question) for each drawing or question

### Language

- Each project is in Japanese or English. The language is stored as `meta.lang` in the params file. Without it, the project is Japanese.
- To switch, ask in the chat: "Switch this project to English" or "Switch back to Japanese". The review page has no language switch.
- In an English project, the review page, the text in the drawings, the dimension sheet, the coupon instructions and the docs are in English. Part names and dimension names stay in the words you wrote them in.

For details, see [plugins/monozukuri/README.en.md](plugins/monozukuri/README.en.md).

## Cautions

- **Published numbers are initial values.** Replace kerf, sheet thickness, clearance and insert holes with values measured on coupons before you go on to the final build. The bundled technical requirements mark each number by source as measured, guideline, standard or rule of thumb, but all of them assume you check them on your own machine.
- **Some materials must not be laser cut.** Ask "Can I laser cut this material?" and Claude checks it. What is allowed also differs by lab (and by machine), so follow your own lab's rules first.

## Guarding against AI mistakes

AI can misread dimensions, mix up units, or write plausible numbers that no source supports. monozukuri is built so that such mistakes surface before the final build.

**What monozukuri does**
- **Dimensions live only in the parameter file.** Mocks, coupons, dimension sheets and Fusion parameters are all generated from it, so nothing is copied by hand.
- **Each value carries a status and a basis.** Fabrication values are marked initial, measured and so on, with their source or how they were measured. Unchecked values are shown as provisional or initial.
- **Unit checkpoint.** Every time a model is loaded, its overall size is printed in mm, with a warning if it looks wrong.
- **Claude checks its own renders.** After drawing a mock, Claude looks at the image to confirm it matches the request.
- **People review it.** Reviewers comment on the review page, and the next version reflects their feedback.
- **Physical checks.** Coupons and partial prototypes confirm real dimensions and fits before the final build.
- **You can go back.** Every version is kept and recorded in Git.

**What we ask of you**
- Measure the parts that go inside, and any off-the-shelf parts, with calipers and give Claude the numbers.
- If a value looks off, ask "What is this value based on?" Claude shows its basis and sources.
- Run at least one coupon or partial prototype before the final build.
- A person makes the final call on material safety and lab rules. Your lab's rules come before any AI answer.

## What monozukuri does not do

- Make the final manufacturing data automatically (a person models the final form in CAD)
- Make photorealistic images (the mock is a rough solid for settling the shape)
- Help with maintenance or repair after you start using what you made

## Roadmap

These are planned, in order. They are not in yet.

- Commands for each function (`/monozukuri:help`, `mock`, `coupon`, `measure`, `review`, `feedback`, `compare`, `handoff`, `safety`)
- Export for each slicer, laser software and CAD tool, with a guide to the first steps in each
- Drawings (dimensioned drawings, assembly drawings and parts lists)
- A mode with more explanation for beginners, and a mode with less for experienced users
- Batch generation of variants with different dimensions, and a record of measured values per machine and material

## Layout

```
README.en.md                      English documentation (this file)
.claude-plugin/marketplace.json   Marketplace definition
plugins/monozukuri/               The plugin
  skills/setup/                   Environment setup
  skills/new-project/             Templates, coupons, technical requirement references
  skills/review-page/             Rendering, comparison, review page, feedback
dist/monozukuri.plugin            Package for the Claude app
```

## License

MIT
