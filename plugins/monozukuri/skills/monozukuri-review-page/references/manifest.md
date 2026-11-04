# manifest の欄とエクスポート

`out/vNN/manifest.json` の形は `build_page.py` の冒頭。文の欄（`stage`・`summary`・`changes`・`questions`・`notes`）の書き方は SKILL.md の手順4。下の欄は、`refs` のほかは `make_version.py` が埋める（`prev` も。自分で書いた値があれば、それが残る）。個別のスクリプトで作るときや、足したいものがあるときに書く。
- `images`：1枚目が大きく出る（外観）。平面図・断面は group を分ける
- `params_diff`、`model`（GLB、11MBまで。ページには base64 のテキストとして載る）
- `parts`：`"out/vNN/scene.json"`。部品ごとの STL をエクスポートできるようになる（GLB の部品を英字のキーで分ける）
- `step`：`"out/vNN/step/index.json"`（モックが作る）か `[{"src": "…step", "name": "表示名", "file": "保存名.step"}]`。人が作った STEP もここに足せる
- `compare`：前の版と同じ向きの画像の before/after。案どうしの比較は `references/branches.md`
- `refs`：資料の説明 `[{"src": "refs/xx.png", "caption": "…"}]`（自分で書く。make_version.py は埋めない）

## エクスポート（ページの「エクスポート」）
- 見ている版の STL（部品ごと＋全体1つ）か STEP（組み立て＋部品ごと）を選び、ZIP で保存する。ページの保存機能は .stl / .step を直接は保存できないので ZIP にまとめている。
- STL は GLB から作り直すので、単位 mm・Z が上に戻してある（元の STL と同じ大きさ）。STEP はモックが書いたファイルそのもの。
- STEP は Fusion で開くと部品ごとのコンポーネントになる。モデル化の出発点に使える（最終形は人がモデル化する）。
- `parts` も `step` も無い版では、STL の全体1つだけが出る。
