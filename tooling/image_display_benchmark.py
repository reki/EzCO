"""ImageView までの表示準備時間を生成画像で測る CLI benchmark。"""
from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Iterable

# Linux の画面なし環境だけ既定値を補う。明示された Qt platform は変更しない。
if sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image, ImageChops, __version__ as PILLOW_VERSION
from PySide6 import __version__ as PYSIDE_VERSION
from PySide6.QtCore import QThread, qVersion
from PySide6.QtWidgets import QApplication

from ez_co.filters.builtin import BUILTIN_FILTER_ID, register_builtin
from ez_co.filters.pipeline import apply_pipe
from ez_co.filters.registry import FilterRegistry
from ez_co.ui.viewer.image_view import ImageView


MODES = ("filter_off", "builtin_basic", "spread")
STAGE_NAMES = (
    "filter_ms",
    "page_a_filter_ms",
    "page_b_filter_ms",
    "combine_spread_ms",
    "rgba_convert_ms",
    "set_image_call_ms",
    "non_rgba_set_image_preparation_ms",
    "display_preparation_total_ms",
)
DEFAULT_IMAGE_SIZE = (2400, 3200)
DEFAULT_WIDGET_SIZE = (1280, 720)
MEASUREMENT_SCOPE = (
    "PIL filter・見開き合成・ImageView.set_image 内の表示準備まで。"
    "Qt paint event と compositor の frame latency は含まない。"
)


def _elapsed_ms(started: float) -> float:
    return max(0.0, (time.perf_counter() - started) * 1000.0)


def _pattern_image(size: tuple[int, int], variant: int) -> Image.Image:
    """高速に再現可能な高解像度 RGB 素材を生成する。"""
    gradient = Image.linear_gradient("L").resize(size)
    green = ImageChops.offset(gradient, variant * 37, variant * 53)
    blue = ImageChops.offset(gradient, variant * 71, variant * 29)
    try:
        return Image.merge("RGB", (gradient, green, blue))
    finally:
        gradient.close()
        green.close()
        blue.close()


def environment_metadata(image_size: tuple[int, int]) -> dict:
    """比較時に必要な実行環境と入力寸法を返す。"""
    return {
        "os": platform.platform(),
        "python": platform.python_version(),
        "pillow": PILLOW_VERSION,
        "pyside": PYSIDE_VERSION,
        "qt": qVersion(),
        "logical_cpu_count": os.cpu_count(),
        "image_width": image_size[0],
        "image_height": image_size[1],
    }


def ensure_gui_main_thread(app: QApplication) -> None:
    """QApplication の GUI thread 以外からの実行を拒否する。"""
    if QThread.currentThread() is not app.thread():
        raise RuntimeError("display benchmark must run on the QApplication GUI main thread")


def _view_config() -> SimpleNamespace:
    return SimpleNamespace(
        viewer={
            "background_color": "#c0ffc0",
            "fit_to_window_minimum": True,
            "zoom_navigation_mode": "page",
        },
        shortcuts={},
    )


def _measure_set_image(view: ImageView, image: Image.Image) -> tuple[float, float]:
    """set_image 中に実行された RGBA convert だけを計測する。"""
    original_convert = Image.Image.convert
    rgba_convert_ms = 0.0

    def measured_convert(source, mode=None, *args, **kwargs):
        nonlocal rgba_convert_ms
        if str(mode or "").upper() != "RGBA":
            return original_convert(source, mode, *args, **kwargs)
        started = time.perf_counter()
        try:
            return original_convert(source, mode, *args, **kwargs)
        finally:
            rgba_convert_ms += _elapsed_ms(started)

    Image.Image.convert = measured_convert
    started = time.perf_counter()
    try:
        view.set_image(image)
    finally:
        set_image_call_ms = _elapsed_ms(started)
        Image.Image.convert = original_convert
    return set_image_call_ms, rgba_convert_ms


def _close_temporary_images(
    images: Iterable[Image.Image | None],
    sources: Iterable[Image.Image],
) -> None:
    source_ids = {id(image) for image in sources}
    closed: set[int] = set()
    for image in images:
        if image is None or id(image) in source_ids or id(image) in closed:
            continue
        closed.add(id(image))
        image.close()


def _filter_image(
    image: Image.Image,
    *,
    enabled: bool,
    registry: FilterRegistry,
    page: int,
) -> tuple[Image.Image, float]:
    started = time.perf_counter()
    result = apply_pipe(
        image,
        [BUILTIN_FILTER_ID] if enabled else [],
        page=page,
        builtin_settings={
            "brightness": 10,
            "contrast": 0,
            "gamma": 1.0,
            "grayscale": False,
        },
        registry=registry,
    )
    if result is None:
        raise RuntimeError("display filter unexpectedly returned no image")
    return result, _elapsed_ms(started)


