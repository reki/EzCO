"""プラグイン設定フィールドの入力ウィジェット。ダイアログとサイドバーで共有する。"""
from PySide6.QtCore import QDate, QDateTime, Qt, QTime, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QCompleter,
    QDateEdit,
    QDateTimeEdit,
    QDoubleSpinBox,
    QFileDialog,
    QFontComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ez_co.plugins.host import coerce_config_value, config_choice_key
from ez_co.utils.language_manager import get_text

# 数値の即時保存を、入力が止まってから待つミリ秒。
SYNC_RELOAD_IDLE_MS = 500
# ドロップダウンで選ぶ設定型。
DROPDOWN_TYPES = ("choice", "charset", "language", "country")
# 数値として扱う設定型。
NUMERIC_TYPES = ("int", "float", "int_range", "float_range")


def make_value_widget(field, current, expand=None, parent=None):
    """項目の型に合わせた入力を作る。複数選択はリスト、複数値は行、それ以外は単一入力。

    Args:
        field: 作る項目。
        current: 初期値。
        expand: 表示文を展開する処理。
        parent: 親ウィジェット。

    Returns:
        作った入力。
    """
    if field.multiple and field.value_type in DROPDOWN_TYPES and field.choices:
        return ChoiceMultiList(field, current, parent=parent, expand=expand)
    if field.multiple:
        return MultiRows(field, current, parent=parent, expand=expand)
    return make_single_widget(field, current, expand=expand, parent=parent)


def make_single_widget(field, current, expand=None, parent=None):
    """型に応じた入力を1つ作る。

    Args:
        field: 作る項目。
        current: 初期値。
        expand: 表示文を展開する処理。
        parent: 親ウィジェット。

    Returns:
        作った入力。数値で接尾辞があれば接尾辞付き。
    """
    kind = field.value_type
    if kind == "bool":
        widget = QCheckBox(parent)
        widget.setChecked(bool(current))
        return widget
    if kind == "int":
        widget = QSpinBox(parent)
        widget.setRange(-2147483647, 2147483647)
        try:
            widget.setValue(int(current))
        except (TypeError, ValueError):
            # 整数にできない初期値は 0 に戻す。
            widget.setValue(0)
        return with_suffix(widget, field, expand=expand)
    if kind == "float":
        widget = QDoubleSpinBox(parent)
        widget.setRange(-1e12, 1e12)
        widget.setDecimals(4)
        try:
            widget.setValue(float(current))
        except (TypeError, ValueError):
            # 小数にできない初期値は 0 に戻す。
            widget.setValue(0.0)
        return with_suffix(widget, field, expand=expand)
    if kind in ("int_range", "float_range"):
        return with_suffix(RangeRow(field, current, parent), field, expand=expand)
    if kind == "path":
        return PathRow(field, current, parent=parent, expand=expand)
    if kind == "password":
        widget = QLineEdit(parent)
        widget.setEchoMode(QLineEdit.EchoMode.Password)
        widget.setText("" if current is None else str(current))
        return widget
    if kind == "color":
        color = coerce_config_value("color", current, field.default)
        button = QPushButton(parent)
        paint_color_button(button, color)
        button.clicked.connect(lambda _=False, widget=button: pick_color(widget))
        return button
    if kind == "date":
        widget = QDateEdit(parent)
        widget.setCalendarPopup(True)
        widget.setDisplayFormat("yyyy-MM-dd")
        widget.setDate(qdate_from_seconds(current))
        return widget
    if kind == "datetime":
        widget = QDateTimeEdit(parent)
        widget.setCalendarPopup(True)
        widget.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        widget.setDateTime(qdatetime_from_seconds(current))
        return widget
    if kind in DROPDOWN_TYPES and field.choices:
        return FilterCombo(field.choices, current, parent=parent, expand=expand)
    if kind == "font":
        widget = QFontComboBox(parent)
        family = "" if current is None else str(current)
        if family:
            widget.setCurrentFont(QFont(family))
        return widget
    widget = QLineEdit(parent)
    widget.setText("" if current is None else str(current))
    return widget


