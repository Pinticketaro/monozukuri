---
name: new-project
description: >
  This skill should be used when the user says "新しいものづくりを始めたい", "モックから始めたい",
  "プロジェクトの雛形を作って", "レーザーと3Dプリントで〇〇を作りたい", "start a new making project",
  "start from a mock", "make a project template", "I want to make X with a laser cutter and a 3D printer",
  or starts a new physical-making
  project (laser cutting, 3D printing, small enclosures, furniture, gadgets) that should move fast through
  3D mock images and feedback before a human models the final form. Also used for "試し片を作って",
  "カーフを測りたい", "はめあい・公差を決めたい", "インサートの穴径は", "この材料はレーザーで切っていい？",
  "道具を新しくして", "プラグインを更新したので道具を更新して", "サポートが要る所を調べて",
  "このプロジェクトを英語にして", "日本語に戻して", "make coupons", "measure the kerf",
  "decide the fits and tolerances", "what pilot hole for heat-set inserts", "can I laser cut this material?",
  "update the tools", "I updated the plugin, update the tools", "find where support is needed",
  "switch the project to English", "switch the project to Japanese".
  Creates a project with a parameter file (shape + fabrication values with confidence), a mock generator (STL + STEP from one shape definition),
  test-coupon generator, preview/section/compare scripts, stage checklist, handoff docs and git settings,
  and carries digital-fabrication requirements (laser, FDM, data/units, assembly, material safety).
  Narrows fabrication values to the chosen process (laser / FDM / both), flags FDM overhangs that need support,
  and updates an existing project's tools after a plugin update (scaffold.py --update-tools).
  Projects are Japanese or English (meta.lang in the params file; scaffold.py --lang en), switched later through chat.
metadata:
  version: "0.5.0"
---

# 新規プロジェクトの雛形

モックで形と比率を決め、確認ページのフィードバックで版を重ね、固まったら人がモデル化する、という流れのプロジェクトを作る。
雛形は `templates/`（言語によらない道具などは `project/`、言語ごとの文書・寸法ファイル・例の mock.py は `lang/<ja|en>/`、作り方ごとの例は `variants/<作り方>/<ja|en>/`）、作成は `scripts/scaffold.py`。参照資料：
- `references/conventions.md`：モックの細かさ、寸法ファイル、版の回し方
- `references/fab-requirements.md`：レーザー・3Dプリント・データ形式・組み立ての技術要件（数値は「初期値＋信頼度＋測り方」）
- `references/fab-safety.md`：切ってはいけない材料（全面禁止／ラボ次第）
- `references/fab-research-report.md`：上の要件の出典つき全文（数値の根拠を示すときに読む）

前提として持っておく考え方：公開されている数値は初期値。出典どうしのずれが圧入とガタの差ほどあるので、カーフ・実板厚・クリアランス・インサート穴は試し片で測った値を使う。

## 聞き方（選択式の画面）
番号で選ぶ問いの画面（AskUserQuestion）が使えるとき（Claude Code・Claude アプリ）は、足りない情報と決めてほしいことをこれで聞く。
- 1回に4問まで、1問に2〜4択。「その他」（自由入力）は画面が自動で付けるので、選択肢に入れない。
- おすすめの案があれば先頭に置き、名前の最後に「（おすすめ）」を付ける。
- 寸法のような自由な値も、よくある値を2〜3個の選択肢にして、ほかの値は「その他」で受ける（例：缶のサイズ 350ml／500ml／250ml、造形範囲 220×220／256×256／300×300）。
- 5問以上あるときは、大事なものから4問ずつ、2回に分けて聞く。
- 答えは `docs/決定事項.md`（英語のプロジェクトは `docs/decisions.md`。項目・決定・理由・版）と `LOG.md` に残す。
- 画面が使えない環境では、今までどおり文字で、番号付きの選択肢を添えて聞く。

