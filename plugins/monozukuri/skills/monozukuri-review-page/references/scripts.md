# 個別のスクリプト（細かく指定したいとき）

ふつうは `make_version.py` が下の順に実行する。別の向き・別の位置の断面が要るとき、人が作ったモデルを載せるときに、個別に使う。`<scripts>` はこのスキルの `scripts/`、`<python>` は monozukuri-setup が記録した Python（SKILL.md の冒頭）。
作った画像は manifest の `images`（または `compare`）に足して、`make_version.py <プロジェクト> vNN --page-only` でページに載せる。

## モックの場合（プロジェクトに `tools/mock.py` がある）
```bash
<python> tools/mock.py vNN        # CadQuery があれば out/vNN/step/ に STEP も出る（「STEP の大きさの確認: すべて一致」／英語では「STEP size check: all match」を確かめる）
<python> <scripts>/render_model.py --scene out/vNN/scene.json --out out/vNN/preview.png --glb out/vNN/model.glb
<python> <scripts>/slices.py --scene out/vNN/scene.json --plan out/vNN/plan.png --section out/vNN/section.png
<python> <scripts>/params_diff.py params/params_vPP.json params/params_vNN.json --json out/vNN/params_diff.json
```

## 人が作ったモデルの場合（Fusion などから STL / OBJ / 3MF / STEP）
- 部品ごとのファイルを `out/vNN/model/` に置き、`out/vNN/scene.json` を書く（部品名・色・不透明度。形は `render_model.py` の冒頭の説明）。上方向は Fusion の既定なら `"up": "z"`。
- 同じく `render_model.py`（`--glb` も）と `slices.py` を実行する。STEP は cascadio が要る。
- モックの版と並べると、モデル化でどこが変わったかが一目でわかる。

## 図の作り方
- 平行投影（`top`・`front`・`side`）には稜線が重なるので、穴や段差の確認には `--views "iso,top,side"` などを使う。
- 平行投影はビューごとに枠いっぱいにレンダリングし、隅に縮尺の目安（「スケールバー 20mm」）が入る。上面と正面などの大きさを同じ縮尺で見比べたいときは `--same-scale`。
- 前の版と同じ向きの画像を `compare` に before/after で渡すと、ページで重ねて動かせる。並べた静止画が要るときは `compare.py`（差分を赤で強調）。
- 断面の位置は見たい所に合わせる：`--at x=値` / `--at y=値`、拡大は `"--zoom=a,b"`。
- 平面図は、各部品の高さの中央の断面（濃い線）に、上面から見た外形（薄い面）を重ねる。断面の高さを決めたいときは `--plan-z "45,80"`。
- 図の文字（ビュー名・スケールバー・見出し）は scene.json の `"lang"`（パラメータファイルの `meta.lang`）の言語になる。プロジェクトと違う言語の図が要るときだけ `render_model.py`・`slices.py` に `--lang ja|en` を付ける（`params_diff.py` も同じ）。

## ページを作る（build_page.py）
```bash
<python> <scripts>/build_page.py --root <プロジェクト> --manifest out/vNN/manifest.json   # 違う言語のページにするときだけ --lang ja|en
```
- `review/index.html` と、公開に使うファイル一覧 `review/publish_vNN.json`（初回は `publish_all.json`）ができる。
- `build_page.py` は、その版のパラメータファイル（`params/params_vNN.json`。別のファイルなら manifest の `"dims"`）の全項目を「寸法と根拠」としてページに載せ、プロジェクトの `refs/` の資料（図面・データシート・写真）を「資料」に載せる。資料の説明は manifest の `"refs": [{"src": "refs/xx.png", "caption": "…"}]`。文字の資料（`.md`・`.txt`・`.csv`）は、ページの中の窓で UTF-8 として開く（Markdown の表・見出しはそのまま読める形に、CSV は表にする）。根拠の無い寸法は「根拠なし」と出るので、載せる前に `basis` を埋める。
- `scene.json` の `notes`（モックが見つけたこと）は、manifest の `parts` に scene.json を渡すと `build_page.py` が読む。問いの候補（`{"q": …, "type": "yesno"|"options", …}`）は「決めてほしいこと」に、文字だけのものは「モックが見つけた注意」としてメモに載る。
- ページの言語の決まりは monozukuri-new-project スキルの `references/language.md`。