def read_value(field, widget):
    """ウィジェットから保存する値を読む。

    Args:
        field: 読む項目。
        widget: 読む入力。

    Returns:
        複数行と複数選択はそれぞれの値。それ以外は単一入力の値。
    """
    if isinstance(widget, MultiRows):
        return widget.values()
    if isinstance(widget, ChoiceMultiList):
        return widget.values()
    return read_single(field, widget)


def read_single(field, widget):
    """単一入力から値を読む。接尾辞付きなら中の入力を見る。

    Args:
        field: 読む項目。
        widget: 読む入力。

    Returns:
        読んだ値。色が空なら既定。選択が空なら表示文か先頭の選択肢。
    """
    editor = widget.editor if isinstance(widget, SuffixRow) else widget
    kind = field.value_type
    if kind == "bool":
        return editor.isChecked()
    if kind in ("int", "float", "int_range", "float_range"):
        return editor.value()
    if kind == "path":
        return editor.text()
    if kind == "password":
        return editor.text()
    if kind == "color":
        return editor.property("color_value") or field.default
    if kind == "date":
        return seconds_from_qdate(editor.date())
    if kind == "datetime":
        return seconds_from_qdatetime(editor.dateTime())
    if kind in DROPDOWN_TYPES and field.choices:
        data = editor.currentData()
        if data is None:
            text = editor.currentText()
            for value, label in field.choices:
                if text in (value, label):
                    return value
            return field.choices[0][0]
        return data
    if kind == "font":
        return editor.currentFont().family()
    return editor.text()


def set_widget_value(field, widget, value):
    """ウィジェットへ値を入れる。

    Args:
        field: 入れる項目。
        widget: 入れる入力。
        value: 入れる値。
    """
    if isinstance(widget, MultiRows):
        widget.set_values(value)
        return
    if isinstance(widget, ChoiceMultiList):
        widget.set_values(value)
        return
    editor = widget.editor if isinstance(widget, SuffixRow) else widget
    kind = field.value_type
    if kind == "bool":
        editor.blockSignals(True)
        editor.setChecked(bool(value))
        editor.blockSignals(False)
        return
    if kind in ("int", "float"):
        editor.blockSignals(True)
        editor.setValue(value)
        editor.blockSignals(False)
        return
    if kind in ("int_range", "float_range"):
        editor.setValue(value)
        return
    if kind == "path":
        editor.setText("" if value is None else str(value))
        return
    if kind == "password":
        editor.blockSignals(True)
        editor.setText("" if value is None else str(value))
        editor.blockSignals(False)
        return
    if kind == "color":
        paint_color_button(editor, coerce_config_value("color", value, field.default))
        return
    if kind == "date":
        editor.blockSignals(True)
        editor.setDate(qdate_from_seconds(value))
        editor.blockSignals(False)
        return
    if kind == "datetime":
        editor.blockSignals(True)
        editor.setDateTime(qdatetime_from_seconds(value))
        editor.blockSignals(False)
        return
    if kind in DROPDOWN_TYPES and field.choices:
        editor.blockSignals(True)
        index = editor.findData(config_choice_key(value))
        editor.setCurrentIndex(max(0, index))
        editor.blockSignals(False)
        return
    if kind == "font":
        editor.blockSignals(True)
        family = "" if value is None else str(value)
        if family:
            editor.setCurrentFont(QFont(family))
        editor.blockSignals(False)
        return
    editor.blockSignals(True)
    editor.setText("" if value is None else str(value))
    editor.blockSignals(False)


