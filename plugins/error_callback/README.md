# Error Callback Probe

確認用です。サイドバーの「エラー」ボタンを押すとコールバックで例外を出します。本番では使いません。

| 項目 | 値 |
| --- | --- |
| ID | `com.ezco.error_callback` |
| バージョン | `1.0.0` |
| 種別 | サイドバー |
| ZIP | `dist-sample-plugins/error_callback-1.0.0.zip` |
| 入口 | `plugin:ErrorCallbackPlugin` |
| LICENSE | `LICENSE.txt` と `LICENSE` を同梱（md なし）。表示は `LICENSE.txt` になること |

## 使い方

1. `error_callback.zip` を実行ファイル旁の `plugins/` 直下に置く
2. EzCo を起動（追加したあとは再起動）
3. プラグイン設定でこのプラグインを有効にする
4. 「エラー検証」サイドバーを開き、「エラー」を押す
5. アプリは終了しない。開発タブの「エラー時にエラーログを表示する」が ON ならスタックトレースダイアログが出る

ショートカットに「エラー」アクションを割り当てても同じ例外になります。確認が終わったらプラグインを無効にしてください。

## 開発

ソースは `plugins/error_callback/` です。データフォルダの `plugins/` にこのフォルダを置けばそのまま読めます。配布 ZIP は `dist-sample-plugins/` です。
