"""ビルドイン基本補正の設定ダイアログ。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ez_co.filters.builtin import BUILTIN_FILTER_ID, normalize_basic_settings
from ez_co.utils.language_manager import get_text


class FilterDialog(QDialog):
    def __init__(self, window, parent=None):
        super().__init__(parent or window)
        self._window = window
        self._config = window.config
        settings = normalize_basic_settings(
            (self._config.filters.get("settings") or {}).get(BUILTIN_FILTER_ID)
        )
        self._snapshot = dict(settings)
        self.setWindowTitle(get_text("ui.filter_dialog_title"))
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
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._apply_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._brightness.valueChanged.connect(self._preview)
        self._contrast.valueChanged.connect(self._preview)
        self._gamma.valueChanged.connect(self._preview)
        self._grayscale.toggled.connect(self._preview)

    def _in_pipe(self) -> bool:
        pipe = [str(item) for item in (self._config.filters.get("pipe") or [])]
        return BUILTIN_FILTER_ID in pipe

    def _current_settings(self) -> dict:
        return {
            "brightness": int(self._brightness.value()),
            "contrast": int(self._contrast.value()),
            "gamma": float(self._gamma.value()),
            "grayscale": bool(self._grayscale.isChecked()),
        }

    def _write_settings(self, settings: dict) -> None:
        stored = dict(self._config.filters.get("settings") or {})
        stored[BUILTIN_FILTER_ID] = normalize_basic_settings(settings)
        self._config.filters["settings"] = stored

    def _preview(self, *_args) -> None:
        self._write_settings(self._current_settings())
        if self._in_pipe():
            self._window.update_image()

    def _apply_and_accept(self) -> None:
        self._write_settings(self._current_settings())
        self._window.save_config()
        if self._in_pipe():
            self._window.update_image()
        self.accept()

    def reject(self):
        self._write_settings(self._snapshot)
        if self._in_pipe():
            self._window.update_image()
        super().reject()


class _IntRangeRow(QWidget):
    def __init__(self, minimum: int, maximum: int, step: int, value: int, parent=None):
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
        return self._spin.valueChanged

    def value(self) -> int:
        return int(self._spin.value())

    def setValue(self, value: int) -> None:
        clamped = max(self._minimum, min(self._maximum, int(value)))
        self._spin.blockSignals(True)
        self._slider.blockSignals(True)
        self._spin.setValue(clamped)
        self._slider.setValue(int(round((clamped - self._minimum) / self._step)))
        self._spin.blockSignals(False)
        self._slider.blockSignals(False)

    def _on_slider(self, tick: int) -> None:
        self._spin.setValue(self._minimum + tick * self._step)

    def _on_spin(self, value: int) -> None:
        self._slider.blockSignals(True)
        self._slider.setValue(int(round((value - self._minimum) / self._step)))
        self._slider.blockSignals(False)


class _FloatRangeRow(QWidget):
    def __init__(self, minimum: float, maximum: float, step: float, value: float, parent=None):
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
        return self._spin.valueChanged

    def value(self) -> float:
        return float(self._spin.value())

    def setValue(self, value: float) -> None:
        clamped = max(self._minimum, min(self._maximum, float(value)))
        self._spin.blockSignals(True)
        self._slider.blockSignals(True)
        self._spin.setValue(clamped)
        self._slider.setValue(int(round((clamped - self._minimum) / self._step)))
        self._spin.blockSignals(False)
        self._slider.blockSignals(False)

    def _on_slider(self, tick: int) -> None:
        self._spin.setValue(self._minimum + tick * self._step)

    def _on_spin(self, value: float) -> None:
        self._slider.blockSignals(True)
        self._slider.setValue(int(round((value - self._minimum) / self._step)))
        self._slider.blockSignals(False)