## 言語（日本語・英語）
- ユーザーが書いた言語で答える。問いの画面（AskUserQuestion）の問いと選択肢も、その言語で書く（英語なら「（おすすめ）」は「(Recommended)」）。
- プロジェクトの言語は寸法ファイル（`params/params_vNN.json`）の `meta.lang`：`ja`（日本語）か `en`（英語）。無ければ `ja`（今までのプロジェクトはそのまま日本語で動く）。道具の表示、図の文字、確認ページの画面の言葉はこれに従う。
- 新しいプロジェクトの言語は、会話の言語で決める（英語で話していれば `en`）。どちらとも取れないとき（日本語と英語が混ざる、見る人が別の言語など）だけ、手順1の問いに入れて聞く。
- `scaffold.py --lang en` で作ると `meta.lang` が `en` になり、文書・寸法ファイルの label と basis・例の mock.py が英語になる。省くと環境変数 `MONOZUKURI_LANG`、それも無ければ `ja`。
- 英語のプロジェクトはファイル名も英語になる。この SKILL.md の日本語のファイル名は、英語のプロジェクトでは右の名前に読み替える。

| 日本語のプロジェクト | 英語のプロジェクト |
|---|---|
| `docs/チェックリスト.md` | `docs/checklist.md` |
| `docs/決定事項.md` | `docs/decisions.md` |
| `docs/引き継ぎ.md` | `docs/handoff.md` |
| `measurements/試し片記録.csv` | `measurements/coupon_log.csv` |
| `measurements/実測.md` | `measurements/measured.md` |
| `docs/寸法表_vNN.md`（`tools/dims_sheet.py` が書く） | `docs/dims_vNN.md` |
| `docs/fusion_params_vNN.csv` | 同じ名前 |

- `fab` の `status` は、日本語のプロジェクトでは 初期値／実測／指針／規格／計算／経験則、英語のプロジェクトでは initial／measured／guideline／standard／calculated／rule of thumb（この順で対応する）。
- Claude が書き足す文（`LOG.md`・決定事項・寸法ファイルの label・notes の問い）も、プロジェクトの言語で書く。

**言語を切り替える**（確認ページに切り替えのボタンは無い。チャットで頼まれたときに行う。例「英語にして」「switch this project to Japanese」）
1. いちばん新しい寸法ファイル（`params/params_vNN.json` の NN が最大のもの）の `meta.lang` を書き換える。前の版の寸法ファイルは変えない（その版の記録として残す）。
2. 同じ寸法ファイルの label・basis を新しい言語に書き直し、`status` を上の対応どおりに置き換える。キーと値は変えない。
3. 最新の版を作り直す：`python3 tools/mock.py vNN` → `render_model.py`・`slices.py` → manifest の文（`stage`・`summary`・`changes`・`questions`）を新しい言語に直して（manifest に `"lang"` を書いてあれば、それも直す）`build_page.py`（review-page スキルの手順3〜4）。問いの並びは変えない（答えは問いの番号で結び付いている）。公開しているなら、いつもどおり再公開する。
4. ページの画面の言葉は `review/board.json` の `lang` に従う（`build_page.py` が scene.json の `lang` から入れる）。前の版の画像や文はその版の言語のまま残る。
- 文書のファイルは改名しない。いまあるほうの名前のファイルに書き足す（`docs/決定事項.md` があればそこへ）。訳して名前を変えるのは、ユーザーが望んだときだけ。

## 手順

### 1. 決めることを集める
依頼文・添付（スケッチ、写真、寸法メモ）から読み取り、足りないものだけを、下の「聞き方」に沿って選択式の画面でまとめて聞く。
- 名前と、何を作るか（1行）：依頼文から決められないときだけ聞く（自由入力になるので「その他」で受ける）
- **作り方**（いつも聞く。依頼文で明らかなら確かめるだけ）：「3Dプリントだけ」／「レーザーだけ」／「両方（例：板はレーザー、枠は3Dプリント）」。ここから `--process` を決める（`fdm`／`laser`／`both`）
- プリンタの造形範囲：「220×220（Ender-3 など）」／「256×256（Bambu Lab など）」／「300×300」。レーザーの加工範囲（分かれば）
- 中に入れる物・組み合わせる既製品の大きさ：よくある大きさを選択肢にする（例：350ml／500ml／250ml 缶）。実物があれば実測をお願いする
- 使う材料：フィラメントなら「PLA」／「PETG」／「TPU」、板なら「アクリル 3mm」／「シナベニヤ 4mm」など。レーザーで切る材料は `references/fab-safety.md` に照らし、「全面禁止」なら別の材料を提案、「ラボ次第」なら所属ラボのリストで確かめるよう伝える
- 置き場所：「このPCのフォルダ」／「GitHub のリポジトリ」／「この作業環境だけ」
- 言語：会話の言語で決める（上の「言語」）。迷うときだけ「日本語」／「English」で聞く。ここから `--lang` を決める（`ja`／`en`）


