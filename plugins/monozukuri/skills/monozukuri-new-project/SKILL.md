---
name: monozukuri-new-project
description: >
  This skill should be used when the user says "新しいものづくりを始めたい", "モックから始めたい",
  "レーザーと3Dプリントで〇〇を作りたい", "テストピースを作って", "カーフを測りたい",
  "はめあい・公差を決めたい", "この材料はレーザーカットしていい？", "ツールを更新して",
  "ライブラリに登録して", "このプロジェクトを英語にして", "start a new making project",
  "make coupons", "measure the kerf", "can I laser cut this material?", "update the tools",
  "switch the project to English".
  Creates a laser-cutting / 3D-printing project (parameter file, mock generator for STL + STEP,
  test coupons, preview scripts, stage checklist) and carries digital-fabrication requirements,
  material safety, a personal library of machines, materials and parts, and tool updates after a plugin update.
license: MIT
compatibility: macOS と Linux（Windows は WSL）。Python 3.10 以上と Node.js が要る。Claude Code・Claude アプリ・Codex などで動く
metadata:
  version: "0.7.0"
---

# 新規プロジェクトのテンプレート

モックで形と比率を決め、確認ページのフィードバックで版を重ね、固まったら人がモデル化する、という流れのプロジェクトを作る。
テンプレートは `templates/`（言語によらないツールなどは `project/`、言語ごとの文書・パラメータファイル・例の mock.py は `lang/<ja|en>/`、加工方法ごとの例は `variants/<加工方法>/<ja|en>/`）、作成は `scripts/scaffold.py`。参照資料：
- `references/conventions.md`：モックの細かさ、パラメータファイル、寸法の根拠と資料、反復の仕方
- `references/fab-requirements.md`：レーザー・3Dプリント・データ形式・組み立ての技術要件（数値は「初期値＋信頼度＋測り方」）
- `references/fab-safety.md`：レーザーカットしてはいけない材料（全面禁止／ラボ次第）
- `references/fab-research-report.md`：上の要件の出典つき全文（数値の根拠を示すときに読む）
- `references/ai-words-ja.md`：AI ワード辞書（日本語で書くときに使わない言い方と、代わりに使う言い方）。日本語の文を書くときはいつもこれに従う
- たまに使うもの：`references/language.md`（英語のプロジェクト・言語の切り替え）、`references/library.md`（ライブラリ）、`references/workplace.md`（PC とクラウドの作業場所）、`references/update-tools.md`（プラグインを更新したら）

前提として持っておく考え方：公開されている数値は初期値。出典どうしのずれが圧入とガタの差ほどあるので、カーフ・実板厚・クリアランス・インサート穴はテストピースで測った値を使う。

## 聞き方（選択式）
足りない情報と決めてほしいことは、選択式の問いの画面があればそれで聞く（Claude の AskUserQuestion など）。無ければ、番号付きの選択肢を文字で添えて聞く（最後に「その他」を付け、「1-2, 2-1 のように番号で答えてください」と添える）。
1回に4問まで（5問以上なら大事なものから2回に分ける）、1問に2〜4択。おすすめの案を先頭に置き、名前の最後に「（おすすめ）」を付ける。寸法のような自由な値も、よくある値を2〜3個の選択肢にする（画面には「その他」が自動で付く）。答えは `docs/決定事項.md`（項目・決定・理由・版）と `LOG.md` に残す。

## 言語
ユーザーが書いた言語で答える。プロジェクトの言語はパラメータファイルの `meta.lang`（`ja`／`en`、無ければ `ja`）。英語のプロジェクト（ファイル名・status の読み替え）と、言語の切り替え（「英語にして」）は `references/language.md` を読む。

## ライブラリ
機材・材料・既製品の寸法を置く個人のライブラリ（`~/.monozukuri/shelf/`。任意で、無くても手順はそのまま動く）。`python3 scripts/shelf.py list` で見て、選択肢に使う。ライブラリを作る・部品を登録する・コマンドの一覧は `references/library.md`（`shelf.py --help` でも出る）。

## 手順

