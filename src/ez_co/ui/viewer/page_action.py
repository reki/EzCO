"""タブ指定のページ操作が、どのタブを触り、ショートカット対象を変えるか。"""


def resolve_page_target(shortcut_id, requested_id, open_ids):
    """ページ操作の対象と、ショートカット対象を変えるかを返す。

    Args:
        shortcut_id: いまのショートカット対象。
        requested_id: 呼び出しが渡したタブ。無ければ None。
        open_ids: 開いているタブ id。

    Returns:
        操作する id と、ショートカット対象を変えるか。
        指定が無ければショートカット対象を操作し、対象は変えない。
        開いている id ならそのタブを操作し、対象は変えない。
        開いていない id は操作せず、対象も変えない。
    """
    if requested_id is None:
        return shortcut_id, False
    if requested_id in open_ids:
        return requested_id, False
    return None, False