### 作業場所の決め方（手順2の前に）
- **PC のフォルダに置き、PC に描画環境がそろっている**（Claude Code など。setup の表がすべて OK）→ PC で直接作り、描画も PC でする。
- **PC のフォルダに置くが、描画はクラウドでする**（Claude アプリで、PC に描画環境が無い）→ クラウドで作業し、**版ごとに変わったファイルだけ**を PC のフォルダに書き戻す（寸法ファイル、`tools/mock.py`、`out/vNN/` の画像・STEP、`LOG.md`・`docs/` の変えた所、`review/` の増えた分）。tar で丸ごと送らない（同じ名前で上書きすると古い中身が残ることがあり、展開も失敗しやすい）。`.git` は同期しない。git の操作（コミット・push）は PC 側の人か Claude Code が行う。
- **この作業環境だけ** → そのまま作る。
- PC で動かすときは、コマンドの `python3` を setup が示した Python に読み替える（mac では `~/.monozukuri/venv/bin/python`）。

### 2. 雛形を作る
```bash
python3 scripts/scaffold.py --dest <フォルダ> --name "<名前>" --summary "<1行>" \
  --methods "<作り方>" --process <laser|fdm|both> --bed 220x220 [--origin "<原点と向き>"] [--lang <ja|en>] [--git]
```
- `--process` で、寸法ファイルの `fab` がその作り方で使う項目だけになる（3Dプリントだけならカーフ・板厚は入らない）。チェックリスト・引き継ぎ・試し片の案内も、関係しない作り方の項目が外れる。省くと `both`。
- `--lang en` で英語のプロジェクトになる（`meta.lang`、文書とそのファイル名、寸法ファイル、例の mock.py が英語）。`--name`・`--summary`・`--methods`・`--origin` もその言語で書く。省くと `MONOZUKURI_LANG`、無ければ日本語。
- `--methods` は自由な説明として文書に残る（例「本体：3Dプリント（PETG）／ふた：アクリル3mm」）。
- 既存のフォルダに中身があると止まる（上書きしない）。
- 描画・断面・比較・差分のスクリプトは `tools/` にコピーされるので、プロジェクト単体で動く。
- 環境が足りなければ setup スキルを先に実行する。

### 3. 最初のモックを、ユーザーの形に書き換える
雛形の `params/params_v01.json` と `tools/mock.py` の `build()` は例。`laser`・`both` は「アクリル板2枚でPLAの枠を挟む箱」、`fdm` は「缶を入れる底つきの筒＋ストラップを通す耳」。依頼の形に書き換える。
- 形の道具（`tools/geom.py`）：押し出し `slab`、円柱 `cyl`、直方体 `box`、筒 `tube`、円錐台 `cone`、回転体 `revolve`、ストラップを通す耳 `lug_with_slot`。組み合わせは `+`・`-`・`&`、`.translate()`・`.rotate_z()`。
- 寸法は寸法ファイルだけに書き、項目ごとに `label` を付ける。
- **寸法ごとに根拠を残す**：`params` の項目にも `basis`（どこから来た値か）を書く。図面・データシートなら名前とページ（例「公式図面 Raspberry Pi 4 mechanical drawing p.1」）、実測なら「実測（measurements/実測.md）」、決めた値なら「決定事項（v03）」。資料のファイルか URL があれば `ref` に書く（`"ref": "refs/rpi4-mechanical.pdf"`）。
- **資料は `refs/` に置く**：調べて見つけたデータシート・図面（PDF）、ユーザーから届いた写真・寸法メモ、実測の写真を保存し、`refs/資料.md` の表に出典（URL・ページ）・取った日・使った寸法を書く。ライセンスなどで置けないものは URL だけ書く。
- **記憶だけの値を事実のように書かない**：調べずに入れた値は `basis` に「仮（記憶・要確認）」と書き、報告で確かめる先（公式の図面・実物）を伝える。`dims_sheet.py` は根拠の無い寸法を一覧にし、確認ページの「寸法と根拠」でも「根拠なし」と出る。
- 寸法ファイルは `params`（形の寸法）と `fab`（加工の値：実板厚 `t_*`・`kerf`・`clr_*`・`insert_hole` など）に分かれる。`fab` は各項目に `status`（初期値／実測／指針／規格／計算／経験則。英語のプロジェクトは initial／measured／guideline／standard／calculated／rule of thumb）と `basis`（根拠）を持たせる。使う材料・ネジに合わせて項目を足し引きし、初期値は `references/fab-requirements.md` から取る。
- 細部は作らない。形・大きさ・比率・配置がわかる粗さにとどめる（`references/conventions.md`）。
- 寸法から機械的にわかる問題（造形範囲を超える、中身が入らない）は notes に出す。
- ユーザーに決めてほしいことは、notes に問いの候補として構造で書く：`{"q": "抜け止めを付けますか", "type": "yesno", "why": "缶が逆さで落ちる"}`、`{"q": "耳の位置", "type": "options", "options": ["上端", "中ほど"], "why": "…"}`。確認ページでボタンで答えられる問いになる。問いの文はプロジェクトの言語で書く（`"type"` の値は言語によらない）。
- 3Dプリントする部品は、サポートが要りそうな下向きの面（水平から `overhang_deg`＝45° より浅い面）が自動で notes に出る。中身・既製品・レーザーの板など刷らない部品は、部品の6つめに `{"print": False}` を付けて外す。印刷の向きを変えるときは `{"up": "-z"}` など（寸法ファイルの `meta.print_up` でもよい）。`--process laser` のプロジェクトでは調べない。
- わからない寸法は仮の値で進め、寸法ファイルの label に「仮」（英語のプロジェクトは「provisional」）と書き、ユーザーに実測をお願いする項目として報告に入れる。

