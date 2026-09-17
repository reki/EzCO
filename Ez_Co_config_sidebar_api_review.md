# Ez_Co Config Sidebar API 実装レビュー

対象: `config_sidebar_api_c983bddd.plan.md`

## 総評

方針は良い。

既存のConfig schemaを、

```text
設定ダイアログ
+
Host生成サイドバー
```

の両方で再利用することで、Plugin側が同じ設定UIを手組みする必要がなくなる。

特に以下は採用・維持推奨。

- Config widget生成処理を `config_widgets.py` へ共通化
- サイドバー生成は自動ではなくPluginが `setup()` で明示要求
- Config schemaが0件なら空UIを作らない
- サイドバーはOK/Cancelなしのため常時保存
- 数値だけdebounce
- `sync` は設定ダイアログ専用の意味を維持
- `reload` はサイドバーでも利用
- `config_changed` で他経路の変更をフォームへ反映
- example_txtの自前設定UIをHost生成フォームへ置換
- PluginはEz_Co内部Widget実装をimportしない

ただし、実装済みコードについて以下の挙動は確認推奨。

---

# 1. 【重要】Resetと `required=True + empty default` の整合

現在のConfig仕様では、

```text
required=True
default=""
```

や、

```text
required=True
multiple=True
default=[]
```

をschemaとして許可している。

一方、今回のPlanではResetを、

```text
schema defaultへ戻す
↓
すぐ set_config()
```

としている。

しかし `set_config()` は `required=True` のempty値を拒否するため、

```text
default=""
required=True
```

ではResetできない。

## 推奨

Resetを、

```text
default値を set_config()
```

ではなく、

```text
保存済みoverrideを削除
→ 未保存状態へ戻す
→ get_config()はschema defaultを返す
```

という意味にする。

つまりConfig storageに、

```python
reset_config(key)
```

あるいは同等の内部処理を持たせる。

これなら、

```text
required=True
default=""
```

でも「未設定状態へ戻す」が成立する。

`required` は「emptyを保存してよいか」であり、
schema defaultそのものを禁止する制約ではないため、
この方が既存仕様と整合する。

---

# 2. Reset時の `reload=True` はまとめて1回

フォーム全体をResetすると複数keyが変更される可能性がある。

各fieldごとに、

```text
reset
→ reload_current()
```

すると、

- reloadが何度も走る
- 中間状態でsourceが開き直される
- 重い
- Plugin callbackが何度も走る

可能性がある。

## 推奨

```text
全keyをreset
↓
config_changedを通常どおり通知
↓
変更されたfieldのどれかに reload=True があれば
↓
最後に reload_current() を1回
```

とする。

通常の単一field変更は現在Planどおり即reloadでよい。

---

# 3. `reload=True` は保存成功・実変更後だけ

サイドバーでは、

```text
set_config
↓
reload_current
```

となるが、

- required違反で保存拒否
- coerce後に値が同じ
- set_configがFalseを返す

場合までreloadしないこと。

概念:

```python
changed = host.set_config(key, value)

if changed and field.reload:
    host.reload_current()
```

既存 `set_config()` のFalseの意味が「失敗のみ」なのか
「変更なしもFalse」なのかは現在実装へ合わせる。

重要なのは、保存されていない値でreloadしないこと。

---

# 4. 外部 `config_changed` をWidgetへ戻すときはsignalを止める

Planでは、

```text
config_changed
→ Sidebar Widgetへ反映
```

する。

このとき、

```text
widget.setValue(...)
↓
valueChanged
↓
set_config()
↓
config_changed
```

というループを作らないようにする。

self-origin guardだけに依存せず、
Widget値を外部から更新する区間では、

```python
QSignalBlocker(widget)
```

または共通Widget adapter側のsignal suppressionを使うのが安全。

特に、

- QSpinBox
- QDoubleSpinBox
- QComboBox
- QListWidget
- checkbox

などはprogrammatic updateでもsignalが出るため確認する。

---

# 5. debounce Timerのlifecycle

数値fieldの500ms debounceは、
`PluginConfigForm` または対象Widgetをparentにする。

Sidebar unload / Plugin disable時に、

```text
Timer callback
→ unload済みScopedHostへ set_config
```

が飛ばないようにする。

Qt parent ownershipで破棄される設計ならそれでよい。

必要ならdestroy/unmount時にpending timerをstopする。

---

# 6. 設定ダイアログとの同時編集

Planでは、

```text
Sidebar
← config_changed
← 設定ダイアログ
```

の反映は明記されている。

逆方向については、設定ダイアログがmodalなら実用上ほぼ問題ない。

もしnon-modalでSidebarを触れるなら、

```text
Sidebarで変更
↓
Dialog側は古い値
↓
Dialog Apply / Cancel
↓
Sidebar変更を上書き
```

が起こり得る。

## 推奨

- Config dialogがmodalなら追加対応不要
- non-modalならDialog側もexternal `config_changed` の扱いを決める

過剰実装は不要。現在UIがmodalならテストだけで十分。

---

# 7. API名 `required_setting_sidebar()` は再検討余地あり

機能上の問題ではないが、

```python
required_setting_sidebar()
```

という名前は、

```text
required=True の設定だけを表示するSidebar
```

のようにも読める。

実際には、

```text
登録済みConfig schemaからWidget/Formを生成する
```

API。

公開前なら例えば、

```python
create_config_form()
config_form_widget()
build_config_form()
```

などの方が意味が直接的。

一方、

```python
register_config_sidebar(...)
```

は現名称で分かりやすい。

すでに命名方針があるなら変更必須ではない。

---

# 最終評価

この機能自体はEz_CoのConfig設計と非常に相性が良い。

今までPlugin側が、

```text
Config schema
+
独自設定Widget
+
Configとの同期処理
```

を二重に持っていた部分を、

```text
Config schema
↓
Host-generated Form
```

にできる。

Plugin作者は、

```python
load():
    register_config_json(...)

setup():
    register_config_sidebar(...)
```

だけで標準設定UIを持てる。

特に確認すべきなのは以下の3点。

1. `required=True + empty default` のReset
2. Reset時のreloadを1回へまとめる
3. external `config_changed` 反映時のsignal loop防止

この3点が問題なければ、設計としてかなり完成度が高い。