### 1. 決めることを集める
依頼文・添付（スケッチ、写真、寸法メモ）から読み取り、足りないものだけを、上の「聞き方」に沿ってまとめて聞く。
先に `python3 scripts/shelf.py list` でライブラリを見て、ライブラリにある機材・材料・部品を選択肢に使う（ライブラリが無ければ今までどおりの選択肢で聞き、「ライブラリを作りますか」を1問足してよい）。
- 名前と、何を作るか（1行）：依頼文から決められないときだけ聞く（自由入力になるので「その他」で受ける）
- **加工方法**（いつも聞く。依頼文で明らかなら確かめるだけ）：「3Dプリントだけ」／「レーザーだけ」／「両方（例：板はレーザー、枠は3Dプリント）」。ここから `--process` を決める（`fdm`／`laser`／`both`）
- 使うプリンター：ライブラリのプリンターを選択肢にする（例「Ender-3 S1 Pro（220×220×270）」）。ライブラリが無ければ造形範囲で聞く：「220×220（Ender-3 など）」／「256×256（Bambu Lab など）」／「300×300」。レーザー加工機もライブラリにあれば選ぶ（加工範囲は分かれば）
- 中に入れる物・組み合わせる既製品の大きさ：部品ライブラリにあればそれを選択肢の先頭にする（`shelf.py use` で入れる。図面を探し直さない）。無ければよくある大きさを選択肢にする（例：350ml／500ml／250ml 缶）。実物があれば実測をお願いする
- 使う材料：ライブラリの材料（実測があるもの）を先に出す。無ければフィラメントなら「PLA」／「PETG」／「TPU」、板なら「アクリル 3mm」／「シナベニヤ 4mm」など。レーザーカットする材料は `references/fab-safety.md` に照らし、「全面禁止」なら別の材料を提案、「ラボ次第」なら所属ラボのリストで確かめるよう伝える
- 置き場所：「このPCのフォルダ」／「GitHub のリポジトリ」／「この作業環境だけ」
- 言語：会話の言語で決める（英語で話していれば `en`）。迷うときだけ「日本語」／「English」で聞く。ここから `--lang` を決める（`ja`／`en`）


### 作業場所の決め方（手順2の前に）
- PC のフォルダに置き、PC にレンダリング環境がそろっていれば（monozukuri-setup の表がすべて OK）、PC で直接作り、レンダリングも PC でする。コマンドの `python3` は monozukuri-setup が示した Python に読み替える（mac では `~/.monozukuri/venv/bin/python`）。
- クラウドの作業環境だけで作るときは、その中に作る（確認ページを PC のブラウザで開けないときは、画像で確かめてもらう）。
- PC のフォルダに置くがレンダリングはクラウドでするとき（Claude アプリで、PC にレンダリング環境が無い）は、`references/workplace.md` を読む。

### 2. テンプレートからプロジェクトを作る
```bash
python3 scripts/scaffold.py --dest <フォルダ> --name "<名前>" --summary "<1行>" \
  --methods "<加工方法>" --process <laser|fdm|both> --bed 220x220 [--origin "<原点と向き>"] [--lang <ja|en>] [--git] \
  [--printer <ライブラリのプリンター>] [--laser <ライブラリのレーザー加工機>] [--material <ライブラリの材料> ...]
```
- ライブラリの機材・材料を選んだら `--printer`・`--laser`・`--material` で渡し、`--bed` は省く（実測があれば `fab` に最初から入る）。引数の詳しい説明は `scaffold.py --help`。
- `--name`・`--summary`・`--methods`・`--origin` はプロジェクトの言語で書く。`--methods` は自由な説明として文書に残る（例「本体：3Dプリント（PETG）／ふた：アクリル3mm」）。
- 既存のフォルダに中身があると止まる（上書きしない）。環境が足りなければ monozukuri-setup スキルを先に実行する。

### 3. 最初のモックを、ユーザーの形に書き換える
テンプレートの `params/params_v01.json` と `tools/mock.py` の `build()` は例。`laser`・`both` は「アクリル板2枚でPLAの枠を挟む箱」、`fdm` は「缶を入れる底つきの筒＋ストラップホール付きのラグ」。依頼の形に書き換える。
- 形の関数（`tools/geom.py`）：押し出し `slab`、円柱 `cyl`、直方体 `box`、筒 `tube`、円錐台 `cone`、回転体 `revolve`、ストラップホール付きのラグ `lug_with_slot`。組み合わせは `+`・`-`・`&`、`.translate()`・`.rotate_z()`。
- 寸法はパラメータファイルだけに書き、項目ごとに `label` と `basis`（どこから来た値か）を付ける。資料（図面・データシート・写真）は `refs/` に置き、`refs/資料.md` に出典を書く。調べずに入れた値は `basis` に「仮（記憶・要確認）」。書き方は `references/conventions.md` の「寸法の根拠と資料」。
- 部品ライブラリにある部品は `shelf.py use` で入れ、図面で確かめた既製品の寸法はユーザーに確かめてから `shelf.py add-part` で登録する（`references/library.md`）。
- パラメータファイルは `params`（形の寸法）と `fab`（加工パラメータ：実板厚 `t_*`・`kerf`・`clr_*`・`insert_hole` など）に分かれる。`fab` は各項目に `status`（初期値／実測／指針／規格／計算／経験則。英語のプロジェクトは initial／measured／guideline／standard／calculated／rule of thumb）と `basis`（根拠）を持たせる。使う材料・ネジに合わせて項目を足し引きし、初期値は `references/fab-requirements.md` から取る。
- 細部は作らない。形・大きさ・比率・配置がわかる粗さにとどめる（`references/conventions.md`）。
- 寸法から機械的にわかる問題（造形範囲を超える、中身が入らない）は notes に出す。
- ユーザーに決めてほしいことは、notes に問いの候補として構造で書く：`{"q": "抜け止めを付けますか", "type": "yesno", "why": "缶が逆さで落ちる"}`、`{"q": "ラグの位置", "type": "options", "options": ["上端", "中ほど"], "why": "…"}`。確認ページでボタンで答えられる問いになる。問いの文はプロジェクトの言語で書く（`"type"` の値は言語によらない）。
- 3Dプリントする部品は、サポートが要りそうなオーバーハング面（水平から `overhang_deg`＝45° より浅い面）が自動で notes に出る。中身・既製品・レーザーの板など印刷しない部品は、部品の6つめに `{"print": False}` を付けて外す。印刷の向きを変えるときは `{"up": "-z"}` など（パラメータファイルの `meta.print_up` でもよい）。`--process laser` のプロジェクトでは調べない。
- わからない寸法は仮の値で進め、パラメータファイルの label に「仮」（英語のプロジェクトは「provisional」）と書き、ユーザーに実測をお願いする項目として報告に入れる。

