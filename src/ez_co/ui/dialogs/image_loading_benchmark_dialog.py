"""このPCで最適な画像読み込み設定を測る、確認・進捗・結果のダイアログ。"""
import logging
import threading

import humanfriendly
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from ez_co.services.image_loading_benchmark import (
    STAGE_CACHE,
    STAGE_PREPARE,
    STAGE_WORKER,
    BenchmarkCancelled,
    run_image_loading_benchmark,
)
from ez_co.services.image_loading_benchmark_evaluator import evaluate_benchmark
from ez_co.utils.image_loader_workers import AUTO_IMAGE_LOADER_WORKERS
from ez_co.utils.language_manager import get_log_text, get_text

logger = logging.getLogger(__name__)

# 測定段階から進捗表示の言語キーへの対応。
STAGE_TEXT_KEYS = {
    STAGE_PREPARE: "settings.cache_benchmark_stage_prepare",
    STAGE_WORKER: "settings.cache_benchmark_stage_worker",
    STAGE_CACHE: "settings.cache_benchmark_stage_cache",
}


class ImageLoadingBenchmarkThread(QThread):
    """measurementはこのthreadが持つ。handlerと素材の後片付けもservice側で行う。"""

    progress_changed = Signal(str, int, int, int, int)
    finished_with_outcome = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, parent=None):
        """キャンセル用のイベントを用意する。

        Args:
            parent: 親ウィジェット。
        """
        super().__init__(parent)
        self.setObjectName("ImageLoadingBenchmarkThread")
        self._cancel_event = threading.Event()

    def request_cancel(self):
        """GUIからはcancel要求だけを出す。resourceはworker側が閉じる。"""
        self._cancel_event.set()

    def run(self):
        """測定を実行し、結果、失敗、キャンセルのいずれかを知らせる。"""
        try:
            report = run_image_loading_benchmark(
                progress=self._emit_progress,
                cancel_event=self._cancel_event,
            )
        except BenchmarkCancelled:
            # 測定の中止は失敗にせず、キャンセルを知らせて戻る。
            self.cancelled.emit()
            return
        except Exception as error:
            # 測定中の失敗はログして、失敗を知らせて戻る。
            logger.error(get_log_text("image_loading_benchmark_failed", error=error))
            self.failed.emit(str(error))
            return
        self.finished_with_outcome.emit(evaluate_benchmark(report))

    def _emit_progress(self, stage, stage_index, stage_total, overall_index, overall_total):
        """段階と全体の進捗を知らせる。

        Args:
            stage: いまの段階。
            stage_index: 段階内の位置。
            stage_total: 段階内の総数。
            overall_index: 全体の位置。
            overall_total: 全体の総数。
        """
        self.progress_changed.emit(
            stage,
            stage_index,
            stage_total,
            overall_index,
            overall_total,
        )


