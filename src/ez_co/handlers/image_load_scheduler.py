"""画像読込taskの優先順位、重複排除、worker lifecycleを管理する。"""

from __future__ import annotations

import itertools
import logging
import queue
import threading
from dataclasses import dataclass
from typing import Callable, Optional

from ez_co.utils.language_manager import get_log_text

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ImageLoadTask:
    """ワーカーへ渡す画像読込の1件。"""
    file: str
    cache_key: str
    page_index: int
    session_id: int
    generation: int
    token: int


@dataclass
class _LoadState:
    """キャッシュキーに紐づく読込状態。"""
    state: str
    token: int
    session_id: int
    generation: int
    event: threading.Event


class ImageLoadScheduler:
    """優先queueとcache key単位のdecode所有権を一元管理する。"""

    def __init__(
        self,
        load_task: Callable[[ImageLoadTask], bool],
        is_session_active: Callable[[int], bool],
        *,
        worker_count: int = 3,
    ):
        """読込関数とセッション判定を受け取り、ワーカーを起動する。

        Args:
            load_task: タスクを処理し、成否を返す関数。
            is_session_active: セッションが有効か返す関数。
            worker_count: 起動するワーカー数。1 未満は 1 にする。
        """
        self._load_task = load_task
        self._is_session_active = is_session_active
        self._worker_count = max(1, int(worker_count))
        self._queue: queue.PriorityQueue = queue.PriorityQueue()
        self._sequence = itertools.count()
        self._token_sequence = itertools.count(1)
        self._lock = threading.RLock()
        self._states: dict[str, _LoadState] = {}
        self._generation = 0
        self._stale_discard_count = 0
        self._active_workers = 0
        self._shutdown = False
        self._workers = [
            threading.Thread(
                target=self._worker_loop,
                name=f"EzCoImageLoader-{index + 1}",
                daemon=True,
            )
            for index in range(self._worker_count)
        ]
        for worker in self._workers:
            worker.start()

    @property
    def generation(self) -> int:
        """現在の世代番号を返す。

        Returns:
            ロック下で読んだ世代番号。
        """
        with self._lock:
            return self._generation

    def advance_generation(self) -> int:
        """世代を進め、待機中のタスクを破棄する。

        Returns:
            進めたあとの世代番号。
        """
        with self._lock:
            self._generation += 1
            stale_states = []
            for cache_key, state in list(self._states.items()):
                if state.state == "queued":
                    stale_states.append(state)
                    self._states.pop(cache_key, None)
            while True:
                try:
                    _priority, _sequence, task = self._queue.get_nowait()
                except queue.Empty:
                    # キューが空なら抜き取りを終える
                    break
                else:
                    self._queue.task_done()
                    if task is not None:
                        self._stale_discard_count += 1
            generation = self._generation
        for state in stale_states:
            state.event.set()
        return generation

    def enqueue(
        self,
        *,
        file: str,
        cache_key: str,
        page_index: int,
        session_id: int,
        generation: int,
        priority: int,
    ) -> bool:
        """読込タスクを優先度付きキューへ積む。

        Args:
            file: 読み込むファイル。
            cache_key: キャッシュキー。
            page_index: ページ位置。
            session_id: 依頼時のセッション。
            generation: 依頼時の世代。
            priority: 小さいほど先に取り出す優先度。

        Returns:
            積めたら真。停止中、世代が違う、同じキーが実行中か同じ世代で待機中なら偽。
        """
        with self._lock:
            if self._shutdown:
                return False
            if generation != self._generation:
                return False
            existing = self._states.get(cache_key)
            if existing is not None:
                if existing.state in ("background_in_progress", "foreground_claimed"):
                    return False
                if existing.state == "queued" and existing.generation == generation:
                    return False
            token = self._next_token_unlocked()
            state = _LoadState(
                state="queued",
                token=token,
                session_id=session_id,
                generation=generation,
                event=existing.event if existing is not None else threading.Event(),
            )
            state.event.clear()
            self._states[cache_key] = state
            task = ImageLoadTask(
                file=str(file),
                cache_key=cache_key,
                page_index=int(page_index),
                session_id=session_id,
                generation=generation,
                token=token,
            )
            self._queue.put((int(priority), next(self._sequence), task))
            return True

    def claim_foreground(
        self,
        cache_key: str,
        session_id: int,
    ) -> tuple[str, threading.Event, int]:
        """foregroundへ所有権を渡すか、実行中decodeの完了eventを返す。

        Args:
            cache_key: 対象のキャッシュキー。
            session_id: 操作しているセッション。

        Returns:
            状態、完了イベント、トークン。状態は所有するとき owner、同じセッションの実行中を待つとき wait。
        """
        with self._lock:
            existing = self._states.get(cache_key)
            if existing is not None and existing.session_id == session_id:
                if existing.state in ("background_in_progress", "foreground_claimed"):
                    return "wait", existing.event, existing.token
                if existing.state == "queued":
                    token = self._next_token_unlocked()
                    existing.state = "foreground_claimed"
                    existing.token = token
                    existing.generation = self._generation
                    return "owner", existing.event, token
            token = self._next_token_unlocked()
            event = threading.Event()
            self._states[cache_key] = _LoadState(
                state="foreground_claimed",
                token=token,
                session_id=session_id,
                generation=self._generation,
                event=event,
            )
            return "owner", event, token

    def finish_foreground(self, cache_key: str, token: int) -> None:
        """foreground の所有を外し、待ちを解除する。

        Args:
            cache_key: 対象のキャッシュキー。
            token: 所有時に受け取ったトークン。
        """
        with self._lock:
            state = self._states.get(cache_key)
            if (
                state is None
                or state.state != "foreground_claimed"
                or state.token != token
            ):
                return
            self._states.pop(cache_key, None)
            state.event.set()

    def cancel_pending(self) -> None:
        """session変更時に待機者を解放し、未開始taskを無効化する。"""
        with self._lock:
            self._generation += 1
            states = list(self._states.values())
            self._states.clear()
        for state in states:
            state.event.set()
        while True:
            try:
                _priority, _sequence, task = self._queue.get_nowait()
            except queue.Empty:
                # キューが空なら抜き取りを終える
                break
            else:
                self._queue.task_done()
                if task is not None:
                    with self._lock:
                        self._stale_discard_count += 1

    def snapshot(self) -> dict[str, int]:
        """キューとワーカーの本数を返す。

        Returns:
            キュー長、実行中ワーカー、破棄数、追跡キー数、世代、ワーカー数、生存ワーカー数。
        """
        with self._lock:
            return {
                "queue_size": self._queue.qsize(),
                "active_workers": self._active_workers,
                "stale_discard_count": self._stale_discard_count,
                "tracked_keys": len(self._states),
                "generation": self._generation,
                "worker_count": self._worker_count,
                "alive_workers": sum(worker.is_alive() for worker in self._workers),
            }

    def shutdown(self, *, wait: bool = False) -> None:
        """スケジューラを止める。

        Args:
            wait: 真なら現在スレッド以外のワーカーの終了を待つ。
        """
        with self._lock:
            first_shutdown = not self._shutdown
            if first_shutdown:
                self._shutdown = True
        if first_shutdown:
            self.cancel_pending()
            for _ in self._workers:
                self._queue.put((float("inf"), next(self._sequence), None))
        if wait:
            for worker in self._workers:
                if worker is not threading.current_thread():
                    worker.join()

    def _next_token_unlocked(self) -> int:
        """次の所有権トークンを返す。

        Returns:
            新しいトークン。
        """
        return next(self._token_sequence)

    def _worker_loop(self) -> None:
        """キューからタスクを取り、バックグラウンドで読込を実行する。"""
        while True:
            priority, _sequence, task = self._queue.get()
            try:
                if task is None:
                    return
                state = self._claim_background(task)
                if state is None:
                    continue
                success = False
                with self._lock:
                    self._active_workers += 1
                try:
                    success = bool(self._load_task(task))
                except BaseException as exc:
                    # 読込の失敗はログして、失敗のまま後始末へ進む
                    logger.error(get_log_text("file_handler_worker_error", error=exc))
                finally:
                    with self._lock:
                        self._active_workers -= 1
                    self._finish_background(task, state, success)
            finally:
                self._queue.task_done()

    def _claim_background(self, task: ImageLoadTask) -> Optional[_LoadState]:
        """待機中のタスクをバックグラウンド実行中にする。

        Args:
            task: 取り出されたタスク。

        Returns:
            所有できた状態。停止、世代違い、セッション無効などで破棄したときは None。
        """
        with self._lock:
            state = self._states.get(task.cache_key)
            stale = (
                self._shutdown
                or state is None
                or state.state != "queued"
                or state.token != task.token
                or state.generation != task.generation
                or task.generation != self._generation
                or not self._is_session_active(task.session_id)
            )
            if stale:
                self._stale_discard_count += 1
                if state is not None and state.token == task.token:
                    self._states.pop(task.cache_key, None)
                    state.event.set()
                return None
            state.state = "background_in_progress"
            return state

    def _finish_background(
        self,
        task: ImageLoadTask,
        claimed_state: _LoadState,
        success: bool,
    ) -> None:
        """バックグラウンド読込の完了待ちを解除する。

        Args:
            task: 完了したタスク。
            claimed_state: 開始時に所有した状態。
            success: 読込の成否。待機の解除には使わない。
        """
        del success  # cacheの有無を結果の正とし、状態は待機解除にだけ使う。
        with self._lock:
            current = self._states.get(task.cache_key)
            if current is claimed_state:
                self._states.pop(task.cache_key, None)
            claimed_state.event.set()
