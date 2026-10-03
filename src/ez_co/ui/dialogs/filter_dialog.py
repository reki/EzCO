"""ビルドイン基本補正の設定ダイアログ。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ez_co.filters.builtin import BUILTIN_FILTER_ID, default_basic_settings, normalize_basic_settings
from ez_co.utils.language_manager import get_text


class FilterDialog(QDialog):
    """基本フィルターの明るさ、コントラスト、ガンマ、グレースケールを調整する。"""

    def __init__(self, window, parent=None):
        """基本フィルターの現在値でダイアログを組み立てる。

        Args:
            window: 設定と画像更新に使うウィンドウ。
            parent: 親ウィジェット。無ければ window。
        """
        super().__init__(parent or window)
        self._window = window
        self._config = window.config
        settings = normalize_basic_settings(
            (self._config.filters.get("settings") or {}).get(BUILTIN_FILTER_ID)
        )
        self._snapshot = dict(settings)
        self.setWindowTitle(get_text("ui.filter_basic"))
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._brightness = _IntRangeRow(-100, 100, 1, settings["brightness"])
        self._contrast = _IntRangeRow(-100, 100, 1, settings["contrast"])
        self._gamma = _FloatRangeRow(0.2, 3.0, 0.05, settings["gamma"])
        self._grayscale = QCheckBox()
        self._grayscale.setChecked(bool(settings["grayscale"]))
        form.addRow(get_text("ui.filter_brightness"), self._brightness)
        form.addRow(get_text("ui.filter_contrast"), self._contrast)
        form.addRow(get_text("ui.filter_gamma"), self._gamma)
        form.addRow(get_text("ui.filter_grayscale"), self._grayscale)
        layout.addLayout(form)
        buttons = QHBoxLayout()
        buttons.addStretch()
        reset_button = QPushButton(get_text("ui.reset"))
        reset_button.clicked.connect(self._reset_to_defaults)
        ok_button = QPushButton(get_text("ui.ok"))
        ok_button.clicked.connect(self._apply_and_accept)
        cancel_button = QPushButton(get_text("ui.cancel"))
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(reset_button)
        buttons.addWidget(ok_button)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)
        self._reset_button = reset_button
        self._brightness.valueChanged.connect(self._preview)
        self._contrast.valueChanged.connect(self._preview)
        self._gamma.valueChanged.connect(self._preview)
        self._grayscale.toggled.connect(self._preview)

    def _in_pipe(self) -> bool:
        """基本フィルターが pipe に入っているかを返す。

        Returns:
            入っているとき True。
        """
        pipe = [str(item) for item in (self._config.filters.get("pipe") or [])]
        return BUILTIN_FILTER_ID in pipe

    def _current_settings(self) -> dict:
        """画面上の明るさ、コントラスト、ガンマ、グレースケールを返す。

        Returns:
            その4つを持つ辞書。
        """
        return {
            "brightness": int(self._brightness.value()),
            "contrast": int(self._contrast.value()),
            "gamma": float(self._gamma.value()),
            "grayscale": bool(self._grayscale.isChecked()),
        }

    def _write_settings(self, settings: dict) -> None:
        """基本フィルターの設定を config に書く。

        Args:
            settings: 書く値。
        """
        stored = dict(self._config.filters.get("settings") or {})
        stored[BUILTIN_FILTER_ID] = normalize_basic_settings(settings)
        self._config.filters["settings"] = stored

    def _preview(self, *_args) -> None:
        """現在値を書いて、pipe に入っていれば画像を更新する。

        Args:
            _args: 値変更シグナルが渡す引数。使わない。
        """
        self._write_settings(self._current_settings())
        if self._in_pipe():
            self._window.update_image()

    def _reset_to_defaults(self) -> None:
        """既定値に戻してプレビューする。"""
        defaults = default_basic_settings()
        self._brightness.setValue(defaults["brightness"])
        self._contrast.setValue(defaults["contrast"])
        self._gamma.setValue(defaults["gamma"])
        self._grayscale.blockSignals(True)
        self._grayscale.setChecked(bool(defaults["grayscale"]))
        self._grayscale.blockSignals(False)
        self._preview()

    def _apply_and_accept(self) -> None:
        """現在値を保存し、pipe に入っていれば画像を更新して閉じる。"""
        self._write_settings(self._current_settings())
        self._window.save_config()
        if self._in_pipe():
            self._window.update_image()
        self.accept()

    def reject(self):
        """開いたときの値に戻し、pipe に入っていれば画像を更新してから閉じる。"""
        self._write_settings(self._snapshot)
        if self._in_pipe():
            self._window.update_image()
        super().reject()


class _IntRangeRow(QWidget):
    """整数のスライダーとスピンボックスを連動させる。"""

    def __init__(self, minimum: int, maximum: int, step: int, value: int, parent=None):
        """整数の範囲と初期値でスライダーとスピンボックスを置く。

        Args:
            minimum: 最小値。
            maximum: 最大値。
            step: 刻み。1未満は1にする。
            value: 初期値。
            parent: 親ウィジェット。
        """
        super().__init__(parent)
        self._minimum = minimum
        self._maximum = maximum
        self._step = max(1, step)
        span = maximum - minimum
        self._ticks = max(1, span // self._step)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, self._ticks)
        self._spin = QSpinBox()
        self._spin.setRange(minimum, maximum)
        self._spin.setSingleStep(self._step)
        layout.addWidget(self._slider, 1)
        layout.addWidget(self._spin)
        self._slider.valueChanged.connect(self._on_slider)
        self._spin.valueChanged.connect(self._on_spin)
        self.setValue(value)

    @property
    def valueChanged(self):
        """値の変更シグナルを返す。

        Returns:
            スピンボックスの valueChanged。
        """
        return self._spin.valueChanged

    def value(self) -> int:
        """現在の整数を返す。

        Returns:
            スピンボックスの値。
        """
        return int(self._spin.value())

    def setValue(self, value: int) -> None:
        """範囲内に収めてスライダーとスピンボックスへ反映する。反映中はシグナルを出さない。

        Args:
            value: 設定する整数。
        """
        clamped = max(self._minimum, min(self._maximum, int(value)))
        self._spin.blockSignals(True)
        self._slider.blockSignals(True)
        self._spin.setValue(clamped)
        self._slider.setValue(int(round((clamped - self._minimum) / self._step)))
        self._spin.blockSignals(False)
        self._slider.blockSignals(False)

    def _on_slider(self, tick: int) -> None:
        """スライダーの目盛りからスピンボックスを更新する。

        Args:
            tick: スライダーの位置。
        """
        self._spin.setValue(self._minimum + tick * self._step)

    def _on_spin(self, value: int) -> None:
        """スピンボックスの値からスライダーを更新する。

        Args:
            value: スピンボックスの値。
        """
        self._slider.blockSignals(True)
        self._slider.setValue(int(round((value - self._minimum) / self._step)))
        self._slider.blockSignals(False)


class _FloatRangeRow(QWidget):
    """実数のスライダーとスピンボックスを連動させる。"""

    def __init__(self, minimum: float, maximum: float, step: float, value: float, parent=None):
        """実数の範囲と初期値でスライダーとスピンボックスを置く。

        Args:
            minimum: 最小値。
            maximum: 最大値。
            step: 刻み。0 のときは 0.05。
            value: 初期値。
            parent: 親ウィジェット。
        """
        super().__init__(parent)
        self._minimum = float(minimum)
        self._maximum = float(maximum)
        self._step = float(step) if step else 0.05
        span = self._maximum - self._minimum
        self._ticks = max(1, int(round(span / self._step)))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, self._ticks)
        self._spin = QDoubleSpinBox()
        self._spin.setRange(self._minimum, self._maximum)
        self._spin.setSingleStep(self._step)
        self._spin.setDecimals(2)
        layout.addWidget(self._slider, 1)
        layout.addWidget(self._spin)
        self._slider.valueChanged.connect(self._on_slider)
        self._spin.valueChanged.connect(self._on_spin)
        self.setValue(value)

    @property
    def valueChanged(self):
        """値の変更シグナルを返す。

        Returns:
            スピンボックスの valueChanged。
        """
        return self._spin.valueChanged

    def value(self) -> float:
        """現在の実数を返す。

        Returns:
            スピンボックスの値。
        """
        return float(self._spin.value())

    def setValue(self, value: float) -> None:
        """範囲内に収めてスライダーとスピンボックスへ反映する。反映中はシグナルを出さない。

        Args:
            value: 設定する実数。
        """
        clamped = max(self._minimum, min(self._maximum, float(value)))
        self._spin.blockSignals(True)
        self._slider.blockSignals(True)
        self._spin.setValue(clamped)
        self._slider.setValue(int(round((clamped - self._minimum) / self._step)))
        self._spin.blockSignals(False)
        self._slider.blockSignals(False)

    def _on_slider(self, tick: int) -> None:
        """スライダーの目盛りからスピンボックスを更新する。

        Args:
            tick: スライダーの位置。
        """
        self._spin.setValue(self._minimum + tick * self._step)

    def _on_spin(self, value: float) -> None:
        """スピンボックスの値からスライダーを更新する。

        Args:
            value: スピンボックスの値。
        """
        self._slider.blockSignals(True)
        self._slider.setValue(int(round((value - self._minimum) / self._step)))
        self._slider.blockSignals(False)
