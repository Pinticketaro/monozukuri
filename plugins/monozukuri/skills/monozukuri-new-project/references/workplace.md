# 作業場所の決め方（PC とクラウド）

monozukuri-new-project の手順2の前に、どこで作ってどこでレンダリングするかを決める。
- **PC のフォルダに置き、PC にレンダリング環境がそろっている**（Claude Code など。monozukuri-setup の表がすべて OK）→ PC で直接作り、レンダリングも PC でする。
- **PC のフォルダに置くが、レンダリングはクラウドでする**（Claude アプリで、PC にレンダリング環境が無い）→ クラウドで作業し、**版ごとに変わったファイルだけ**を PC のフォルダに書き戻す（パラメータファイル、`tools/mock.py`、`out/vNN/` の画像・STEP、`LOG.md`・`docs/` の変えた所、`review/` の増えた分）。tar で丸ごと送らない（同じ名前で上書きすると古い中身が残ることがあり、展開も失敗しやすい）。`.git` は同期しない。git の操作（コミット・push）は PC 側の人か Claude Code が行う。
- **この作業環境だけ** → そのまま作る。
- コマンドの `<python>` は、monozukuri-setup が記録した Python（SKILL.md の冒頭。mac・Windows の PC では仮想環境の Python、クラウドの作業環境では `python3`）。
