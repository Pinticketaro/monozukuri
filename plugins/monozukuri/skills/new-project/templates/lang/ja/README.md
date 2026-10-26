# {{NAME}}

{{SUMMARY}}

## このリポジトリの進め方

モックで形と大きさを決め、確認ページでフィードバックを集めて版を重ねる。形が固まったら、寸法表と画像を渡して Fusion などで人がモデル化する。

4つの関所で進める：**モック → 試し片 → 部分試作 → 本番**（`docs/チェックリスト.md`）。

1. **寸法を変える**：`params/params_vNN.json` を1つ上の版としてコピーして書き換える（1つの版で変える条件はなるべく1つ）
2. **モックと図を作る**：下の「生成コマンド」
3. **確認ページに載せて見る・書く**：`review/`（monozukuri プラグインの確認ページ）
4. **フィードバックを次の版に反映**し、`LOG.md` に記録してコミット
5. **試し片で加工の値を決める**：`tools/coupons.py` で作って切る・刷る → `measurements/試し片記録.csv` → 寸法ファイルの `fab` を「実測」に
6. **形が固まったら引き継ぐ**：`docs/寸法表_vNN.md`・`docs/fusion_params_vNN.csv` と画像を渡してモデル化（`docs/引き継ぎ.md`）。モデル化した結果（STL / STEP）も同じ確認ページで見られる

## 生成コマンド

```
python3 tools/mock.py vNN                     # モック → out/vNN/parts/*.stl, out/vNN/scene.json, out/vNN/step/*.step（CadQuery があるとき）
python3 tools/render_model.py --scene out/vNN/scene.json --out out/vNN/preview.png --glb out/vNN/model.glb
python3 tools/slices.py --scene out/vNN/scene.json --plan out/vNN/plan.png --section out/vNN/section.png
python3 tools/compare.py out/vPP/preview.png out/vNN/preview.png --out out/vNN/compare.png --labels vPP vNN
python3 tools/params_diff.py params/params_vPP.json params/params_vNN.json --json out/vNN/params_diff.json
python3 tools/dims_sheet.py vNN               # 引き継ぎ用の寸法表 → docs/寸法表_vNN.md と docs/fusion_params_vNN.csv
python3 tools/coupons.py vNN                  # 試し片 → out/coupons/（作り方に応じてレーザーのSVG・3DプリントのSTLと、説明 coupons.md）
```

モックの STEP（`out/vNN/step/assembly_vNN.step`）は Fusion で開くと部品ごとのコンポーネントになり、モデル化の出発点に使える。確認ページの「書き出す」からも STL / STEP を ZIP で保存できる。

Fusion などで作ったモデルを見るとき：`python3 tools/render_model.py frame.step:#d9d4cb top.stl:#bcd6e4:0.6 --out out/vNN/model_preview.png`

必要なもの：`pip install -r tools/requirements.txt`、three.js（monozukuri の setup で入る）

## フォルダ

| フォルダ | 中身 |
|---|---|
| `params/` | 版ごとの寸法（`params`＝形の寸法、`fab`＝試し片で決める加工の値。数値はここだけに書く） |
| `tools/` | モック・描画・断面・比較・寸法表のスクリプト |
| `out/` | 版ごとの出力（画像は残す、STL・STEP・GLB は作り直せるので Git に入れない） |
| `review/` | 確認ページ（公開用） |
| `docs/` | 決定事項、引き継ぎ、寸法表 |
| `measurements/` | 実物の実測値、試し片の記録 |
| `photos/` | 試作・試し刷り・切断の写真（定規を一緒に写す） |
| `LOG.md` | 製作ログ |

## 決まり

- **単位はmm、原点と向き**：{{ORIGIN}}。全部のソフト・スクリプトでそろえる
- **版番号**：寸法ファイル・出力・画像に `vNN` を付ける（`out/v03/preview.png`）
- **コミット＝製作ログ**：「何を変えた → どう見えた／どうだった → 次に何を試す」
- **実物を作ったらタグ**：`proto-1`、`cut-test-1` など
- **モックは見た目と比率の確認用**。製造用のデータは、モデル化した結果から作る
- **公開されている数値は初期値**。加工の値（寸法ファイルの `fab`）は試し片で測った値を使う
- **読み込んだら1寸法を測る**（単位の取り違え：25.4倍・1000倍）
