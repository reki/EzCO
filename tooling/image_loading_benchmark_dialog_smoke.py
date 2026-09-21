"""実測ダイアログのthread lifecycleを小さい素材で確認する手動smoke。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog

from ez_co.services import image_loading_benchmark as service
from ez_co.ui.dialogs import image_loading_benchmark_dialog as dialog_module


def small_dataset(root):
    return service.generate_dataset(Path(root), page_count=6, page_size=(96, 96))


def small_run(**kwargs):
    kwargs.update(
        dataset_factory=small_dataset,
        source_pages=6,
        measurement_pages=3,
        warmup_runs=0,
        measured_runs=1,
        logical_cpu_count=4,
        physical_memory_bytes=8 * 1024**3,
    )
    return service.run_image_loading_benchmark(**kwargs)


def main():
    app = QApplication(sys.argv)
    dialog_module.run_image_loading_benchmark = small_run

    progress = dialog_module.ImageLoadingBenchmarkProgressDialog()
    progress.start()
    result = progress.exec()
    print("completed:", result == QDialog.Accepted, progress.outcome)
    assert progress.outcome is not None
    assert not progress._thread.isRunning()

    cancelling = dialog_module.ImageLoadingBenchmarkProgressDialog()
    cancelling.start()
    QTimer.singleShot(50, cancelling.request_cancel)
    cancelling.exec()
    print("cancelled:", cancelling.was_cancelled, "outcome:", cancelling.outcome)
    assert cancelling.was_cancelled and cancelling.outcome is None
    assert not cancelling._thread.isRunning()

    closing = dialog_module.ImageLoadingBenchmarkProgressDialog()
    closing.start()
    QTimer.singleShot(50, closing.close)
    closing.exec()
    print("closed while running:", not closing._thread.isRunning())
    assert not closing._thread.isRunning()

    app.processEvents()
    print("smoke ok")


if __name__ == "__main__":
    main()
