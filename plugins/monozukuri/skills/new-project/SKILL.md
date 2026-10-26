---
name: new-project
description: >
  This skill should be used when the user says "新しいものづくりを始めたい", "モックから始めたい",
  "プロジェクトの雛形を作って", "レーザーと3Dプリントで〇〇を作りたい", or starts a new physical-making
  project (laser cutting, 3D printing, small enclosures, furniture, gadgets) that should move fast through
  3D mock images and feedback before a human models the final form. Also used for "試し片を作って",
  "カーフを測りたい", "はめあい・公差を決めたい", "インサートの穴径は", "この材料はレーザーで切っていい？".
  Creates a project with a parameter file (shape + fabrication values with confidence), a mock generator (STL + STEP from one shape definition),
  test-coupon generator, preview/section/compare scripts, stage checklist, handoff docs and git settings,
  and carries digital-fabrication requirements (laser, FDM, data/units, assembly, material safety).
metadata:
  version: "0.3.0"
---

# 新規プロジェクトの雛形

モックで形と比率を決め、確認ページのフィードバックで版を重ね、固まったら人がモデル化する、という流れのプロジェクトを作る。
雛形は `templates/project/`、作成は `scripts/scaffold.py`。参照資料：
- `references/conventions.md`：モックの細かさ、寸法ファイル、版の回し方
- `references/fab-requirements.md`：レーザー・3Dプリント・データ形式・組み立ての技術要件（数値は「初期値＋信頼度＋測り方」）
- `references/fab-safety.md`：切ってはいけない材料（全面禁止／ラボ次第）
- `references/fab-research-report.md`：上の要件の出典つき全文（数値の根拠を示すときに読む）

前提として持っておく考え方：公開されている数値は初期値。出典どうしのずれが圧入とガタの差ほどあるので、カーフ・実板厚・クリアランス・インサート穴は試し片で測った値を使う。

## 手順

### 1. 決めることを集める
依頼文・添付（スケッチ、写真、寸法メモ）から読み取り、足りないものだけ AskUserQuestion で1回にまとめて聞く。
- 名前と、何を作るか（1行）
- 作り方：どの部品をレーザー・3Dプリント・既製品にするか。ここから `--process` を決める（レーザーだけ＝`laser`、3Dプリントだけ＝`fdm`、両方＝`both`）
- プリンタの造形範囲（例 220×220）、レーザーの加工範囲（分かれば）
- 中に入れる物・組み合わせる既製品の大きさ（実物があれば実測をお願いする）
- 使う材料（板の種類と厚み、フィラメント）。レーザーで切る材料は `references/fab-safety.md` に照らし、「全面禁止」なら別の材料を提案、「ラボ次第」なら所属ラボのリストで確かめるよう伝える
- 置き場所：GitHub のリポジトリにするか、ユーザーのPCのフォルダか、この作業環境だけか

### 2. 雛形を作る
```bash
python3 scripts/scaffold.py --dest <フォルダ> --name "<名前>" --summary "<1行>" \
  --methods "<作り方>" --process <laser|fdm|both> --bed 220x220 [--origin "<原点と向き>"] [--git]
```
- `--process` で、寸法ファイルの `fab` がその作り方で使う項目だけになる（3Dプリントだけならカーフ・板厚は入らない）。チェックリスト・引き継ぎ・試し片の案内も、関係しない作り方の項目が外れる。省くと `both`。
- `--methods` は自由な説明として文書に残る（例「本体：3Dプリント（PETG）／ふた：アクリル3mm」）。
- 既存のフォルダに中身があると止まる（上書きしない）。
- 描画・断面・比較・差分のスクリプトは `tools/` にコピーされるので、プロジェクト単体で動く。
- 環境が足りなければ setup スキルを先に実行する。