def _measure_iteration(
    mode: str,
    view: ImageView,
    sources: tuple[Image.Image, Image.Image],
    registry: FilterRegistry,
) -> dict[str, float]:
    page_a = page_b = combined = display_image = None
    page_a_filter_ms = 0.0
    page_b_filter_ms = 0.0
    combine_spread_ms = 0.0
    try:
        if mode == "filter_off":
            page_a, page_a_filter_ms = _filter_image(
                sources[0], enabled=False, registry=registry, page=1
            )
            display_image = page_a
        elif mode == "builtin_basic":
            page_a, page_a_filter_ms = _filter_image(
                sources[0], enabled=True, registry=registry, page=1
            )
            display_image = page_a
        elif mode == "spread":
            page_a, page_a_filter_ms = _filter_image(
                sources[0], enabled=True, registry=registry, page=1
            )
            page_b, page_b_filter_ms = _filter_image(
                sources[1], enabled=True, registry=registry, page=2
            )
            started = time.perf_counter()
            combined = view.combine_spread_images(page_a, page_b)
            combine_spread_ms = _elapsed_ms(started)
            display_image = combined
        else:
            raise ValueError(f"unknown display benchmark mode: {mode}")

        filter_ms = page_a_filter_ms + page_b_filter_ms
        set_image_call_ms, rgba_convert_ms = _measure_set_image(view, display_image)
        non_rgba_ms = max(0.0, set_image_call_ms - rgba_convert_ms)
        return {
            "filter_ms": filter_ms,
            "page_a_filter_ms": page_a_filter_ms,
            "page_b_filter_ms": page_b_filter_ms,
            "combine_spread_ms": combine_spread_ms,
            "rgba_convert_ms": rgba_convert_ms,
            "set_image_call_ms": set_image_call_ms,
            "non_rgba_set_image_preparation_ms": non_rgba_ms,
            "display_preparation_total_ms": (
                filter_ms + combine_spread_ms + set_image_call_ms
            ),
        }
    finally:
        # current_image と Qt 変換元を先に解放し、一時 PIL 画像はその後で閉じる。
        view.set_image(None)
        _close_temporary_images(
            (combined, page_b, page_a),
            sources,
        )


def aggregate_stages(samples: list[dict[str, float]]) -> dict[str, dict[str, float]]:
    """各 stage の反復値を非負の集約値へまとめる。"""
    stages = {}
    for name in STAGE_NAMES:
        values = [max(0.0, float(sample[name])) for sample in samples]
        stages[name] = {
            "average_ms": statistics.fmean(values) if values else 0.0,
            "min_ms": min(values, default=0.0),
            "max_ms": max(values, default=0.0),
            "total_ms": sum(values),
        }
    return stages


def run_mode(
    mode: str,
    *,
    warmups: int = 1,
    iterations: int = 5,
    image_size: tuple[int, int] = DEFAULT_IMAGE_SIZE,
    widget_size: tuple[int, int] = DEFAULT_WIDGET_SIZE,
    app: QApplication | None = None,
    thread_probe: Callable[[], int] | None = None,
) -> dict:
    """1モードを GUI main thread 上で実行する。"""
    if mode not in MODES:
        raise ValueError(f"unknown display benchmark mode: {mode}")
    if warmups < 0 or iterations < 1:
        raise ValueError("warmups must be non-negative and iterations must be positive")
    app = app or QApplication.instance() or QApplication([])
    ensure_gui_main_thread(app)
    if thread_probe is not None:
        thread_probe()

    registry = FilterRegistry()
    register_builtin(registry)
    sources = (_pattern_image(image_size, 1), _pattern_image(image_size, 2))
    view = ImageView(config=_view_config())
    view.setFixedSize(*widget_size)
    view.layout().activate()
    app.processEvents()
    try:
        for _ in range(warmups):
            app.processEvents()
            _measure_iteration(mode, view, sources, registry)
        samples = []
        for _ in range(iterations):
            # 計測前に保留中の resize / timer 等を処理し、stage 外へ出す。
            app.processEvents()
            samples.append(_measure_iteration(mode, view, sources, registry))
        return {
            "mode": mode,
            "conditions": {
                "warmups": warmups,
                "measurement_iterations": iterations,
                "widget_width": widget_size[0],
                "widget_height": widget_size[1],
                "builtin_brightness": 10 if mode != "filter_off" else 0,
                "gui_main_thread": True,
            },
            "measurement_scope": MEASUREMENT_SCOPE,
            "excludes_qt_paint_compositor_latency": True,
            "environment": environment_metadata(image_size),
            "samples": samples,
            "stages": aggregate_stages(samples),
        }
    finally:
        view.set_image(None)
        view.close()
        app.processEvents()
        for source in sources:
            source.close()


def _subprocess_environment() -> dict[str, str]:
    root = Path(__file__).resolve().parent.parent
    paths = [str(root), str(root / "src")]
    existing = os.environ.get("PYTHONPATH")
    if existing:
        paths.append(existing)
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(paths)
    environment["PYTHONIOENCODING"] = "utf-8"
    if sys.platform.startswith("linux"):
        environment.setdefault("QT_QPA_PLATFORM", "offscreen")
    return environment


