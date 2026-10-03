"""対象: ez_co.ui.docks.image_slide_sidebar"""
from ez_co.ui.docks.image_slide_sidebar import ThumbnailWidget


def test_thumbnail_text_uses_language_keys(qapp, monkeypatch):
    """待ちと失敗の表示が言語キー以外の文になり、読み込み失敗へ切り替わらない。"""
    monkeypatch.setattr(
        "ez_co.ui.docks.image_slide_sidebar.get_text",
        lambda key, **kwargs: key,
    )

    widget = ThumbnailWidget(0, 1, size=(80, 100))
    try:
        assert widget.image_label.text() == "ui.thumbnail_loading"
        widget.set_thumbnail(None)
        assert widget.image_label.text() == "ui.thumbnail_load_failed"
    finally:
        widget.close()