class ImageLoadingBenchmarkProgressDialog(QDialog):
    """測定中の進捗とキャンセルだけを出す。"""

    def __init__(self, parent=None):
        """段階、進捗バー、キャンセルを配置し、測定スレッドをつなぐ。

        Args:
            parent: 親ウィジェット。
        """
        super().__init__(parent)
        self.setWindowTitle(get_text("settings.cache_benchmark_progress_title"))
        self.setModal(True)
        self.setMinimumWidth(420)
        self.outcome = None
        self.error_message = None
        self.was_cancelled = False
        self._closing = False

        layout = QVBoxLayout()
        self.stage_label = QLabel(
            get_text("settings.cache_benchmark_stage_prepare")
        )
        self.stage_label.setWordWrap(True)
        layout.addWidget(self.stage_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        self.note_label = QLabel(get_text("settings.cache_benchmark_progress_note"))
        self.note_label.setWordWrap(True)
        self.note_label.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(self.note_label)

        button_row = QHBoxLayout()
        button_row.addStretch()
        self.cancel_button = QPushButton(get_text("ui.cancel"))
        self.cancel_button.clicked.connect(self.request_cancel)
        button_row.addWidget(self.cancel_button)
        layout.addLayout(button_row)
        self.setLayout(layout)

        self._thread = ImageLoadingBenchmarkThread(self)
        self._thread.progress_changed.connect(self._on_progress)
        self._thread.finished_with_outcome.connect(self._on_finished)
        self._thread.failed.connect(self._on_failed)
        self._thread.cancelled.connect(self._on_cancelled)

    def start(self):
        """測定スレッドを開始する。"""
        self._thread.start()

    def request_cancel(self):
        """cancel Eventをsetし、thread終了を待ってから閉じる。"""
        self.was_cancelled = True
        self.cancel_button.setEnabled(False)
        self.stage_label.setText(get_text("settings.cache_benchmark_cancelling"))
        self._thread.request_cancel()

    def _on_progress(self, stage, stage_index, stage_total, overall_index, overall_total):
        """段階の文言と全体の進捗バーを更新する。

        Args:
            stage: いまの段階。
            stage_index: 段階内の位置。
            stage_total: 段階内の総数。
            overall_index: 全体の位置。
            overall_total: 全体の総数。
        """
        stage_text = get_text(
            STAGE_TEXT_KEYS.get(stage, "settings.cache_benchmark_stage_prepare")
        )
        self.stage_label.setText(
            get_text("settings.cache_benchmark_progress_stage").format(
                stage=stage_text,
                stage_index=stage_index,
                stage_total=stage_total,
                overall_index=max(1, overall_index),
                overall_total=overall_total,
            )
        )
        self.progress_bar.setRange(0, max(1, overall_total))
        self.progress_bar.setValue(max(0, overall_index - 1))

    def _on_finished(self, outcome):
        """結果を残してダイアログを確定で閉じる。

        Args:
            outcome: 測定結果。
        """
        self.outcome = outcome
        self._finish(QDialog.Accepted)

    def _on_failed(self, message):
        """失敗メッセージを残してダイアログを拒否で閉じる。

        Args:
            message: 失敗の内容。
        """
        self.error_message = message
        self._finish(QDialog.Rejected)

    def _on_cancelled(self):
        """キャンセル済みにしてダイアログを拒否で閉じる。"""
        self.was_cancelled = True
        self._finish(QDialog.Rejected)

    def _finish(self, result):
        """スレッドの終了を待ってから、指定の結果で閉じる。

        Args:
            result: ダイアログの結果。
        """
        self._wait_for_thread()
        self.done(result)

    def _wait_for_thread(self):
        """スレッドが動いていれば終了を待つ。"""
        if self._thread.isRunning():
            self._thread.wait()

    def closeEvent(self, event):
        """スレッドが動いていればキャンセルして終了を待ってから閉じる。

        Args:
            event: 閉じるイベント。
        """
        # QThread: Destroyed while thread is still running を起こさない
        if self._thread.isRunning():
            if not self._closing:
                self._closing = True
                self.request_cancel()
            self._wait_for_thread()
        super().closeEvent(event)

    def reject(self):
        """スレッドが動いていればキャンセルして終了を待ってから拒否する。"""
        if self._thread.isRunning():
            self.request_cancel()
            self._wait_for_thread()
        super().reject()


class ImageLoadingBenchmarkResultDialog(QDialog):
    """測定結果を出し、採用するかを選ばせる。"""

    def __init__(self, outcome, current_settings, parent=None):
        """現在値と測定結果、再起動の注意、採用とキャンセルを出す。

        Args:
            outcome: 測定結果。
            current_settings: いまのメモリ上限、先読みページ、ワーカー表示。
            parent: 親ウィジェット。
        """
        super().__init__(parent)
        self.setWindowTitle(get_text("settings.cache_benchmark_result_title"))
        self.setModal(True)
        self.setMinimumWidth(420)
        self.outcome = outcome

        layout = QVBoxLayout()
        current_label = QLabel(
            get_text("settings.cache_current_settings").format(
                memory_limit=current_settings["memory_limit"],
                prefetch_pages=current_settings["prefetch_pages"],
                workers=current_settings["workers"],
            )
        )
        current_label.setWordWrap(True)
        layout.addWidget(current_label)

        measured_label = QLabel(
            get_text("settings.cache_benchmark_result_measured").format(
                memory_limit=outcome.memory_limit,
                prefetch_pages=outcome.prefetch_pages,
                workers=self._worker_text(outcome),
            )
        )
        measured_label.setWordWrap(True)
        layout.addWidget(measured_label)

        detail_label = QLabel(
            get_text("settings.cache_benchmark_result_detail").format(
                p95=f"{outcome.p95_latency_ms:.1f}",
                max=f"{outcome.max_latency_ms:.1f}",
                memory=self._rss_text(outcome.condition_rss_delta_bytes),
                elapsed=f"{outcome.elapsed_seconds:.0f}",
            )
        )
        detail_label.setWordWrap(True)
        detail_label.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(detail_label)

        restart_label = QLabel(get_text("settings.cache_benchmark_result_restart_note"))
        restart_label.setWordWrap(True)
        restart_label.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(restart_label)

        buttons = QDialogButtonBox()
        apply_button = buttons.addButton(
            get_text("settings.cache_benchmark_result_apply"),
            QDialogButtonBox.AcceptRole,
        )
        apply_button.setDefault(True)
        buttons.addButton(get_text("ui.cancel"), QDialogButtonBox.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def _worker_text(self, outcome):
        """ワーカー数の表示文を返す。

        Args:
            outcome: 測定結果。

        Returns:
            自動のときは実効数入りの文言。それ以外はワーカー数の文字列。
        """
        if outcome.image_loader_workers == AUTO_IMAGE_LOADER_WORKERS:
            return get_text("settings.cache_recommended_workers_auto").format(
                count=outcome.effective_workers
            )
        return str(outcome.image_loader_workers)

    def _rss_text(self, rss_delta_bytes):
        """メモリ差分の表示文を返す。

        Args:
            rss_delta_bytes: メモリ差分のバイト数。無ければ None。

        Returns:
            人が読める大きさ。無ければ不明の文言。
        """
        if rss_delta_bytes is None:
            return get_text("settings.cache_benchmark_result_memory_unknown")
        return humanfriendly.format_size(rss_delta_bytes, binary=True)


def confirm_image_loading_benchmark(parent=None) -> bool:
    """所要時間と結果が環境に左右されることを伝えてから始める。

    Args:
        parent: 親ウィジェット。

    Returns:
        開始が押されたとき True。
    """
    message_box = QMessageBox(parent)
    message_box.setIcon(QMessageBox.Question)
    message_box.setWindowTitle(get_text("settings.cache_benchmark_confirm_title"))
    message_box.setText(get_text("settings.cache_benchmark_confirm_text"))
    message_box.setInformativeText(
        get_text("settings.cache_benchmark_confirm_detail")
    )
    start_button = message_box.addButton(
        get_text("settings.cache_benchmark_confirm_start"),
        QMessageBox.AcceptRole,
    )
    message_box.addButton(get_text("ui.cancel"), QMessageBox.RejectRole)
    message_box.setDefaultButton(start_button)
    message_box.exec()
    return message_box.clickedButton() is start_button


def current_cache_settings_text(dialog) -> dict:
    """結果ダイアログへ出す現在値をwidgetから読む。

    Args:
        dialog: メモリ上限、先読みページ、ワーカー表示を持つ設定ダイアログ。

    Returns:
        memory_limit、prefetch_pages、workers を持つ辞書。空のメモリ上限は -。
    """
    return {
        "memory_limit": dialog.cache_memory_limit.text().strip() or "-",
        "prefetch_pages": dialog.cache_prefetch_pages.value(),
        "workers": dialog.current_worker_display(),
    }


def run_image_loading_benchmark_dialog(settings_dialog):
    """確認 → 測定 → 結果の順に出し、採用された結果だけを返す。

    Args:
        settings_dialog: 確認と結果の親にする設定ダイアログ。

    Returns:
        採用された測定結果。始めない、失敗、中断、結果を閉じたときは None。
    """
    if not confirm_image_loading_benchmark(settings_dialog):
        return None
    progress_dialog = ImageLoadingBenchmarkProgressDialog(settings_dialog)
    progress_dialog.start()
    progress_dialog.exec()
    if progress_dialog.error_message:
        QMessageBox.warning(
            settings_dialog,
            get_text("dialogs.error"),
            get_text("settings.cache_benchmark_failed").format(
                error=progress_dialog.error_message
            ),
        )
        return None
    if progress_dialog.outcome is None:
        return None
    result_dialog = ImageLoadingBenchmarkResultDialog(
        progress_dialog.outcome,
        current_cache_settings_text(settings_dialog),
        settings_dialog,
    )
    if result_dialog.exec() != QDialog.Accepted:
        return None
    return progress_dialog.outcome