def blank_value(field):
    """空の行に入れる初期値を返す。

    Args:
        field: 項目。

    Returns:
        真偽は False。整数と実数は最小、無ければ 0。色は既定。日付は 0。それ以外は空文字。
    """
    kind = field.value_type
    if kind == "bool":
        return False
    if kind in ("int", "int_range"):
        if field.minimum is not None:
            return field.minimum
        return 0
    if kind in ("float", "float_range"):
        if field.minimum is not None:
            return field.minimum
        return 0.0
    if kind == "color":
        return coerce_config_value("color", None, field.default)
    if kind in ("date", "datetime"):
        return 0
    if kind == "font":
        return ""
    return ""


def connect_value_changed(widget, callback):
    """値が変わったときに処理をつなぐ。

    Args:
        widget: つなぐ入力。
        callback: 変化時に呼ぶ処理。
    """
    if isinstance(widget, MultiRows):
        widget.valueChanged.connect(lambda _=None: callback())
        return
    if isinstance(widget, ChoiceMultiList):
        widget.changed.connect(callback)
        return
    if isinstance(widget, SuffixRow):
        connect_value_changed(widget.editor, callback)
        return
    if isinstance(widget, PathRow):
        widget.valueChanged.connect(lambda _=None: callback())
        return
    if isinstance(widget, RangeRow):
        widget.valueChanged.connect(lambda _=None: callback())
        return
    if isinstance(widget, QLineEdit):
        widget.editingFinished.connect(callback)
        return
    if isinstance(widget, (QComboBox, FilterCombo)):
        widget.currentIndexChanged.connect(lambda _=None: callback())
        return
    if isinstance(widget, (QSpinBox, QDoubleSpinBox, QDateEdit, QDateTimeEdit)):
        widget.valueChanged.connect(lambda _=None: callback())
        return
    if isinstance(widget, QFontComboBox):
        widget.currentFontChanged.connect(lambda _=None: callback())
        return
    if isinstance(widget, QCheckBox):
        widget.toggled.connect(lambda _=None: callback())
        return
    if isinstance(widget, QPushButton):
        widget.clicked.connect(lambda _=None: callback())


def config_field_display_name(field, expand=None) -> str:
    """設定の項目名。range は末尾に範囲、float_range は step も付ける。

    Args:
        field: 項目。
        expand: ラベルを展開する処理。無ければそのまま。

    Returns:
        表示名。複数選択のドロップダウンにはその旨を足す。
    """
    raw = str(field.label or field.key or "")
    name = expand(raw) if expand is not None else raw
    kind = field.value_type
    if kind in ("int_range", "float_range"):
        if field.minimum is not None and field.maximum is not None:
            as_int = kind == "int_range"
            step = field.step
            lo = _format_range_number(field.minimum, as_int, step)
            hi = _format_range_number(field.maximum, as_int, step)
            if as_int:
                name = get_text("ui.plugin_config_int_range_name", name=name, minimum=lo, maximum=hi)
            else:
                st = _format_range_number(step if step is not None else 0.01, False, step)
                name = get_text(
                    "ui.plugin_config_float_range_name",
                    name=name,
                    minimum=lo,
                    maximum=hi,
                    step=st,
                )
    if field.multiple and kind in DROPDOWN_TYPES:
        return name + get_text("ui.plugin_config_multiple")
    return name


def with_suffix(widget, field, expand=None):
    """数値型で接尾辞があれば接尾辞付きの行で包む。

    Args:
        widget: 包む入力。
        field: 接尾辞を持つ項目。
        expand: 接尾辞を展開する処理。

    Returns:
        包んだ行。接尾辞が無い、または数値型でなければ元の入力。
    """
    suffix = field.suffix
    if expand is not None:
        suffix = expand(suffix)
    if not suffix or field.value_type not in NUMERIC_TYPES:
        return widget
    return SuffixRow(widget, suffix)


def pick_color(button: QPushButton):
    """色ダイアログで選ばれた色をボタンに塗る。無効な色なら変えない。

    Args:
        button: 塗るボタン。
    """
    current = button.property("color_value") or "#000000"
    color = QColorDialog.getColor(QColor(str(current)), button)
    if color.isValid():
        paint_color_button(button, color.name())


