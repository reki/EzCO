# 配布用サンプルプラグイン

ここにある `.zip` は完成したサンプルです。データフォルダ（設定の「データの置き場」）の `plugins/` にコピーして使います。置いたあとは EzCo を再起動してください。ON/OFF や読み込み方式の変更はプラグイン設定の OK / 適用で足り、再起動は不要です。

本体は中身を検査しません。置いたコードはアプリと同じ権限で動きます。注意の全文は [plugins/README.md](../plugins/README.md) です。

開発するときはリポジトリの `plugins/` にある展開フォルダを置きます。データ置き場を実行ファイルと同じフォルダにすると、そのフォルダがそのまま読み込まれます。ZIP の作り直しは配布するときだけで構いません。

| ファイル | 内容 |
| --- | --- |
| `example_png-1.0.0.zip` | `.png` をプラグイン経由で開く確認用。ルートは `LICENSE`（拡張子なし） |
| `example_zip-1.1.0.zip` | `.zip` をプラグイン経由で開く確認用。ルートは `LICENSE.txt` |
| `example_txt-1.0.0.zip` | `.txt` をページ画像として開く。ルートは `LICENSE.md` |
| `product_info-1.0.0.zip` | 商品情報サイドバー。LICENSE なし |
| `error_setup-1.0.0.zip` | `setup()` で例外を出す確認用。LICENSE 3種あり、表示は md |
| `error_callback-1.0.0.zip` | コールバック例外の確認用。txt と無印あり、表示は txt |
| `config_types-1.0.0.zip` | 設定種別の確認用。bool / string / int / float / int_range / float_range / path / password / color / date / datetime / choice / font |

ソースから ZIP を作り直すときは、タスク **「EzCo: プラグインZIP」** または `poetry run pack-plugins` です。1 件だけなら `poetry run pack-plugins example_txt` です。出力は `<フォルダ>-<version>.zip`。manifest が不正なものはログしてスキップし、最後に成功／失敗件数を出します。
