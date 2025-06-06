# 第三者ライセンス

EzCo 本体は [MIT License](LICENSE) です。以下は `pyproject.toml` の依存と、実行時に引き込まれる主なパッケージのライセンスです。法律上の助言ではありません。配布前は各公式ライセンス文を確認してください。

**結論（2026-09 時点）:** 実行時依存に **GPL / AGPL 単独** はありません。コピーレフト系はすべて **LGPL**（または Qt の LGPL / GPL デュアルで、PyPI 版は LGPL を選択可能）です。LGPL は一般に、自前アプリのソース公開を求めません。変更した LGPL ライブラリ自体のソース提供と、利用者がそのライブラリを差し替えられること（動的リンク等）が条件になります。

開発専用の `pylint` だけが **GPL-2.0-or-later** です。リンターとして使うだけでアプリに同梱しなければ、本体が GPL にはなりません。

---

## 実行時（アプリに同梱し得るもの）

| パッケージ | ライセンス | ソース公開義務（本体） |
| --- | --- | --- |
| PySide6 / PySide6-Essentials / PySide6-Addons / shiboken6 | LGPL-3.0 **または** GPL-2.0 / GPL-3.0 | なし（LGPL として使う場合） |
| py7zr | LGPL-2.1-or-later | なし |
| inflate64 / pybcj / pyppmd / multivolumefile（py7zr 依存） | LGPL-2.1-or-later | なし |
| pynput | LGPLv3 | なし |
| pystray | LGPLv3 | なし |
| pytray | LGPLv3+ | なし |
| pillow | MIT-CMU | なし |
| click | BSD-3-Clause | なし |
| numpy | BSD | なし |
| torch | BSD-3-Clause | なし |
| setuptools | MIT | なし |
| tomli | MIT | なし |
| PyYAML | MIT | なし |
| humanfriendly | MIT | なし |
| pypdf | BSD-3-Clause | なし |
| pyzipper | MIT | なし |
| pycryptodomex（pyzipper / py7zr 依存） | BSD / Public Domain | なし |
| rarfile | ISC | なし |

### PySide6（Qt）

デュアルライセンスです。PyPI の PySide6 は **LGPL-3.0 で利用**できます。GPL を選ぶ必要はありません。

LGPL 利用時の典型的な注意:

- EzCo のソースを公開する義務はない
- Qt / PySide6 を改変したら、その改変分は LGPL で出す
- バイナリ配布時は LGPL 条文の添付と、利用者が LGPL ライブラリを差し替えられる手段（動的リンク、または再リンク用オブジェクト等）が求められることがある
- Nuitka の onefile は静的に近い束ね方になるため、**公開配布する段階**では Qt の LGPL 遵守方法を別途確認すること

### py7zr 一式・pynput・pystray・pytray

いずれも LGPL。リンクして使う分には本体の公開義務はない。ライブラリを改変して配布する場合だけ、その改変ソースが対象になる。

### rarfile と UnRAR

`rarfile` 自体は ISC。RAR の展開には別途 UnRAR（RARLAB）が必要な場合がある。UnRAR は GPL ではないが、独自の利用条件がある。本体の MIT / 公開義務とは別件。

---

## 開発専用（アプリに入れない）

| パッケージ | ライセンス | 備考 |
| --- | --- | --- |
| pylint | GPL-2.0-or-later | 開発時の静的解析のみ。配布物に含めない |
| astroid | LGPL-2.1-or-later | pylint 依存 |
| pytest / pytest-qt | MIT | テスト |
| Nuitka | Apache-2.0 | ビルドツール。成果物をオープンソースにする義務はない |
| py-spy | MIT | プロファイラ |

`pylint` を実行ファイルに同梱したり、GPL コードを本体にコピーしたりすると、本体側にも GPL が及ぶ可能性がある。開発依存のまま使うこと。

---

## 確認していない／対象外

- プラグイン作者が自分の ZIP に入れた第三者コード
- Windows システムフォントや OS コンポーネント
- ユーザーが開く漫画・画像ファイル

---

## ライセンス条文の入手先

各パッケージの PyPI / リポジトリ、およびインストール済みメタデータ（`License` / `Classifier`）を一次情報とした。Qt は [Qt Licensing](https://www.qt.io/licensing/)、LGPL 条文は GNU 公式を参照。