def paint_color_button(button: QPushButton, color: str):
    """ボタンに色と、明るさに合わせた文字色を塗る。

    Args:
        button: 塗るボタン。
        color: 塗る色。
    """
    button.setProperty("color_value", color)
    button.setText(color)
    value = (color or "").lstrip("#")
    light = True
    if len(value) == 6:
        try:
            red = int(value[0:2], 16)
            green = int(value[2:4], 16)
            blue = int(value[4:6], 16)
            light = (red * 299 + green * 587 + blue * 114) >= 140000
        except ValueError:
            # 色コードを読めないときは明るい文字色の判定に戻す。
            light = True
    fg = "#111111" if light else "#f5f5f5"
    button.setStyleSheet(
        f"background-color: {color}; color: {fg}; min-width: 72px; min-height: 22px;"
    )


def qdate_from_seconds(value) -> QDate:
    """秒を UTC の日付にする。

    Args:
        value: 秒。整数にできないときは 0。

    Returns:
        その日付。
    """
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        # 秒にできない値は起点の 0 に戻す。
        seconds = 0
    return QDateTime.fromSecsSinceEpoch(seconds, Qt.TimeSpec.UTC).date()


def qdatetime_from_seconds(value) -> QDateTime:
    """秒をローカルの日時にする。

    Args:
        value: 秒。整数にできないときは 0。

    Returns:
        その日時。
    """
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        # 秒にできない値は起点の 0 に戻す。
        seconds = 0
    return QDateTime.fromSecsSinceEpoch(seconds, Qt.TimeSpec.UTC).toLocalTime()


def seconds_from_qdate(value: QDate) -> int:
    """日付の UTC 0時を秒にする。

    Args:
        value: 日付。

    Returns:
        秒。
    """
    return int(QDateTime(value, QTime(0, 0, 0), Qt.TimeSpec.UTC).toSecsSinceEpoch())


def seconds_from_qdatetime(value: QDateTime) -> int:
    """日時を UTC の秒にする。

    Args:
        value: 日時。

    Returns:
        秒。
    """
    return int(value.toUTC().toSecsSinceEpoch())


def _format_range_number(value, as_int: bool, step) -> str:
    """範囲表示用の数文字列にする。

    Args:
        value: 表示する数。
        as_int: 整数として出すとき True。
        step: 実数の桁に使う刻み。

    Returns:
        表示用の文字列。実数は末尾の 0 を落とす。
    """
    if as_int:
        return str(int(value))
    decimals = _decimals_from_step(step if step is not None else 0.01)
    text = f"{float(value):.{decimals}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _decimals_from_step(step) -> int:
    """刻みの小数桁を返す。

    Args:
        step: 刻み。

    Returns:
        小数桁。最大 6。小数が無ければ 2。
    """
    text = f"{float(step):.10f}".rstrip("0").rstrip(".")
    if "." in text:
        return min(6, max(1, len(text.split(".", 1)[1])))
    return 2


class SuffixRow(QWidget):
    """数値入力の右に接尾辞を出す。"""
    valueChanged = Signal(object)

    def __init__(self, editor, suffix: str, parent=None):
        """入力の右に接尾辞を置く。

        Args:
            editor: 数値入力。
            suffix: 接尾辞。
            parent: 親ウィジェット。
        """
        super().__init__(parent)
        self.editor = editor
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(editor, 1)
        self._suffix_label = QLabel(suffix)
        layout.addWidget(self._suffix_label, 0)
        if hasattr(editor, "valueChanged"):
            editor.valueChanged.connect(self.valueChanged.emit)

    def set_suffix(self, suffix: str):
        """接尾辞の文字を差し替える。

        Args:
            suffix: 新しい接尾辞。
        """
        self._suffix_label.setText(suffix)