（案を2つ以上並べて試すときは、版を枝分かれさせる：`params_v04a.json`・`params_v04b.json`、`meta.parent` に分けた元。手順は review-page スキルの「案を分ける」。）

### 4. 1回目の画像を作って見る
```bash
python3 tools/mock.py v01        # CadQuery があれば out/v01/step/ に STEP も出る
python3 tools/render_model.py --scene out/v01/scene.json --out out/v01/preview.png --glb out/v01/model.glb
python3 tools/slices.py --scene out/v01/scene.json --plan out/v01/plan.png --section out/v01/section.png
```
- 画像を Read で1回ずつ見て、依頼の形になっているか確かめる。崩れていれば1回直す。
- README の「決まり」（英語のプロジェクトは「Rules」）の原点・向きを、実際の mock.py に合わせて書き直す。
- `docs/決定事項.md` に、ここまでに決まったこと（作り方、造形範囲など）を理由付きで書く。

### 5. 試し片を用意する（2つめの関所）
形がおおよそ決まったら（または最初から材料が決まっているなら）、試し片を作って渡す。
```bash
python3 tools/coupons.py v01
```
- `out/coupons/` に、寸法ファイルの `fab` にある作り方の分だけ、レーザー用 SVG（カーフ四角・スロットのコーム・差し込む細板）、3Dプリント用 STL（はめあい片・インサート穴片）と、手順と番号表 `coupons.md` ができる。
- ユーザーが切って・刷って測った値を `measurements/試し片記録.csv`（英語のプロジェクトは `measurements/coupon_log.csv`）に書き、寸法ファイルの `fab` を書き換えて status を「実測」（英語のプロジェクトは `measured`）にする（版を上げる）。
- 次は部分試作（ケースの一角：USB切り欠き・ネジボス1つ・中身の角）。mock.py で該当部分を切り出すか、モデル化後に Fusion で切り出す。
- 段階ごとの確認は雛形の `docs/チェックリスト.md`（英語のプロジェクトは `docs/checklist.md`）。

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
- `mock.py.new` と表示の言語は、いちばん新しい寸法ファイルの `meta.lang`（無ければ日本語）。`--lang ja|en` を付けると表示だけがその言語になる（`mock.py.new` は変わらない）。
- 使ったプラグインの版は `tools/.monozukuri-version` に記録される（「0.3.0 → 0.4.0」のように表示）。
- 更新したら review-page の SKILL.md も読み直す（手順や問いの形が変わっていることがある）。

## 報告
2〜3文：何を作ったか、最初のモックで見てほしい所、実測をお願いしたい値。フォルダの中身の列挙はしない。
