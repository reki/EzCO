# Example Filter

確認用の表示フィルターです。開いている画像に青緑の色とラベルを重ねます。文字サイズは `int_range` で、`sync=True` と `reload=True` を付けています。本番向けではありません。

| 項目 | 値 |
| --- | --- |
| ID | `com.ezco.example.filter` |
| バージョン | `1.0.0` |
| 種別 | フィルター |
| ZIP | `dist-sample-plugins/example_filter-1.0.0.zip` |
| 入口 | `plugin:ExampleFilterPlugin` |
| LICENSE | ルートの `LICENSE.md` |
| 公開 ID | `plugin:com.ezco.example.filter:overlay` |

プラグインを ON にしただけでは `process` は走りません。フィルターメニューで「重ね表示」を有効にしてください。ON と pipe は別です。

`config_types` の `int_range` は `sync` のみです。こちらは `reload` も付けて、スライダー後に表示が更新されるところまで見ます。

## 使い方

1. `example_filter-1.0.0.zip`、またはこのフォルダをデータフォルダの `plugins/` 直下に置く
2. EzCo を起動（追加したあとは再起動）
3. プラグイン設定でこのプラグインを有効にする
4. 画像を開く
5. フィルターメニューの「重ね表示」を有効にする
6. 同じメニューの設定、またはプラグイン設定の「設定」で文字サイズを動かす

スライダーを止めて 0.5 秒待つと保存され、ラベルの大きさが変わります。確認が終わったらフィルターを無効にしてください。

## 開発

ソースは `plugins/example_filter/` です。データフォルダの `plugins/` にこのフォルダを置けばそのまま読めます。配布 ZIP は `dist-sample-plugins/` です。

ホスト API の一覧はユーザーマニュアルの [プラグインリファレンス](../../resources/UserManual/files/plugin-reference.html) と [docs/plugins.md](../../docs/plugins.md) を見てください。