class FilterCombo(QComboBox):
    """部分一致で絞れる選択コンボ。"""

    def __init__(self, choices, current, parent=None, expand=None):
        """選択肢を入れ、部分一致の補完を付ける。

        Args:
            choices: 値と表示の組。
            current: 初期選択。
            parent: 親ウィジェット。
            expand: 表示を展開する処理。
        """
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        for value, label in choices:
            text = expand(label) if expand is not None else label
            self.addItem(text, value)
        completer = self.completer()
        if completer is None:
            completer = QCompleter(self)
            self.setCompleter(completer)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        index = self.findData(config_choice_key(current))
        self.setCurrentIndex(max(0, index))


class ChoiceMultiList(QWidget):
    """絞り込み付きの複数選択リスト。"""
    changed = Signal()

    def __init__(self, field, current, parent=None, expand=None):
        """絞り込み欄と複数選択リストを置く。

        Args:
            field: 選択肢を持つ項目。
            current: 初期の選択。
            parent: 親ウィジェット。
            expand: 表示を展開する処理。
        """
        super().__init__(parent)
        self._choices = list(field.choices)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self._filter = QLineEdit()
        layout.addWidget(self._filter)
        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        for value, label in self._choices:
            text = expand(label) if expand is not None else label
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, value)
            self._list.addItem(item)
        layout.addWidget(self._list)
        self.set_values(current)
        self._filter.textChanged.connect(self._apply_filter)
        self._list.itemSelectionChanged.connect(self.changed.emit)

    def values(self):
        """選択中の値を返す。

        Returns:
            選択中の値。
        """
        selected = []
        for index in range(self._list.count()):
            item = self._list.item(index)
            if item.isSelected():
                selected.append(item.data(Qt.ItemDataRole.UserRole))
        return selected

    def set_values(self, values):
        """渡された値を選択する。選択のあいだシグナルは止める。

        Args:
            values: 選択する値。無ければ選択を外す。
        """
        wanted = {config_choice_key(item) for item in (values or [])}
        self._list.blockSignals(True)
        for index in range(self._list.count()):
            item = self._list.item(index)
            item.setSelected(str(item.data(Qt.ItemDataRole.UserRole)) in wanted)
        self._list.blockSignals(False)

    def _apply_filter(self, text: str):
        """文字がラベルにも値にも無い項目を隠す。

        Args:
            text: 絞り込みの文字。空なら全部出す。
        """
        needle = (text or "").casefold()
        for index in range(self._list.count()):
            item = self._list.item(index)
            label = item.text().casefold()
            value = str(item.data(Qt.ItemDataRole.UserRole) or "").casefold()
            item.setHidden(bool(needle) and needle not in label and needle not in value)


