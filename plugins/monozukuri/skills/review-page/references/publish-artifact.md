# Artifact で公開する（Claude アプリなど、Artifact ツールが使える環境）

Artifact ツールで公開できない環境（Claude Code など）では使わない。SKILL.md の手順5「PC で開く」に進む。

Artifact ツールで公開する。`root` はプロジェクトのフォルダ、`file_path` は `review/index.html`、`files` は一覧ファイル（`build_page.py` が作る `review/publish_vNN.json`、初回は `publish_all.json`）の `files` をそのまま渡す。
**毎回**（初回も2回目以降も）`capabilities: {"db": {}, "user": {"scopes": ["profile"]}, "downloads": true}` を3つそろえて渡す。省いたり一部だけ渡したりしない（省くと前の宣言のままになり、古いページでは「エクスポート」が使えない。一部だけ渡すと、渡さなかったものが外れる）。
- **初回**：`files` は `publish_all.json`。`icon: "ruler"`、`description` は1文。公開後、URL を `review/artifact.json` に `{"url": "..."}` で保存する。続けて `ArtifactData` で `feedback` を1回 `list` して、読めることを確かめる（空でよい）。
- **2回目以降**：`url` に既存の URL、`files` は `publish_vNN.json`（増えたファイルだけ。残りはそのまま残る）。`icon` は省く。
- 作業ディレクトリかスクラッチパッドの外にあるプロジェクトは公開できないので、その場合は作業ディレクトリにコピーしてから行う。
- フィードバックを読む・閉じるのは SKILL.md の手順2・6（`ArtifactData`。ToolSearch で読み込む）。
