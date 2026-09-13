# Example PNG Loader

確認用の画像プラグインです。`.png` をプラグイン経由で開き、色と「プラグイン読み込み表示」ラベルを重ねます。本番向けではありません。

| 項目 | 値 |
| --- | --- |
| ID | `com.ezco.example.png` |
| バージョン | `1.0.0` |
| 種別 | ファイル（画像） |
| ZIP | `dist-sample-plugins/example_png.zip` |
| 入口 | `loader:FileLoader` |

## 使い方

1. `example_png.zip` を実行ファイル旁の `plugins/` 直下に置く
2. EzCo を起動（追加したあとは再起動）
3. プラグイン設定でこのプラグインを有効にする
4. `.png` の読み込み方式をこのプラグインにする（既定はビルドイン）

重ね表示が出れば、プラグインが読んだことが分かります。確認が終わったら読み込み方式をビルドインに戻すか、プラグインを無効にしてください。

設定項目と独自アクションはありません。

## 開発

ソースは `plugins/example_png/` です。データフォルダの `plugins/` にこのフォルダを置けばそのまま読めます。配布 ZIP は `dist-sample-plugins/` です。

```python
from pathlib import Path
import zipfile

src = Path("plugins/example_png")
dst = Path("dist-sample-plugins/example_png.zip")
with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zf:
    for path in sorted(src.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            zf.write(path, path.relative_to(src).as_posix())
```

ホスト API の一覧はユーザーマニュアルの [プラグインリファレンス](../../resources/UserManual/files/plugin-reference.html) と [docs/plugins.md](../../docs/plugins.md) を見てください。