class MultiRows(QWidget):
    """同じ項目を行で増減する。"""
    valueChanged = Signal(object)
    rowsChanged = Signal()

    def __init__(self, field, current, parent=None, expand=None):
        """現在値の行と、行を足すボタンを置く。

        Args:
            field: 各行の項目。
            current: 初期の行の値。
            parent: 親ウィジェット。
            expand: 表示を展開する処理。
        """
        super().__init__(parent)
        self._field = field
        self._expand = expand
        self._inners = []
        self._column = QVBoxLayout(self)
        self._column.setContentsMargins(0, 0, 0, 0)
        self._column.setSpacing(4)
        self._rows_box = QVBoxLayout()
        self._rows_box.setContentsMargins(0, 0, 0, 0)
        self._rows_box.setSpacing(4)
        self._column.addLayout(self._rows_box)
        self._add_button = QPushButton("+")
        self._add_button.setFixedWidth(28)
        self._add_button.clicked.connect(self._add_blank)
        self._column.addWidget(self._add_button, 0, Qt.AlignmentFlag.AlignLeft)
        values = list(current or [])
        for value in values:
            self._append_row(value)

    def values(self):
        """各行の値を返す。

        Returns:
            行の値。
        """
        return [read_single(self._field, inner) for inner in self._inners]

    def set_values(self, values):
        """行をいったん消して、渡された値で作り直す。

        Args:
            values: 新しい行の値。無ければ空。
        """
        while self._inners:
            self._remove_at(0)
        for value in values or []:
            self._append_row(value)
        self.rowsChanged.emit()

    def _add_blank(self):
        """空の値の行を足す。"""
        self._append_row(blank_value(self._field))
        self.rowsChanged.emit()
        self.valueChanged.emit(self.values())

    def _append_row(self, value):
        """値の入力行と削除ボタンを足す。

        Args:
            value: 行の初期値。
        """
        inner = make_single_widget(self._field, value, expand=self._expand)
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(inner, 1)
        remove = QPushButton("-")
        remove.setFixedWidth(28)
        layout.addWidget(remove, 0)
        self._rows_box.addWidget(row)
        self._inners.append(inner)
        remove.clicked.connect(lambda _=False, widget=inner: self._remove_inner(widget))
        connect_value_changed(inner, lambda: self.valueChanged.emit(self.values()))

    def _remove_inner(self, inner):
        """その入力の行を消す。見つからなければ何もしない。

        Args:
            inner: 消す行の入力。
        """
        try:
            index = self._inners.index(inner)
        except ValueError:
            # 消す行が既に無いときは、削除をやめて戻る。
            return
        self._remove_at(index)
        self.rowsChanged.emit()
        self.valueChanged.emit(self.values())

    def _remove_at(self, index: int):
        """指定位置の行を外す。

        Args:
            index: 外す行。
        """
        inner = self._inners.pop(index)
        row = inner.parentWidget()
        self._rows_box.removeWidget(row)
        row.deleteLater()


class RangeRow(QWidget):
    """範囲のスライダーと数値入力を連動させる。"""
    valueChanged = Signal(object)

    def __init__(self, field, current, parent=None):
        """範囲のスライダーと数値入力を置く。範囲や刻みが無い整数は 0 から 100 の 1、実数は 0 から 1 の 0.01。

        Args:
            field: 範囲の項目。
            current: 初期値。列なら先頭。無ければ最小。
            parent: 親ウィジェット。
        """
        super().__init__(parent)
        self._as_int = field.value_type == "int_range"
        self._minimum = field.minimum
        self._maximum = field.maximum
        self._step = field.step
        if self._minimum is None or self._maximum is None or self._step is None:
            lo, hi, st = (0, 100, 1) if self._as_int else (0.0, 1.0, 0.01)
            self._minimum = lo if self._minimum is None else self._minimum
            self._maximum = hi if self._maximum is None else self._maximum
            self._step = st if self._step is None else self._step
        span = self._maximum - self._minimum
        if self._step <= 0 or span <= 0:
            self._ticks = 0
        else:
            self._ticks = max(1, int(round(span / self._step)))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, self._ticks)
        if self._as_int:
            self._spin = QSpinBox()
            self._spin.setRange(int(self._minimum), int(self._maximum))
            self._spin.setSingleStep(max(1, int(self._step)))
        else:
            self._spin = QDoubleSpinBox()
            self._spin.setRange(float(self._minimum), float(self._maximum))
            self._spin.setSingleStep(float(self._step))
            self._spin.setDecimals(_decimals_from_step(self._step))
        self._spin.setMaximumWidth(96)
        layout.addWidget(self._slider, 1)
        layout.addWidget(self._spin, 0)
        self._slider.valueChanged.connect(self._from_slider)
        self._spin.valueChanged.connect(self._from_spin)
        seed = current
        if isinstance(seed, (list, tuple)):
            seed = seed[0] if seed else None
        self.setValue(seed if seed is not None else self._minimum)

    def value(self):
        """数値入力の値を返す。

        Returns:
            数値入力の値。
        """
        return self._spin.value()

    def setValue(self, value):
        """範囲内に収めてスライダーと数値へ入れる。入れるあいだシグナルは止める。

        Args:
            value: 入れる値。
        """
        number = self._clamp(value)
        tick = self._tick_for(number)
        self._slider.blockSignals(True)
        self._spin.blockSignals(True)
        self._slider.setValue(tick)
        self._spin.setValue(number)
        self._slider.blockSignals(False)
        self._spin.blockSignals(False)

    def _clamp(self, value):
        """範囲内の数にする。

        Args:
            value: 収める値。変換できないときは最小。

        Returns:
            範囲内の数。
        """
        try:
            number = int(value) if self._as_int else float(value)
        except (TypeError, ValueError):
            # 数値にできないときは範囲の最小値に戻す。
            number = self._minimum
        if number < self._minimum:
            return int(self._minimum) if self._as_int else float(self._minimum)
        if number > self._maximum:
            return int(self._maximum) if self._as_int else float(self._maximum)
        return int(number) if self._as_int else float(number)

    def _tick_for(self, value) -> int:
        """値に対応するスライダー位置を返す。

        Args:
            value: 位置を求める値。

        Returns:
            0 から目盛り数までの位置。目盛りが無ければ 0。
        """
        if self._ticks <= 0 or self._step <= 0:
            return 0
        tick = int(round((value - self._minimum) / self._step))
        if tick < 0:
            return 0
        if tick > self._ticks:
            return self._ticks
        return tick

    def _from_slider(self, tick: int):
        """スライダー位置から数値を更新する。

        Args:
            tick: スライダーの位置。
        """
        number = self._minimum + tick * self._step
        number = self._clamp(number)
        self._spin.blockSignals(True)
        self._spin.setValue(number)
        self._spin.blockSignals(False)
        self.valueChanged.emit(self.value())

    def _from_spin(self, number):
        """数値からスライダー位置を更新する。

        Args:
            number: 数値入力の値。
        """
        tick = self._tick_for(number)
        self._slider.blockSignals(True)
        self._slider.setValue(tick)
        self._slider.blockSignals(False)
        self.valueChanged.emit(self.value())