（案を2つ以上並べて試すときは、版をブランチに分ける：`params_v04a.json`・`params_v04b.json`、`meta.parent` に分けた元。手順は monozukuri-review-page スキルの `references/branches.md`。）

### 4. 1回目の画像を作って見る
```bash
python3 tools/mock.py v01        # CadQuery があれば out/v01/step/ に STEP も出る
python3 tools/render_model.py --scene out/v01/scene.json --out out/v01/preview.png --glb out/v01/model.glb
python3 tools/slices.py --scene out/v01/scene.json --plan out/v01/plan.png --section out/v01/section.png
```
- 画像を見る機能で1回ずつ開いて（Claude は Read）、依頼の形になっているか確かめる。崩れていれば1回直す。見られない環境では、ユーザーに開いてもらい、気になる所を聞く。
- README の「決まり」（英語のプロジェクトは「Rules」）の原点・向きを、実際の mock.py に合わせて書き直す。
- `docs/決定事項.md` に、ここまでに決まったこと（加工方法、造形範囲など）を理由付きで書く。

### 5. テストピースを用意する（2つめのステージゲート）
形がおおよそ決まったら（または最初から材料が決まっているなら）、テストピースを作って渡す。
```bash
python3 tools/coupons.py v01
```
- `out/coupons/` に、パラメータファイルの `fab` にある加工方法の分だけ、レーザー用 SVG（カーフテスト・スロットのコーム・タブ）、3Dプリント用 STL（はめあいテストピース・インサート穴テストピース）と、手順と番号表 `coupons.md` ができる。
- ユーザーがカット・印刷して測った値を `measurements/試し片記録.csv`（英語のプロジェクトは `measurements/coupon_log.csv`）に書き、パラメータファイルの `fab` を書き換えて status を「実測」（英語のプロジェクトは `measured`）にする（版を上げる）。basis に測った日（YYYY-MM-DD）と条件を書く。
- 測った値はライブラリに残す：`python3 scripts/shelf.py record <プロジェクト>`（`meta` に機材・材料が無い古いプロジェクトは `--machine <ライブラリの機材> --material <材料>`。レーザーの値と3Dプリントの値は機材ごとに分けて2回）。次のプロジェクトでは `scaffold.py --printer … --material …` で最初から入る。
- 次は部分試作（ケースの一角：USB切り欠き・ネジボス1つ・中身の角）。mock.py で該当部分を取り出すか、モデル化後に Fusion で取り出す。
- 段階ごとの確認はテンプレートの `docs/チェックリスト.md`（英語のプロジェクトは `docs/checklist.md`）。

### 6. 確認ページへ進む
外観画像をユーザーに見せ（ファイルを送る機能があれば送る。Claude の SendUserFile など。無ければ `out/v01/preview.png` のパスを伝える）、monozukuri-review-page スキルで確認ページを作る。以後は monozukuri-review-page の手順で反復する（2つ目の版からは monozukuri-review-page の `make_version.py` で、モックからページまで1回で作る）。
`--git` で作った場合は最初のコミットまでできている。GitHub に上げるのはユーザーが望んだときだけ。

## プラグインを更新したら
既存のプロジェクトの `tools/` は古いままなので、「ツールを更新して」と頼まれたら `references/update-tools.md` を読んで `python3 scripts/scaffold.py --update-tools <プロジェクトのフォルダ>` を実行する。

## 報告
2〜3文：何を作ったか、最初のモックで見てほしい所、実測をお願いしたい値。フォルダの中身の列挙はしない。
最後に1行：「続きは新しい会話で『<プロジェクト名>の続き』と頼むと、トークンを節約できます（状態はファイルに残っています）」。
