"""タブごとに、見えているあいだだけ次ページか指定ページで送る。

ホストは Class() のあと load(root, get_text, host) を渡す。
送りは run_action の next_page と goto_page だけを使う。
"""
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from turn import GOTO, NEXT, TurnBook

# 改ページ間隔の下限（秒）。
_INTERVAL_MIN = 1
# 改ページ間隔の上限（秒）。設定とサイドバーで揃える。
_INTERVAL_MAX = 86400
# ページ欄の上限。
_PAGE_MAX = 999999
# プラグイン設定の間隔キー。
_INTERVAL_KEY = "interval"


class AutoPagePlugin:
    """サイドバーからタブごとの自動改ページを始める。"""

    def __init__(self):
        """引数と、タブごとの状態の入れ物を空で作る。"""
        self.root = None
        self.get_text = None
        self.host = None
        self.widget = None
        self.book = TurnBook()
        self._timers = {}
        self._busy = set()
        self._rows = []
        self._shown_id = None
        self._filling = False
        self._listening = False
        self._panel = None
        self._start_label = None
        self._end_label = None
        self._interval_label = None
        self._start = None
        self._end = None
        self._interval = None
        self._from_button = None
        self._to_button = None
        self._run_button = None
        self._loop = None

    def load(self, root, get_text, host):
        """引数を保持し、間隔の初期値を登録する。

        Args:
            root: プラグインルート。このプラグインでは使わない。
            get_text: 文言取得関数。
            host: スコープ付きホスト。
        """
        self.root = root
        self.get_text = get_text
        self.host = host
        self.host.register_config(
            _INTERVAL_KEY,
            "int_range",
            default=_INTERVAL_MIN,
            label="{interval}",
            description="{interval_help}",
            minimum=_INTERVAL_MIN,
            maximum=_INTERVAL_MAX,
            step=1,
            suffix="{seconds}",
        )

    def setup(self):
        """サイドバーを作り、ページと設定の変化を受け取る。"""
        if self.widget is None:
            self._build()
        if not self._listening:
            self.host.on("current_changed", self._on_current)
            self.host.on("config_changed", self._on_config)
            self._listening = True
        self.host.register_sidebar("auto_page", "{title}", self.widget)
        self._apply_labels()
        self._refresh_form()

    def teardown(self):
        """タイマーを止め、サイドバーのウィジェットを捨てる。"""
        self._listening = False
        for tab_id in list(self._timers):
            self._disarm(tab_id)
        self.widget = None
        self._panel = None

    def language_changed(self):
        """サイドバーの文言を、いまの言語ファイルで置き換える。"""
        self._apply_labels()
        self._refresh_form()

    def _build(self):
        """開始、終了、間隔、ループの欄を作る。"""
        self.widget = QWidget()
        outer = QVBoxLayout(self.widget)
        self._panel = QWidget()
        form = QFormLayout(self._panel)
        self._start_label = QLabel()
        self._end_label = QLabel()
        self._interval_label = QLabel()
        self._start = self._page_spin()
        self._end = self._page_spin()
        self._interval = QSpinBox()
        self._interval.setRange(_INTERVAL_MIN, _INTERVAL_MAX)
        self._from_button = QPushButton()
        self._to_button = QPushButton()
        self._run_button = QPushButton()
        self._loop = QCheckBox()
        form.addRow(self._start_label, self._start)
        form.addRow(self._end_label, self._end)
        form.addRow(self._interval_label, self._interval)
        buttons = QHBoxLayout()
        buttons.addWidget(self._from_button)
        buttons.addWidget(self._to_button)
        outer.addWidget(self._panel)
        outer.addLayout(buttons)
        outer.addWidget(self._run_button)
        outer.addWidget(self._loop)
        outer.addStretch(1)
        self._start.valueChanged.connect(self._on_start_page)
        self._end.valueChanged.connect(self._on_end_page)
        self._interval.valueChanged.connect(self._on_interval)
        self._from_button.clicked.connect(self._on_from_current)
        self._to_button.clicked.connect(self._on_to_current)
        self._run_button.clicked.connect(self._on_run)
        self._loop.toggled.connect(self._on_loop)

    def _page_spin(self):
        """1 以上のページ番号欄を返す。

        Returns:
            ページ番号のスピンボックス。
        """
        spin = QSpinBox()
        spin.setRange(1, _PAGE_MAX)
        return spin

    def _apply_labels(self):
        """欄の名前を言語ファイルから入れる。"""
        if self.widget is None or self.get_text is None:
            return
        text = self.get_text
        self._start_label.setText(text("start_page"))
        self._end_label.setText(text("end_page"))
        self._interval_label.setText(text("interval"))
        self._interval.setSuffix(" " + text("seconds"))
        self._from_button.setText(text("from_current"))
        self._to_button.setText(text("to_current"))
        self._loop.setText(text("loop"))
        self._apply_run_button()

    def _apply_run_button(self):
        """開始中なら停止、止まっていれば開始と出す。"""
        if self._run_button is None or self.get_text is None:
            return
        state = self._shown_state()
        running = state is not None and state.running
        key = "stop" if running else "start"
        self._run_button.setText(self.get_text(key))

    def _default_interval(self):
        """設定の間隔を、1 秒以上で返す。

        Returns:
            間隔（秒）。
        """
        try:
            value = int(self.host.get_config(_INTERVAL_KEY, _INTERVAL_MIN))
        except (TypeError, ValueError):
            # 設定が整数でなければ、登録した初期値に戻す。
            value = _INTERVAL_MIN
        return min(_INTERVAL_MAX, max(_INTERVAL_MIN, value))

    def _on_current(self, _payload=None):
        """ページかタブが変わったら、送りの停止と欄を合わせる。

        Args:
            _payload: ショートカット対象の path、folder、page。欄は open_tabs を見る。
        """
        self._refresh_form()

    def _on_config(self, payload=None):
        """間隔の初期値が変わったら、欄を触っていないタブへ反映する。

        Args:
            payload: key と value。間隔以外は見ない。
        """
        if isinstance(payload, dict) and payload.get("key") not in (None, _INTERVAL_KEY):
            return
        self.book.apply_default_interval(self._default_interval())
        self._refresh_form()

    def _on_start_page(self, value):
        """表示中タブの開始ページを、欄の値にする。

        Args:
            value: 開始ページ。
        """
        if self._filling:
            return
        state = self._shown_state()
        if state is not None:
            state.start = int(value)

    def _on_end_page(self, value):
        """表示中タブの終了ページを、欄の値にする。

        Args:
            value: 終了ページ。
        """
        if self._filling:
            return
        state = self._shown_state()
        if state is not None:
            state.end = int(value)

    def _on_interval(self, value):
        """表示中タブの間隔を固定し、次の待ちからその秒数を使う。

        Args:
            value: 間隔（秒）。
        """
        if self._filling:
            return
        state = self._shown_state()
        if state is None:
            return
        state.interval = min(_INTERVAL_MAX, max(_INTERVAL_MIN, int(value)))
        state.interval_custom = True

    def _on_loop(self, checked):
        """表示中タブのループを切り替える。

        Args:
            checked: オンのとき True。
        """
        if self._filling:
            return
        state = self._shown_state()
        if state is not None:
            state.loop = bool(checked)

    def _on_from_current(self):
        """開始ページを、ショートカット対象のいまのページにする。"""
        self._reconcile()
        state = self._shown_state()
        row = self._current_row()
        if state is None or row is None:
            return
        state.start = int(row.get("page") or 1)
        self._refresh_form()

    def _on_to_current(self):
        """終了ページを、ショートカット対象のいまのページにする。"""
        self._reconcile()
        state = self._shown_state()
        row = self._current_row()
        if state is None or row is None:
            return
        state.end = int(row.get("page") or 1)
        self._refresh_form()

    def _on_run(self):
        """表示中タブの自動送りを始める。動作中なら止める。"""
        self._reconcile()
        state = self._shown_state()
        row = self._current_row()
        if state is None or row is None:
            return
        tab_id = row["id"]
        if state.running:
            state.running = False
            state.hold = False
            self._disarm(tab_id)
            self._refresh_form()
            return
        action = self.book.begin(tab_id, row.get("page") or 1, bool(row.get("shown")))
        if action[0] == GOTO:
            self._perform(tab_id, action)
        if tab_id in self.book.tabs and self.book.tabs[tab_id].running:
            self._arm(tab_id)
        self._refresh_form()

    def _on_tick(self, tab_id):
        """1タブ分の次の手を実行し、動作中なら次の間隔を予約する。

        Args:
            tab_id: タブ id。
        """
        if self.widget is None:
            return
        self._reconcile()
        state = self.book.tabs.get(tab_id)
        if state is None or not state.running:
            self._refresh_form()
            return
        row = self._row(tab_id)
        if row is None:
            self._refresh_form()
            return
        action = self.book.step(tab_id, bool(row.get("shown")))
        if action[0] in (NEXT, GOTO):
            self._perform(tab_id, action)
        state = self.book.tabs.get(tab_id)
        if state is not None and state.running:
            self._arm(tab_id)
        else:
            self._disarm(tab_id)
        self._refresh_form()

    def _reconcile(self):
        """開いているタブに状態を合わせ、閉じたタブと手動のページ変更を片付ける。"""
        rows = list(self.host.open_tabs() or [])
        self._rows = rows
        live = {row.get("id") for row in rows}
        for tab_id in self.book.drop_closed(live):
            self._disarm(tab_id)
        interval = self._default_interval()
        for row in rows:
            tab_id = row.get("id")
            if not tab_id:
                continue
            document = row.get("document")
            if document is None:
                document = row.get("path") or ""
            page = int(row.get("page") or 1)
            total = int(row.get("total") or 0)
            self.book.touch(tab_id, page, total, document, interval)
            if self.book.note_document(tab_id, document, total, page):
                self._disarm(tab_id)
                continue
            if tab_id in self._busy:
                self.book.adopt(tab_id, page)
                continue
            if self.book.observe_manual(tab_id, page):
                self._disarm(tab_id)

    def _current_row(self):
        """ショートカット対象のタブ情報を返す。

        Returns:
            対象の辞書。無ければ None。
        """
        for row in self._rows:
            if row.get("current"):
                return row
        return None

    def _row(self, tab_id):
        """id のタブ情報を返す。

        Args:
            tab_id: タブ id。

        Returns:
            その辞書。無ければ None。
        """
        for row in self._rows:
            if row.get("id") == tab_id:
                return row
        return None

    def _perform(self, tab_id, action):
        """次ページか指定ページのアクションを、そのタブへ出す。

        Args:
            tab_id: タブ id。
            action: ("next", None) または ("goto", ページ)。
        """
        kind, target = action
        self._busy.add(tab_id)
        try:
            if kind == NEXT:
                self.host.run_action("next_page", tab=tab_id)
            elif kind == GOTO:
                self.host.run_action("goto_page", page=int(target), tab=tab_id)
        except Exception:
            # 送れなくても印は残さず、直後に実測のページへ合わせる。
            pass
        finally:
            self._busy.discard(tab_id)
            self._adopt(tab_id)

    def _adopt(self, tab_id):
        """送りのあと、そのタブのページを実測に合わせる。閉じていれば状態を捨てる。

        Args:
            tab_id: タブ id。
        """
        rows = list(self.host.open_tabs() or [])
        self._rows = rows
        for row in rows:
            if row.get("id") == tab_id:
                self.book.adopt(tab_id, row.get("page") or 1)
                return
        for closed in self.book.drop_closed({row.get("id") for row in rows}):
            self._disarm(closed)

    def _arm(self, tab_id):
        """そのタブの次の間隔を、いまの秒数で予約する。

        Args:
            tab_id: タブ id。
        """
        state = self.book.tabs.get(tab_id)
        if state is None or not state.running or self.widget is None:
            return
        timer = self._timers.get(tab_id)
        if timer is None:
            timer = QTimer(self.widget)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda tab_id=tab_id: self._on_tick(tab_id))
            self._timers[tab_id] = timer
        timer.start(state.interval * 1000)

    def _disarm(self, tab_id):
        """そのタブのタイマーを止めて捨てる。

        Args:
            tab_id: タブ id。
        """
        timer = self._timers.pop(tab_id, None)
        if timer is not None:
            timer.stop()

    def _set_controls(self, enabled):
        """欄とボタンを、タブがあるときだけ触れるようにする。

        Args:
            enabled: 触れるとき True。
        """
        self._panel.setEnabled(enabled)
        self._from_button.setEnabled(enabled)
        self._to_button.setEnabled(enabled)
        self._run_button.setEnabled(enabled)
        self._loop.setEnabled(enabled)

    def _refresh_form(self):
        """ショートカット対象の値と、開始か停止を欄へ出す。"""
        if self.widget is None:
            return
        self._reconcile()
        row = self._current_row()
        self._filling = True
        try:
            if row is None:
                self._shown_id = None
                self._set_controls(False)
                self._apply_run_button()
                return
            self._set_controls(True)
            self._shown_id = row.get("id")
            state = self._shown_state()
            if state is None:
                return
            self._start.setValue(int(state.start))
            self._end.setValue(int(state.end))
            self._interval.setValue(int(state.interval))
            self._loop.setChecked(bool(state.loop))
            self._apply_run_button()
        finally:
            self._filling = False

    def _shown_state(self):
        """欄に出しているタブの状態を返す。

        Returns:
            タブの状態。欄が空なら None。
        """
        if self._shown_id is None:
            return None
        return self.book.tabs.get(self._shown_id)
