# Error Setup Probe

確認用です。`setup()` で必ず例外を出します。本番では使いません。

| 項目 | 値 |
| --- | --- |
| ID | `com.ezco.error_setup` |
| バージョン | `1.0.0` |
| 種別 | サイドバー（setup のみ） |
| ZIP | `dist-sample-plugins/error_setup.zip` |
| 入口 | `plugin:ErrorSetupPlugin` |
| LICENSE | `LICENSE.md` / `LICENSE.txt` / `LICENSE` を同梱。表示は `LICENSE.md` になること |

## 使い方

1. `error_setup.zip` を実行ファイル旁の `plugins/` 直下に置く
2. EzCo を起動（追加したあとは再起動）
3. プラグイン設定でこのプラグインを有効にして適用する
4. 状態列が「失敗」になることを確認する
5. 開発タブの「エラー時にエラーログを表示する」が ON なら、スタックトレースダイアログも出る

確認が終わったらプラグインを無効にしてください。

## 開発

ソースは `plugins/error_setup/` です。データフォルダの `plugins/` にこのフォルダを置けばそのまま読めます。配布 ZIP は `dist-sample-plugins/` です。
