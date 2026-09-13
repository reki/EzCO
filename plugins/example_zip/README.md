# Example ZIP Loader

確認用のアーカイブプラグインです。`.zip` をプラグイン経由で開き、中の画像をページとして表示します。暗号化 ZIP（ZipCrypto / AES）は本体のパスワードダイアログ（`host.ask_password`）を使います。開いた画像には色とラベルを重ねます。本番向けではありません。

| 項目 | 値 |
| --- | --- |
| ID | `com.ezco.example.zip` |
| バージョン | `1.1.0` |
| 種別 | ファイル（アーカイブ） |
| ZIP | `dist-sample-plugins/example_zip.zip` |
| 入口 | `loader:FileLoader` |

## 使い方

1. `example_zip.zip` を実行ファイル旁の `plugins/` 直下に置く
2. EzCo を起動（追加したあとは再起動）
3. プラグイン設定でこのプラグインを有効にする
4. `.zip` の読み込み方式をこのプラグインにする（既定はビルドイン）

パスワード付き ZIP では本体の入力ダイアログが出ます。キャンセルすると開けません。

設定項目と独自アクションはありません。

## 開発

ソースは `plugins/example_zip/` です。`pyzipper` は本体依存です。データフォルダの `plugins/` にこのフォルダを置けばそのまま読めます。配布 ZIP は `dist-sample-plugins/` です。

ホスト API の一覧はユーザーマニュアルの [プラグインリファレンス](../../resources/UserManual/files/plugin-reference.html) と [docs/plugins.md](../../docs/plugins.md) を見てください。
