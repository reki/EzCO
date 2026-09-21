"""対象: ez_co.handlers.image_load_scheduler"""

import threading
import time

import pytest

from ez_co.handlers.image_load_scheduler import ImageLoadScheduler


def _wait_until(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return False


@pytest.mark.parametrize("worker_count", [1, 3, 6, 8])
def test_configured_worker_count_starts_and_shuts_down(worker_count):
    scheduler = ImageLoadScheduler(
        lambda _task: True,
        lambda _session: True,
        worker_count=worker_count,
    )
    assert scheduler.snapshot()["worker_count"] == worker_count
    assert scheduler.snapshot()["alive_workers"] == worker_count
    scheduler.shutdown(wait=True)
    assert scheduler.snapshot()["alive_workers"] == 0


def test_three_workers_can_start_in_parallel():
    started = []
    lock = threading.Lock()
    release = threading.Event()

    def load(task):
        with lock:
            started.append(task.cache_key)
        release.wait(2)
        return True

    scheduler = ImageLoadScheduler(load, lambda _session: True, worker_count=3)
    generation = scheduler.advance_generation()
    try:
        for index in range(3):
            scheduler.enqueue(
                file=str(index),
                cache_key=str(index),
                page_index=index,
                session_id=1,
                generation=generation,
                priority=index,
            )
        assert _wait_until(lambda: len(started) == 3)
        assert scheduler.snapshot()["active_workers"] == 3
    finally:
        release.set()
        scheduler.shutdown(wait=True)


def test_priority_queue_uses_priority_then_stable_sequence():
    started = []
    first_started = threading.Event()
    release_first = threading.Event()

    def load(task):
        started.append(task.cache_key)
        if task.cache_key == "blocker":
            first_started.set()
            release_first.wait(2)
        return True

    scheduler = ImageLoadScheduler(load, lambda _session: True, worker_count=1)
    generation = scheduler.advance_generation()
    try:
        scheduler.enqueue(
            file="blocker",
            cache_key="blocker",
            page_index=0,
            session_id=1,
            generation=generation,
            priority=0,
        )
        assert first_started.wait(2)
        for key, priority in (("later-a", 10), ("near-a", 1), ("near-b", 1)):
            scheduler.enqueue(
                file=key,
                cache_key=key,
                page_index=1,
                session_id=1,
                generation=generation,
                priority=priority,
            )
        release_first.set()
        assert _wait_until(lambda: len(started) == 4)
        assert started == ["blocker", "near-a", "near-b", "later-a"]
    finally:
        release_first.set()
        scheduler.shutdown(wait=True)


def test_new_generation_discards_unstarted_old_tasks():
    started = []
    blocker_started = threading.Event()
    release = threading.Event()

    def load(task):
        started.append(task.cache_key)
        if task.cache_key == "blocker":
            blocker_started.set()
            release.wait(2)
        return True

    scheduler = ImageLoadScheduler(load, lambda _session: True, worker_count=1)
    old_generation = scheduler.advance_generation()
    try:
        scheduler.enqueue(
            file="blocker",
            cache_key="blocker",
            page_index=0,
            session_id=1,
            generation=old_generation,
            priority=0,
        )
        assert blocker_started.wait(2)
        scheduler.enqueue(
            file="old",
            cache_key="old",
            page_index=1,
            session_id=1,
            generation=old_generation,
            priority=1,
        )
        new_generation = scheduler.advance_generation()
        scheduler.enqueue(
            file="new",
            cache_key="new",
            page_index=20,
            session_id=1,
            generation=new_generation,
            priority=1,
        )
        release.set()
        assert _wait_until(lambda: "new" in started)
        assert "old" not in started
        assert scheduler.snapshot()["stale_discard_count"] >= 1
    finally:
        release.set()
        scheduler.shutdown(wait=True)


def test_foreground_claim_invalidates_queued_prefetch():
    started = []
    blocker_started = threading.Event()
    release = threading.Event()

    def load(task):
        started.append(task.cache_key)
        blocker_started.set()
        release.wait(2)
        return True

    scheduler = ImageLoadScheduler(load, lambda _session: True, worker_count=1)
    generation = scheduler.advance_generation()
    try:
        scheduler.enqueue(
            file="blocker",
            cache_key="blocker",
            page_index=0,
            session_id=1,
            generation=generation,
            priority=0,
        )
        assert blocker_started.wait(2)
        scheduler.enqueue(
            file="page",
            cache_key="page",
            page_index=1,
            session_id=1,
            generation=generation,
            priority=1,
        )
        claim, _event, token = scheduler.claim_foreground("page", 1)
        assert claim == "owner"
        scheduler.finish_foreground("page", token)
        release.set()
        assert _wait_until(lambda: scheduler.snapshot()["queue_size"] == 0)
        assert started == ["blocker"]
    finally:
        release.set()
        scheduler.shutdown(wait=True)


def test_foreground_waits_for_in_progress_decode():
    started = threading.Event()
    release = threading.Event()
    calls = []

    def load(task):
        calls.append(task.cache_key)
        started.set()
        release.wait(2)
        return True

    scheduler = ImageLoadScheduler(load, lambda _session: True, worker_count=1)
    generation = scheduler.advance_generation()
    try:
        scheduler.enqueue(
            file="page",
            cache_key="page",
            page_index=1,
            session_id=1,
            generation=generation,
            priority=1,
        )
        assert started.wait(2)
        claim, event, _token = scheduler.claim_foreground("page", 1)
        assert claim == "wait"
        assert not event.is_set()
        release.set()
        assert event.wait(2)
        assert calls == ["page"]
    finally:
        release.set()
        scheduler.shutdown(wait=True)


def test_worker_continues_after_task_exception():
    processed = []

    def load(task):
        if task.cache_key == "broken":
            raise SystemExit("boom")
        processed.append(task.cache_key)
        return True

    scheduler = ImageLoadScheduler(load, lambda _session: True, worker_count=1)
    generation = scheduler.advance_generation()
    try:
        for key in ("broken", "healthy"):
            scheduler.enqueue(
                file=key,
                cache_key=key,
                page_index=0,
                session_id=1,
                generation=generation,
                priority=0,
            )
        assert _wait_until(lambda: processed == ["healthy"])
    finally:
        scheduler.shutdown(wait=True)


def test_inactive_session_task_is_discarded():
    processed = []
    active_session = {"value": 1}
    scheduler = ImageLoadScheduler(
        lambda task: processed.append(task.cache_key) or True,
        lambda session: session == active_session["value"],
        worker_count=1,
    )
    generation = scheduler.advance_generation()
    active_session["value"] = 2
    try:
        scheduler.enqueue(
            file="old",
            cache_key="old",
            page_index=0,
            session_id=1,
            generation=generation,
            priority=0,
        )
        assert _wait_until(lambda: scheduler.snapshot()["queue_size"] == 0)
        assert processed == []
    finally:
        scheduler.shutdown(wait=True)


def test_old_foreground_owner_cannot_finish_new_session_owner():
    scheduler = ImageLoadScheduler(lambda _task: True, lambda _session: True, worker_count=1)
    try:
        claim, _event, old_token = scheduler.claim_foreground("page", 1)
        assert claim == "owner"
        scheduler.cancel_pending()

        claim, new_event, new_token = scheduler.claim_foreground("page", 2)
        assert claim == "owner"
        scheduler.finish_foreground("page", old_token)

        claim, same_event, token = scheduler.claim_foreground("page", 2)
        assert claim == "wait"
        assert same_event is new_event
        assert token == new_token

        scheduler.finish_foreground("page", new_token)
        assert new_event.is_set()
    finally:
        scheduler.shutdown(wait=True)


def test_shutdown_waits_for_all_workers():
    scheduler = ImageLoadScheduler(lambda _task: True, lambda _session: True, worker_count=3)
    scheduler.shutdown(wait=True)
    snapshot = scheduler.snapshot()
    assert snapshot["worker_count"] == 3
    assert snapshot["alive_workers"] == 0


def test_waiting_shutdown_joins_after_prior_non_waiting_shutdown():
    started = threading.Event()
    release = threading.Event()

    def load(_task):
        started.set()
        release.wait(2)
        return True

    scheduler = ImageLoadScheduler(load, lambda _session: True, worker_count=1)
    generation = scheduler.advance_generation()
    scheduler.enqueue(
        file="page",
        cache_key="page",
        page_index=0,
        session_id=1,
        generation=generation,
        priority=0,
    )
    assert started.wait(2)

    scheduler.shutdown(wait=False)
    assert scheduler.snapshot()["alive_workers"] == 1
    release.set()
    scheduler.shutdown(wait=True)
    assert scheduler.snapshot()["alive_workers"] == 0


def test_generation_changes_compact_unstarted_queue():
    blocker_started = threading.Event()
    release = threading.Event()

    def load(task):
        if task.cache_key == "blocker":
            blocker_started.set()
            release.wait(2)
        return True

    scheduler = ImageLoadScheduler(load, lambda _session: True, worker_count=1)
    generation = scheduler.advance_generation()
    scheduler.enqueue(
        file="blocker",
        cache_key="blocker",
        page_index=0,
        session_id=1,
        generation=generation,
        priority=0,
    )
    assert blocker_started.wait(2)
    try:
        for generation_index in range(100):
            generation = scheduler.advance_generation()
            for index in range(10):
                scheduler.enqueue(
                    file=f"{generation_index}-{index}",
                    cache_key=f"{generation_index}-{index}",
                    page_index=index,
                    session_id=1,
                    generation=generation,
                    priority=index,
                )
            assert scheduler.snapshot()["queue_size"] <= 10
        assert scheduler.snapshot()["stale_discard_count"] >= 990
    finally:
        release.set()
        scheduler.shutdown(wait=True)
