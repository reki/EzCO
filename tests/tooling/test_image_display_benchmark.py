"""対象: tooling.image_display_benchmark"""
from __future__ import annotations

import threading

import pytest
from PIL import Image

from tooling.image_display_benchmark import (
    MODES,
    STAGE_NAMES,
    aggregate_stages,
    ensure_gui_main_thread,
    render_markdown,
    run_mode,
    run_mode_subprocess,
)


@pytest.mark.parametrize("mode", MODES)
def test_run_mode_measures_all_display_preparation_stages(qapp, mode):
    result = run_mode(
        mode,
        warmups=0,
        iterations=2,
        image_size=(32, 24),
        widget_size=(48, 36),
        app=qapp,
    )

    assert result["mode"] == mode
    assert result["conditions"]["measurement_iterations"] == 2
    assert result["conditions"]["gui_main_thread"] is True
    assert result["excludes_qt_paint_compositor_latency"] is True
    assert "compositor" in result["measurement_scope"]
    assert len(result["samples"]) == 2
    assert set(result["stages"]) == set(STAGE_NAMES)
    assert result["environment"]["image_width"] == 32
    assert result["environment"]["image_height"] == 24
    for sample in result["samples"]:
        assert set(sample) == set(STAGE_NAMES)
        assert all(value >= 0 for value in sample.values())
        assert sample["display_preparation_total_ms"] == pytest.approx(
            sample["filter_ms"]
            + sample["combine_spread_ms"]
            + sample["set_image_call_ms"]
        )
        assert sample["non_rgba_set_image_preparation_ms"] == pytest.approx(
            max(0.0, sample["set_image_call_ms"] - sample["rgba_convert_ms"])
        )

    if mode == "spread":
        assert all(sample["page_a_filter_ms"] >= 0 for sample in result["samples"])
        assert all(sample["page_b_filter_ms"] >= 0 for sample in result["samples"])
        assert all(
            sample["filter_ms"]
            == pytest.approx(
                sample["page_a_filter_ms"] + sample["page_b_filter_ms"]
            )
            for sample in result["samples"]
        )
    else:
        assert all(sample["page_b_filter_ms"] == 0 for sample in result["samples"])


def test_rgba_convert_is_measured_only_during_set_image_and_restored(
    qapp, monkeypatch
):
    original = Image.Image.convert
    converted_modes = []

    def convert_spy(source, mode=None, *args, **kwargs):
        converted_modes.append(mode)
        return original(source, mode, *args, **kwargs)

    monkeypatch.setattr(Image.Image, "convert", convert_spy)

    result = run_mode(
        "filter_off",
        warmups=0,
        iterations=1,
        image_size=(24, 18),
        widget_size=(40, 30),
        app=qapp,
    )

    assert converted_modes == ["RGBA"]
    assert result["samples"][0]["rgba_convert_ms"] >= 0
    assert Image.Image.convert is convert_spy


def test_aggregate_stages_returns_nonnegative_values():
    sample = {name: 1.5 for name in STAGE_NAMES}
    stages = aggregate_stages([sample, sample])

    for stage in stages.values():
        assert stage == {
            "average_ms": 1.5,
            "min_ms": 1.5,
            "max_ms": 1.5,
            "total_ms": 3.0,
        }


def test_gui_work_is_rejected_outside_qapplication_thread(qapp):
    errors = []

    def check_from_worker():
        try:
            ensure_gui_main_thread(qapp)
        except RuntimeError as exc:
            errors.append(str(exc))

    thread = threading.Thread(target=check_from_worker)
    thread.start()
    thread.join(timeout=2)

    assert not thread.is_alive()
    assert errors == ["display benchmark must run on the QApplication GUI main thread"]


def test_single_mode_runs_in_isolated_subprocess():
    result = run_mode_subprocess(
        "builtin_basic",
        warmups=0,
        iterations=1,
        image_size=(24, 18),
        widget_size=(40, 30),
    )

    assert result["mode"] == "builtin_basic"
    assert result["conditions"]["measurement_iterations"] == 1
    assert result["conditions"]["builtin_brightness"] == 10
    assert "rgba_convert_ms" in result["samples"][0]
    assert result["excludes_qt_paint_compositor_latency"] is True


def test_markdown_states_scope_and_stage_summary(qapp):
    mode_result = run_mode(
        "filter_off",
        warmups=0,
        iterations=1,
        image_size=(16, 12),
        widget_size=(32, 24),
        app=qapp,
    )
    report = {
        "measurement_scope": mode_result["measurement_scope"],
        "results": [mode_result],
    }

    text = render_markdown(report)

    assert "| filter_off |" in text
    assert "Qt paint event" in text
    assert "compositor" in text