class PathRow(QWidget):
    """パス入力と参照ボタン。"""
    valueChanged = Signal(object)

    def __init__(self, field, current, parent=None, expand=None):
        """パス欄と参照ボタンを置く。

        Args:
            field: パスの種類とフィルタを持つ項目。
            current: 初期パス。
            parent: 親ウィジェット。
            expand: ファイルダイアログのフィルタを展開する処理。
        """
        super().__init__(parent)
        self._kind = field.path_kind
        self._filter = field.path_filter
        self._expand = expand if expand is not None else (lambda value: "" if value is None else str(value))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self._edit = QLineEdit()
        self._edit.setText("" if current is None else str(current))
        browse = QPushButton(get_text("ui.plugin_config_browse"))
        browse.clicked.connect(self._browse)
        layout.addWidget(self._edit, 1)
        layout.addWidget(browse, 0)
        self._edit.editingFinished.connect(lambda: self.valueChanged.emit(self.text()))

    def text(self) -> str:
        """入力中のパスを返す。

        Returns:
            パス文字列。
        """
        return self._edit.text()

    def setText(self, value: str):
        """パス欄へ入れる。

        Args:
            value: 入れるパス。None は空。
        """
        self._edit.setText("" if value is None else str(value))

    def _browse(self):
        """ディレクトリかファイルを選び、選ばれたパスを欄へ入れる。"""
        start = self._edit.text().strip() or ""
        if self._kind == "directory":
            path = QFileDialog.getExistingDirectory(self, get_text("ui.plugin_config_browse"), start)
        else:
            path, _ = QFileDialog.getOpenFileName(
                self,
                get_text("ui.plugin_config_browse"),
                start,
                self._expand(self._filter) if self._filter else "",
            )
        if path:
            self._edit.setText(path)
            self.valueChanged.emit(path)