def _child_command(
    mode: str,
    *,
    warmups: int,
    iterations: int,
    image_size: tuple[int, int],
    widget_size: tuple[int, int],
) -> list[str]:
    return [
        sys.executable,
        "-m",
        "tooling.image_display_benchmark",
        "--child",
        "--mode",
        mode,
        "--warmups",
        str(warmups),
        "--iterations",
        str(iterations),
        "--image-width",
        str(image_size[0]),
        "--image-height",
        str(image_size[1]),
        "--widget-width",
        str(widget_size[0]),
        "--widget-height",
        str(widget_size[1]),
    ]


def run_mode_subprocess(
    mode: str,
    *,
    warmups: int = 1,
    iterations: int = 5,
    image_size: tuple[int, int] = DEFAULT_IMAGE_SIZE,
    widget_size: tuple[int, int] = DEFAULT_WIDGET_SIZE,
) -> dict:
    """1モードを独立 process で測る。"""
    completed = subprocess.run(
        _child_command(
            mode,
            warmups=warmups,
            iterations=iterations,
            image_size=image_size,
            widget_size=widget_size,
        ),
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=_subprocess_environment(),
    )
    return json.loads(completed.stdout)


def run_batch(
    *,
    warmups: int = 1,
    iterations: int = 5,
    image_size: tuple[int, int] = DEFAULT_IMAGE_SIZE,
    widget_size: tuple[int, int] = DEFAULT_WIDGET_SIZE,
) -> dict:
    """3モードをそれぞれ独立 process で実行する。"""
    return {
        "schema_version": 1,
        "benchmark": "image_display_preparation",
        "measurement_scope": MEASUREMENT_SCOPE,
        "excludes_qt_paint_compositor_latency": True,
        "environment": environment_metadata(image_size),
        "conditions": {
            "warmups": warmups,
            "measurement_iterations": iterations,
            "widget_width": widget_size[0],
            "widget_height": widget_size[1],
            "mode_process_isolated": True,
        },
        "results": [
            run_mode_subprocess(
                mode,
                warmups=warmups,
                iterations=iterations,
                image_size=image_size,
                widget_size=widget_size,
            )
            for mode in MODES
        ],
    }


def render_markdown(report: dict) -> str:
    """batch JSON の短い Markdown 要約を作る。"""
    lines = [
        "# Image display preparation benchmark",
        "",
        f"> {report['measurement_scope']}",
        "",
        "| Mode | Filter ms | Spread combine ms | RGBA convert ms | "
        "Other set_image ms | Total ms |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for result in report["results"]:
        stages = result["stages"]
        average = lambda name: stages[name]["average_ms"]
        lines.append(
            "| {mode} | {filter_ms:.3f} | {combine_ms:.3f} | {rgba_ms:.3f} | "
            "{other_ms:.3f} | {total_ms:.3f} |".format(
                mode=result["mode"],
                filter_ms=average("filter_ms"),
                combine_ms=average("combine_spread_ms"),
                rgba_ms=average("rgba_convert_ms"),
                other_ms=average("non_rgba_set_image_preparation_ms"),
                total_ms=average("display_preparation_total_ms"),
            )
        )
    lines.extend(
        [
            "",
            "Qt paint event と compositor の frame latency は計測対象外です。",
        ]
    )
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--mode", choices=MODES)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--image-width", type=int, default=DEFAULT_IMAGE_SIZE[0])
    parser.add_argument("--image-height", type=int, default=DEFAULT_IMAGE_SIZE[1])
    parser.add_argument("--widget-width", type=int, default=DEFAULT_WIDGET_SIZE[0])
    parser.add_argument("--widget-height", type=int, default=DEFAULT_WIDGET_SIZE[1])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    dimensions = (
        args.image_width,
        args.image_height,
        args.widget_width,
        args.widget_height,
    )
    if args.warmups < 0 or args.iterations < 1 or any(value < 1 for value in dimensions):
        raise SystemExit("dimensions/iterations must be positive and warmups non-negative")
    image_size = (args.image_width, args.image_height)
    widget_size = (args.widget_width, args.widget_height)
    if args.child:
        if args.mode is None:
            raise SystemExit("--child requires --mode")
        report = run_mode(
            args.mode,
            warmups=args.warmups,
            iterations=args.iterations,
            image_size=image_size,
            widget_size=widget_size,
        )
    elif args.mode:
        report = run_mode(
            args.mode,
            warmups=args.warmups,
            iterations=args.iterations,
            image_size=image_size,
            widget_size=widget_size,
        )
    else:
        report = run_batch(
            warmups=args.warmups,
            iterations=args.iterations,
            image_size=image_size,
            widget_size=widget_size,
        )
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    if args.markdown_output:
        if args.child or args.mode:
            raise SystemExit("--markdown-output is available only in parent batch mode")
        args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
