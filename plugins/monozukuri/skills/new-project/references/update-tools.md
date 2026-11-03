# プラグインを更新したら（既存のプロジェクトのツールを新しくする）

`tools/` はプロジェクトにコピーされるので、プラグインを更新しても既存のプロジェクトは古いツールのままになる。更新したら、まずツールを新しくする。
```bash
python3 scripts/scaffold.py --update-tools <プロジェクトのフォルダ>
```
- 上書きするのはプラグインが管理するファイルだけ（`geom.py`・`common.py`・`coupons.py`・`dims_sheet.py`・`render_model.py`・`slices.py`・`compare.py`・`params_diff.py`・`requirements.txt`）。元は `tools/.backup-<日時>/` に残る。
- `mock.py` は上書きしない（利用者の `build()` があるため）。新しいテンプレートが `tools/mock.py.new` に置かれ、`build()` の外の違いが表示される。新しい枠組みを使うときは、`mock.py.new` の `build()` をプロジェクトの `build()` に置き換えて `mock.py` にする。
  - 0.3.0 以前の `mock.py`（`main()` を持つもの）は、`def main()` から下を消して `if __name__ == "__main__": common.run_mock(build)` にする。中身・既製品など3Dプリントしない部品には、部品の6つめに `{"print": False}` を付ける（オーバーハングの確認から外す）。
- プロジェクトで手を加えたファイルは、足した関数が新しい版にすべてあれば上書きする。新しい版に無い関数があると、何も上書きせずに止まる。その関数を残すかユーザーに確かめ、上書きしてよければ `--force`。
- `mock.py.new` と表示の言語は、いちばん新しいパラメータファイルの `meta.lang`（無ければ日本語）。`--lang ja|en` を付けると表示だけがその言語になる（`mock.py.new` は変わらない）。
- 使ったプラグインの版は `tools/.monozukuri-version` に記録される（「0.3.0 → 0.4.0」のように表示）。
- 更新したら review-page の SKILL.md も読み直す（手順や問いの形が変わっていることがある）。