### 3. 最初のモックを、ユーザーの形に書き換える
雛形の `params/params_v01.json` と `tools/mock.py` の `build()` は例。`laser`・`both` は「アクリル板2枚でPLAの枠を挟む箱」、`fdm` は「缶を入れる底つきの筒＋ストラップを通す耳」。依頼の形に書き換える。
- 形の道具（`tools/geom.py`）：押し出し `slab`、円柱 `cyl`、直方体 `box`、筒 `tube`、円錐台 `cone`、回転体 `revolve`、ストラップを通す耳 `lug_with_slot`。組み合わせは `+`・`-`・`&`、`.translate()`・`.rotate_z()`。
- 寸法は寸法ファイルだけに書き、項目ごとに `label` を付ける。
- 寸法ファイルは `params`（形の寸法）と `fab`（加工の値：実板厚 `t_*`・`kerf`・`clr_*`・`insert_hole` など）に分かれる。`fab` は各項目に `status`（初期値／実測／指針／規格／計算）と `basis`（根拠）を持たせる。使う材料・ネジに合わせて項目を足し引きし、初期値は `references/fab-requirements.md` から取る。
- 細部は作らない。形・大きさ・比率・配置がわかる粗さにとどめる（`references/conventions.md`）。
- 寸法から機械的にわかる問題（造形範囲を超える、中身が入らない）は notes に出す。
- ユーザーに決めてほしいことは、notes に問いの候補として構造で書く：`{"q": "抜け止めを付けますか", "type": "yesno", "why": "缶が逆さで落ちる"}`、`{"q": "耳の位置", "type": "options", "options": ["上端", "中ほど"], "why": "…"}`。確認ページでボタンで答えられる問いになる。
- 3Dプリントする部品は、サポートが要りそうな下向きの面（水平から `overhang_deg`＝45° より浅い面）が自動で notes に出る。中身・既製品・レーザーの板など刷らない部品は、部品の6つめに `{"print": False}` を付けて外す。印刷の向きを変えるときは `{"up": "-z"}` など（寸法ファイルの `meta.print_up` でもよい）。`--process laser` のプロジェクトでは調べない。
- わからない寸法は仮の値で進め、寸法ファイルの label に「仮」と書き、ユーザーに実測をお願いする項目として報告に入れる。

### 4. 1回目の画像を作って見る
```bash
python3 tools/mock.py v01        # CadQuery があれば out/v01/step/ に STEP も出る
python3 tools/render_model.py --scene out/v01/scene.json --out out/v01/preview.png --glb out/v01/model.glb
python3 tools/slices.py --scene out/v01/scene.json --plan out/v01/plan.png --section out/v01/section.png
```
- 画像を Read で1回ずつ見て、依頼の形になっているか確かめる。崩れていれば1回直す。
- README の「決まり」の原点・向きを、実際の mock.py に合わせて書き直す。
- `docs/決定事項.md` に、ここまでに決まったこと（作り方、造形範囲など）を理由付きで書く。

### 5. 試し片を用意する（2つめの関所）
形がおおよそ決まったら（または最初から材料が決まっているなら）、試し片を作って渡す。
```bash
python3 tools/coupons.py v01
```
- `out/coupons/` に、寸法ファイルの `fab` にある作り方の分だけ、レーザー用 SVG（カーフ四角・スロットのコーム・差し込む細板）、3Dプリント用 STL（はめあい片・インサート穴片）と、手順と番号表 `coupons.md` ができる。
- ユーザーが切って・刷って測った値を `measurements/試し片記録.csv` に書き、寸法ファイルの `fab` を書き換えて status を「実測」にする（版を上げる）。
- 次は部分試作（ケースの一角：USB切り欠き・ネジボス1つ・中身の角）。mock.py で該当部分を切り出すか、モデル化後に Fusion で切り出す。
- 段階ごとの確認は雛形の `docs/チェックリスト.md`。

### 6. 確認ページへつなぐ
外観画像をユーザーに見せ（SendUserFile）、review-page スキルで確認ページを作って公開する。以後は review-page の手順で版を回す。
`--git` で作った場合は最初のコミットまでできている。GitHub に上げるのはユーザーが望んだときだけ。

## プラグインを更新したら（既存のプロジェクトの道具を新しくする）
`tools/` はプロジェクトにコピーされるので、プラグインを更新しても既存のプロジェクトは古い道具のままになる。更新したら、まず道具を新しくする。
```bash
python3 scripts/scaffold.py --update-tools <プロジェクトのフォルダ>
```
- 上書きするのはプラグインが持ち主のファイルだけ（`geom.py`・`common.py`・`coupons.py`・`dims_sheet.py`・`render_model.py`・`slices.py`・`compare.py`・`params_diff.py`・`requirements.txt`）。元は `tools/.backup-<日時>/` に残る。
- `mock.py` は上書きしない（利用者の `build()` があるため）。新しい雛形が `tools/mock.py.new` に置かれ、`build()` の外の違いが表示される。新しい枠組みを使うときは、`mock.py.new` の `build()` をプロジェクトの `build()` に置き換えて `mock.py` にする。
  - 0.3.0 以前の `mock.py`（`main()` を持つもの）は、`def main()` から下を消して `if __name__ == "__main__": common.run_mock(build)` にする。中身・既製品など3Dプリントしない部品には、部品の6つめに `{"print": False}` を付ける（張り出しの確認から外す）。
- プロジェクトで手を加えたファイルは、足した関数が新しい版にすべてあれば上書きする。新しい版に無い関数があると、何も上書きせずに止まる。その関数を残すかユーザーに確かめ、上書きしてよければ `--force`。
- 使ったプラグインの版は `tools/.monozukuri-version` に記録される（「0.3.0 → 0.4.0」のように表示）。
- 更新したら review-page の SKILL.md も読み直す（手順や問いの形が変わっていることがある）。

## 報告
2〜3文：何を作ったか、最初のモックで見てほしい所、実測をお願いしたい値。フォルダの中身の列挙はしない。
