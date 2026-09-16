# Agents

このファイルはルールの複製ではありません。詳細は [`.cursor/rules/`](.cursor/rules/) が正です。全体構造は [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)、なぜそうしたかは [docs/DECISIONS.md](docs/DECISIONS.md) です。

## 読むもの

- `.cursor/rules/tests.mdc`
- `.cursor/rules/plugins.mdc`
- `.cursor/rules/plugin-data.mdc`
- `.cursor/rules/ui-strings.mdc`
- `.cursor/rules/user-manual.mdc`
- `.cursor/rules/workflow.mdc`
- リリースノートを書くとき: `.cursor/rules/release-notes.mdc`

## 守ること

- 既存設計を見てから変える。頼まれていない大規模リファクタはしない
- 同じ役割の提供物は横並びで名前と置き場を揃える
- コミットと push は指示があるまでしない
- GUI 操作と `QWidget` の変更は GUI スレッド。worker から触らない
- `FileHandler` を変えるときは cache / prefetch / session を一緒に見る
- プラグインはコールバック側。`import ez_co` しない。本体 Config を上書きしない
- プラグインから `host` は直接アクセス。`getattr` / `hasattr` で探さない
- プラグインの入口は `src/plugin.py`
- 権限は `manifest.permissions`。形式は `formats`、サイドバーは `sidebar`
- テストは 1ソース n ファイル。本番の `%APPDATA%` とリポジトリの `config.db` は触らない
- クラッシュは推測で直さない。先に呼び出しとスレッドが残る調査ログ
- manifest / host API を変えたら `docs/plugins.md` とユーザーマニュアル（日英）を直す
- UI 文言は `langs` の ja / en。画面に `%APPDATA%` を出さない
- リリースノートは `.cursor/rules/release-notes.mdc`。`RELEASE_NOTES_<version>.md` を出す。タグは指示があるまで作らない
