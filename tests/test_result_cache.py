"""Tests for the ResultCache module."""

from __future__ import annotations

import threading
import time
from pathlib import Path

from code_chain.core.result_cache import ResultCache


def test_save_creates_file(tmp_path: Path):
    cache = ResultCache(tmp_path)
    filepath = cache.save("query", "test_key", "Test content")

    assert filepath is not None
    assert filepath.exists()
    assert filepath.parent.name == "results"
    assert filepath.read_text(encoding="utf-8") == "Test content"
    assert "query" in filepath.name
    assert "test_key" in filepath.name


def test_save_disabled_returns_none(tmp_path: Path):
    cache = ResultCache(tmp_path, enabled=False)
    filepath = cache.save("query", "test_key", "Test content")

    assert filepath is None
    results_dir = tmp_path / ".code_chain" / "results"
    assert not results_dir.exists()


def test_eviction_removes_oldest(tmp_path: Path):
    cache = ResultCache(tmp_path, max_entries=3)

    # Save 5 items with slight delays so mtimes differ
    for i in range(5):
        cache.save("query", f"key_{i}", f"content {i}")
        time.sleep(0.01)

    results = cache.list_results()
    assert len(results) == 3
    # The newest 3 should be kept: key_2, key_3, key_4
    # Because they are newest, list_results returns them in descending order
    assert "key_4" in results[0].name
    assert "key_3" in results[1].name
    assert "key_2" in results[2].name


def test_list_results_newest_first(tmp_path: Path):
    cache = ResultCache(tmp_path)

    cache.save("task1", "key1", "c1")
    time.sleep(0.01)
    cache.save("task2", "key2", "c2")

    results = cache.list_results()
    assert len(results) == 2
    assert "task2" in results[0].name
    assert "task1" in results[1].name


def test_clear_removes_all(tmp_path: Path):
    cache = ResultCache(tmp_path)
    cache.save("t1", "k1", "c1")
    cache.save("t2", "k2", "c2")

    assert len(cache.list_results()) == 2
    cache.clear()
    assert len(cache.list_results()) == 0


def test_key_sanitization(tmp_path: Path):
    cache = ResultCache(tmp_path)
    filepath = cache.save("impact", "Dirty/Key@123!", "content")

    assert filepath is not None
    assert "dirty_key_123_" in filepath.name


def test_thread_safety(tmp_path: Path):
    cache = ResultCache(tmp_path, max_entries=10)

    def worker(idx: int):
        cache.save("query", f"key_{idx}", f"content {idx}")

    threads = []
    for i in range(20):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    assert len(cache.list_results()) == 10
