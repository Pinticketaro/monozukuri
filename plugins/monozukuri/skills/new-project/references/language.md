# 言語（日本語・英語）

new-project と review-page の両方の、英語のプロジェクトと言語の切り替えの決まり。

## プロジェクトの言語
- ユーザーが書いた言語で答える。問いの画面（AskUserQuestion）の問いと選択肢も、その言語で書く（英語なら「（おすすめ）」は「(Recommended)」）。
- プロジェクトの言語はパラメータファイル（`params/params_vNN.json`）の `meta.lang`：`ja`（日本語）か `en`（英語）。無ければ `ja`（今までのプロジェクトはそのまま日本語で動く）。ツールの表示、図の文字、確認ページの画面の言葉はこれに従う。
- 新しいプロジェクトの言語は、会話の言語で決める（英語で話していれば `en`）。どちらとも取れないとき（日本語と英語が混ざる、見る人が別の言語など）だけ、手順1の問いに入れて聞く。
- `scaffold.py --lang en` で作ると `meta.lang` が `en` になり、文書・パラメータファイルの label と basis・例の mock.py が英語になる。省くと環境変数 `MONOZUKURI_LANG`、それも無ければ `ja`。
- 英語のプロジェクトはファイル名も英語になる。SKILL.md の日本語のファイル名は、英語のプロジェクトでは右の名前に読み替える。

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
- Claude が書き足す文（`LOG.md`・決定事項・パラメータファイルの label・notes の問い）も、プロジェクトの言語で書く。

## 確認ページの言語（review-page）
- `tools/mock.py` が `meta.lang` を `out/vNN/scene.json` の `"lang"` に書き、`render_model.py`・`slices.py` は scene.json の `"lang"`、`params_diff.py` はパラメータファイルの `meta.lang` に従う。
- `build_page.py` はページの言語を manifest の `"lang"` ＞ scene.json の `"lang"`（manifest の `parts`）＞ 前の `review/board.json` の `lang` の順で決め、board.json に残す。ページの画面の言葉は board.json の `lang` に従う（切り替えのボタンは置かない）。`serve_review.py` の表示も同じ。
- プロジェクトと違う言語で出したいときだけ `--lang ja|en` を付ける（`render_model.py`・`slices.py`・`build_page.py`。`params_diff.py`・`compare.py`・`serve_review.py` も同じ）。`build_page.py` の `--lang` はページ全体（すべての版の画面の言葉）を変える。プロジェクトと違う言語のページを続けるなら毎回 `--lang` を付ける（ふつうはパラメータファイルの `meta.lang` を変えて、プロジェクトごと切り替える）。
- manifest の文（`stage`・`summary`・`changes`・`questions`・`notes`）と `reply` は、プロジェクトの言語で書く。英語の段階名は Mock／Coupons／Partial prototype／Model (Fusion)／Prototype。
- 「決めてほしいこと」「モックが見つけた注意」などの見出しと、問いの はい／いいえ の表示（英語では Yes／No）は、ページの言語に従う。答えの ID（`yes`／`no`、`a`, `b`…）、`"type"`、フィードバックの `kind`・`status` は言語によらない。

## 言語を切り替える
確認ページに切り替えのボタンは無い。チャットで頼まれたときに行う（例「英語にして」「switch this project to Japanese」）。
1. いちばん新しいパラメータファイル（`params/params_vNN.json` の NN が最大のもの）の `meta.lang` を書き換える。前の版のパラメータファイルは変えない（その版の記録として残す）。
2. 同じパラメータファイルの label・basis を新しい言語に書き直し、`status` を上の対応どおりに置き換える。キーと値は変えない。
3. 最新の版を作り直す：`python3 tools/mock.py vNN` → `render_model.py`・`slices.py` → manifest の文（`stage`・`summary`・`changes`・`questions`）を新しい言語に直して（manifest に `"lang"` を書いてあれば、それも直す）`build_page.py`（review-page スキルの手順3〜4）。問いの並びは変えない（答えは問いの番号で結び付いている）。公開しているなら、いつもどおり再公開する。
4. ページの画面の言葉は `review/board.json` の `lang` に従う（`build_page.py` が scene.json の `lang` から入れる）。前の版の画像や文はその版の言語のまま残る。
- 文書のファイルは改名しない。いまあるほうの名前のファイルに書き足す（`docs/決定事項.md` があればそこへ）。訳して名前を変えるのは、ユーザーが望んだときだけ。
