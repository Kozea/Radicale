import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from radicale import auth, config


NS = 10**9


class _Clock:
    def __init__(self):
        self.ns = 0
        self.wall_ns = 1_700_000_000 * NS
        self.sleeps = []

    def monotonic_ns(self):
        return self.ns

    def time_ns(self):
        return self.wall_ns

    def advance(self, seconds):
        """Advance only the monotonic clock."""
        self.ns += seconds * NS

    def advance_wall(self, seconds):
        """Adjust only the wall clock."""
        self.wall_ns += seconds * NS


@pytest.fixture
def clock(monkeypatch):
    clock = _Clock()

    monkeypatch.setattr(auth, "time", SimpleNamespace(
        monotonic_ns=clock.monotonic_ns,
        time_ns=clock.time_ns,
        sleep=clock.sleeps.append,
    ))
    return clock


def _cache(max_items=3, ttl=10):
    return auth.AuthCache("test", max_items, ttl)


def test_empty_cache(clock):
    cache = _cache()

    assert cache.get("missing") is None
    assert cache.clear("missing") is False
    cache.cleanup(clock.ns)


def test_insert_preserves_identity_and_groups(clock):
    cache = _cache()
    groups = {"readers", "editors"}

    cache.set_or_refresh("digest", "mapped-user", groups)

    assert cache.get("digest") == (
        10 * NS, "mapped-user", groups)


@pytest.mark.parametrize("offset_ns, present", [
    (10 * NS - 1, True),
    (10 * NS, False),
    (10 * NS + 1, False),
])
def test_expiry_boundary(clock, offset_ns, present):
    cache = _cache()
    cache.set_or_refresh("digest", "alice")

    clock.ns = offset_ns

    assert (cache.get("digest") is not None) is present


def test_lookup_does_not_extend_expiry(clock):
    cache = _cache()
    cache.set_or_refresh("digest", "alice")

    clock.advance(6)
    assert cache.get("digest") is not None

    clock.advance(4)
    assert cache.get("digest") is None


def test_lookup_does_not_change_eviction_order(clock):
    cache = _cache(max_items=2)
    cache.set_or_refresh("a", "alice")
    cache.set_or_refresh("b", "bob")

    assert cache.get("a") is not None
    cache.set_or_refresh("c", "carol")

    assert cache.get("a") is None
    assert cache.get("b") is not None
    assert cache.get("c") is not None


def test_refresh_replaces_payload_and_extends_expiry(clock):
    cache = _cache()
    cache.set_or_refresh("digest", "old-user", {"old-group"})

    clock.advance(3)
    cache.set_or_refresh("digest", "new-user", {"new-group"})

    assert cache.get("digest") == (
        13 * NS, "new-user", {"new-group"})

    clock.advance(7)
    assert cache.get("digest") is not None

    clock.advance(3)
    assert cache.get("digest") is None


def test_refresh_moves_entry_to_end_without_extra_eviction(clock):
    cache = _cache(max_items=2)
    cache.set_or_refresh("a", "alice")
    cache.set_or_refresh("b", "bob")

    clock.advance(1)
    cache.set_or_refresh("a", "alice")

    assert cache.get("a") is not None
    assert cache.get("b") is not None

    cache.set_or_refresh("c", "carol")

    assert cache.get("a") is not None
    assert cache.get("b") is None
    assert cache.get("c") is not None


def test_expiration_order_after_refresh(clock):
    cache = _cache()
    cache.set_or_refresh("a", "alice")

    clock.advance(1)
    cache.set_or_refresh("b", "bob")

    clock.advance(1)
    cache.set_or_refresh("a", "alice")

    clock.advance(9)  # b expires at 11; refreshed a expires at 12.
    cache.cleanup(clock.ns)

    assert cache.get("b") is None
    assert cache.get("a") is not None


def test_concurrent_insertions_expire_in_lock_acquisition_order(clock, monkeypatch):
    cache = _cache()
    writer_waiting = threading.Event()
    release_writer = threading.Event()
    main_thread = threading.current_thread()
    lock = cache._lock

    class DelayFirstWriter:
        def __enter__(self):
            if threading.current_thread() is not main_thread and not writer_waiting.is_set():
                writer_waiting.set()
                if not release_writer.wait(timeout=5):
                    raise TimeoutError("First cache writer was not released")
            return lock.__enter__()

        def __exit__(self, *exc_info):
            return lock.__exit__(*exc_info)

    monkeypatch.setattr(cache, "_lock", DelayFirstWriter())
    with ThreadPoolExecutor(max_workers=1) as executor:
        first = executor.submit(cache.set_or_refresh, "first", "alice")
        try:
            assert writer_waiting.wait(timeout=5)
            clock.advance(1)
            cache.set_or_refresh("second", "bob")
            clock.advance(1)
        finally:
            release_writer.set()
        first.result(timeout=5)

    clock.advance(9)
    assert cache.get("second") is None
    assert cache.get("first") == (12 * NS, "alice", None)


def test_insertion_removes_all_expired_entries(clock):
    cache = _cache(max_items=3)
    cache.set_or_refresh("expired-a", "alice")
    cache.set_or_refresh("expired-b", "bob")

    clock.advance(5)
    cache.set_or_refresh("live", "carol")

    clock.advance(5)
    cache.set_or_refresh("new", "dave")

    # Inspect storage before get() can perform additional cleanup.
    assert list(cache._items) == ["live", "new"]


def test_lookup_removes_expired_prefix(clock):
    cache = _cache()
    cache.set_or_refresh("expired-a", "alice")
    cache.set_or_refresh("expired-b", "bob")

    clock.advance(5)
    cache.set_or_refresh("live", "carol")

    clock.advance(5)
    assert cache.get("live") is not None

    assert list(cache._items) == ["live"]


def test_capacity_remains_bounded(clock):
    cache = _cache(max_items=3)

    for index in range(10):
        cache.set_or_refresh(str(index), "alice")
        assert len(cache._items) <= 3

    assert list(cache._items) == ["7", "8", "9"]


def test_clear_reports_removal_and_preserves_other_entries(clock):
    cache = _cache()
    cache.set_or_refresh("a", "alice")
    cache.set_or_refresh("b", "bob")

    assert cache.clear("a") is True
    assert cache.clear("a") is False
    assert cache.get("a") is None
    assert cache.get("b") is not None


@pytest.mark.parametrize("max_items, ttl", [
    (0, 10),
    (3, 0),
    (0, 0),
])
def test_disabled_cache_never_retains_entries(clock, max_items, ttl):
    cache = _cache(max_items=max_items, ttl=ttl)

    cache.set_or_refresh("digest", "alice")

    # Check before get() could remove an expired entry.
    assert len(cache._items) == 0
    assert cache.get("digest") is None


def test_cache_instances_are_independent(clock):
    successful = _cache(max_items=1, ttl=10)
    failed = _cache(max_items=2, ttl=20)

    successful.set_or_refresh("same-key", "successful-user")
    failed.set_or_refresh("same-key", "failed-user")
    successful.clear("same-key")

    assert successful.get("same-key") is None
    assert failed.get("same-key") == (
        20 * NS, "failed-user", None)


class _Backend(auth.BaseAuth):
    """Controlled backend: no external authentication dependencies."""

    def __init__(self, configuration):
        super().__init__(configuration)
        self.calls = []

    def _login_ext_with_groups(self, login, password, context):
        self.calls.append((login, password))
        if password == "correct":
            return "mapped-user", {"readers"}
        return "", set()


def _backend(success=(3, 10), failed=(3, 10), **auth_options):
    configuration = config.load()
    configuration.update({
        "auth": {
            "type": "htpasswd",
            "cache_logins": "True",
            "cache_successful_logins_max_count": str(success[0]),
            "cache_successful_logins_expiry": str(success[1]),
            "cache_failed_logins_max_count": str(failed[0]),
            "cache_failed_logins_expiry": str(failed[1]),
            **auth_options,
        },
    }, "test", privileged=True)
    return _Backend(configuration)


CACHE_SETTINGS = [
    (0, 0),
    (0, 10),
    (3, 0),
    (3, 10),
]


@pytest.mark.parametrize("success", CACHE_SETTINGS)
@pytest.mark.parametrize("failed", CACHE_SETTINGS)
def test_effective_cache_configuration(clock, success, failed):
    backend = _backend(success=success, failed=failed)
    context = auth.AuthContext()

    success_enabled = success[0] > 0 and success[1] > 0
    failed_enabled = failed[0] > 0 and failed[1] > 0

    assert backend._cache_logins == (
        success_enabled or failed_enabled)

    first = backend.login("alias", "correct", context)
    second = backend.login("alias", "correct", context)

    assert first[:2] == ("mapped-user", {"readers"})
    assert second[:2] == first[:2]
    assert backend.calls.count(("alias", "correct")) == (
        1 if success_enabled else 2)

    assert backend.login("alias", "wrong", context)[0] == ""
    assert backend.login("alias", "wrong", context)[0] == ""
    assert backend.calls.count(("alias", "wrong")) == (
        1 if failed_enabled else 2)


def test_cache_capacity_defaults():
    configuration = config.load()
    configuration.update(
        {"auth": {"type": "htpasswd", "cache_logins": "True"}}, "test")
    backend = _Backend(configuration)

    assert backend._cache_successful._max_item_count == 1000
    assert backend._cache_failed._max_item_count == 1000


@pytest.mark.parametrize("option", [
    "cache_successful_logins_max_count",
    "cache_failed_logins_max_count",
])
def test_negative_cache_capacity_is_rejected(option):
    with pytest.raises(RuntimeError, match=option):
        _backend(**{option: "-1"})


@pytest.mark.parametrize("path, credentials, expected_type", [
    ("success-hit", ("current", "correct"), "htpasswd/cached"),
    ("failed-hit", ("current", "wrong"), "htpasswd/cached"),
    ("miss", ("unseen", "correct"), "htpasswd"),
    ("empty", ("@example.org", "correct"), "htpasswd"),
])
def test_login_prunes_both_caches(clock, path, credentials, expected_type):
    backend = _backend(strip_domain="True")
    context = auth.AuthContext()
    backend.login("older", "correct", context)
    backend.login("older", "wrong", context)
    old_success = next(iter(backend._cache_successful._items))
    old_failure = next(iter(backend._cache_failed._items))

    clock.advance(5)
    backend.login("current", "correct", context)
    backend.login("current", "wrong", context)
    live_success = next(reversed(backend._cache_successful._items))
    live_failure = next(reversed(backend._cache_failed._items))
    previous_calls = list(backend.calls)

    clock.advance(5)
    result, _, auth_type = backend.login(*credentials, context)

    expected_result = "mapped-user" if path in ("success-hit", "miss") else ""
    assert (result, auth_type) == (expected_result, expected_type)
    assert backend.calls == previous_calls + ([credentials] if path == "miss" else [])
    assert old_success not in backend._cache_successful._items
    assert old_failure not in backend._cache_failed._items
    assert live_success in backend._cache_successful._items
    assert live_failure in backend._cache_failed._items


def test_cached_groups_are_isolated_from_callers(clock):
    backend = _backend()
    context = auth.AuthContext()

    _, initial_groups, _ = backend.login("alias", "correct", context)
    initial_groups.add("added-after-verification")
    _, hit_groups, _ = backend.login("alias", "correct", context)
    assert hit_groups == {"readers"}

    hit_groups.clear()
    assert backend.login("alias", "correct", context) == (
        "mapped-user", {"readers"}, "htpasswd/cached")
    assert backend.calls == [("alias", "correct")]


def test_expiry_revalidates_identity_and_groups(clock):
    backend = _backend()
    context = auth.AuthContext()

    assert backend.login("alias", "correct", context)[:2] == (
        "mapped-user", {"readers"})

    def changed_backend(login, password, context):
        backend.calls.append((login, password))
        return "replacement-user", {"editors"}

    backend._login_ext_with_groups = changed_backend

    clock.advance(9)
    assert backend.login("alias", "correct", context)[:2] == (
        "mapped-user", {"readers"})
    assert len(backend.calls) == 1

    clock.advance(1)
    assert backend.login("alias", "correct", context)[:2] == (
        "replacement-user", {"editors"})
    assert len(backend.calls) == 2


def test_failed_cache_expires_and_allows_new_verification(clock):
    backend = _backend()
    context = auth.AuthContext()

    assert backend.login("alias", "wrong", context)[0] == ""

    def now_valid(login, password, context):
        backend.calls.append((login, password))
        return "mapped-user", {"readers"}

    backend._login_ext_with_groups = now_valid

    clock.advance(9)
    assert backend.login("alias", "wrong", context)[0] == ""
    assert len(backend.calls) == 1

    clock.advance(1)
    assert backend.login("alias", "wrong", context)[0] == "mapped-user"
    assert len(backend.calls) == 2


def test_failure_timing_uses_monotonic_elapsed_time(clock):
    # Isolate the helper from configuration and cache behavior.
    backend = object.__new__(auth.BaseAuth)
    backend._lock = threading.Lock()
    backend._failed_auth_delay = 0.25

    started_ns = clock.ns
    clock.ns += NS // 10  # 100 ms elapsed.

    backend._sleep_for_constant_exec_time(started_ns)

    assert backend._failed_auth_delay == pytest.approx(0.25)
    assert clock.sleeps == pytest.approx([0.15])


def test_cached_failure_does_not_pass_through_failure_padding(clock):
    backend = _backend()
    context = auth.AuthContext()
    padding_calls = []

    backend._sleep_for_constant_exec_time = padding_calls.append

    assert backend.login("alias", "wrong", context)[0] == ""
    assert backend.login("alias", "wrong", context)[0] == ""
    assert backend.login("alias", "wrong", context)[0] == ""

    assert len(backend.calls) == 1
    assert len(padding_calls) == 1

@pytest.mark.parametrize("wall_adjustment", [-3600, 3600])
def test_failure_timing_uses_monotonic_elapsed_time(
        clock, wall_adjustment):
    backend = object.__new__(auth.BaseAuth)
    backend._lock = threading.Lock()
    backend._failed_auth_delay = 0.25

    started_ns = clock.monotonic_ns()
    clock.ns += NS // 10  # 100 ms of actual elapsed time.
    clock.advance_wall(wall_adjustment)

    backend._sleep_for_constant_exec_time(started_ns)

    assert backend._failed_auth_delay == pytest.approx(0.25)
    assert clock.sleeps == pytest.approx([0.15])


@pytest.mark.parametrize("password, expected_identity", [
    ("correct", ("mapped-user", {"readers"})),
    ("wrong", ("", set())),
])
@pytest.mark.parametrize("wall_adjustment", [-3600, 3600])
def test_cache_ttl_starts_after_backend_verification(
        clock, monkeypatch, password, expected_identity,
        wall_adjustment):
    ttl = 10
    verification_seconds = 7
    backend = _backend(success=(3, ttl), failed=(3, ttl))
    context = auth.AuthContext()
    completions = []

    def slow_verification(login_name, supplied_password, context):
        backend.calls.append((login_name, supplied_password))
        clock.advance(verification_seconds)
        clock.advance_wall(wall_adjustment)
        completions.append(clock.monotonic_ns())

        if supplied_password == "correct":
            return "mapped-user", {"readers"}
        return "", set()

    monkeypatch.setattr(
        backend, "_login_ext_with_groups", slow_verification)

    first = backend.login("alias", password, context)
    assert first[:2] == expected_identity
    assert len(backend.calls) == 1

    cache = (
        backend._cache_successful
        if password == "correct"
        else backend._cache_failed
    )
    assert len(cache._items) == 1
    key = next(iter(cache._items))
    entry = cache.get(key)

    assert entry is not None
    assert entry[0] == completions[0] + ttl * NS

    # Nine seconds after completion: still cached.
    # A TTL measured before the seven-second verification would
    # already have expired.
    clock.advance(ttl - 1)
    second = backend.login("alias", password, context)

    assert second[:2] == expected_identity
    assert len(backend.calls) == 1

    # Exactly ten seconds after completion: verify again.
    clock.advance(1)
    third = backend.login("alias", password, context)

    assert third[:2] == expected_identity
    assert len(backend.calls) == 2

    refreshed_entry = cache.get(key)
    assert refreshed_entry is not None
    assert refreshed_entry[0] == completions[1] + ttl * NS


@pytest.mark.parametrize("wall_adjustment", [-3600, 3600])
def test_login_failure_timing_ignores_wall_clock_changes(
        clock, monkeypatch, wall_adjustment):
    backend = _backend()
    backend._failed_auth_delay = 0.25
    context = auth.AuthContext()

    def failed_verification(login_name, password, context):
        backend.calls.append((login_name, password))
        clock.ns += NS // 10  # 100 ms backend execution.
        clock.advance_wall(wall_adjustment)
        return "", set()

    monkeypatch.setattr(
        backend, "_login_ext_with_groups", failed_verification)

    result = backend.login("alias", "wrong", context)

    assert result[:2] == ("", set())
    assert backend.calls == [("alias", "wrong")]
    assert backend._failed_auth_delay == pytest.approx(0.25)
    assert clock.sleeps == pytest.approx([0.15])


def test_distinct_successful_credentials_for_same_login_coexist(
        clock, monkeypatch):
    backend = _backend(success=(2, 60))
    context = auth.AuthContext()
    credentials = {
        "first-password": {"readers"},
        "second-password": {"readers", "editors"},
    }

    def verification(login_name, password, context):
        backend.calls.append((login_name, password))
        if password not in credentials:
            return "", set()
        return "mapped-user", set(credentials[password])

    monkeypatch.setattr(
        backend, "_login_ext_with_groups", verification)

    for password in credentials:
        result = backend.login("alias", password, context)
        assert result[:2] == (
            "mapped-user", credentials[password])

    assert backend.calls == [
        ("alias", "first-password"),
        ("alias", "second-password"),
    ]

    # Both entries must remain usable without another verification.
    for password in credentials:
        result = backend.login("alias", password, context)
        assert result[:2] == (
            "mapped-user", credentials[password])

    assert len(backend.calls) == 2
    assert len(backend._cache_successful._items) == 2


def test_refresh_replaces_entry_without_mutating_previous_entry(clock):
    """Asserts that AuthCache.set_or_refresh() does not replace an _AuthCacheEntry in
    place. The test will fail in case of a construction like this:

    if digest in self._items:
        self._items[digest]._expiry_ns = new_expiry_ns
        self._items[digest]._login = login
        self._items[digest]._groups = frozenset(groups) if groups is not None else None
    """
    cache = auth.AuthCache("test", 2, 10)
    cache.set_or_refresh("key", "old-user", {"readers"})
    previous = cache._items["key"]

    clock.advance(1)
    cache.set_or_refresh("key", "new-user", {"editors"})
    current = cache._items["key"]

    assert current is not previous
    assert (
        previous._expiry_ns,
        previous._login,
        previous._groups,
    ) == (10 * NS, "old-user", frozenset({"readers"}))
    assert cache.get("key") == (
        11 * NS, "new-user", {"editors"})


def test_cache_copies_groups_on_insert(clock):
    cache = auth.AuthCache("test", 2, 10)
    groups = {"readers"}

    cache.set_or_refresh("key", "alice", groups)
    groups.clear()
    groups.add("editors")

    assert cache.get("key") == (
        10 * NS, "alice", {"readers"})
    assert isinstance(cache._items["key"]._groups, frozenset)


def test_cache_copies_groups_on_lookup(clock):
    cache = auth.AuthCache("test", 2, 10)
    cache.set_or_refresh("key", "alice", {"readers"})

    result = cache.get("key")
    assert result is not None
    returned_groups = result[2]
    assert isinstance(returned_groups, set)

    returned_groups.clear()
    returned_groups.add("editors")

    assert cache.get("key") == (
        10 * NS, "alice", {"readers"})
        

class _PauseReaderAfterUnlock:
    """Wrap the cache lock and pause one reader after its outer unlock."""

    def __init__(self, lock):
        self._lock = lock
        self._depth = 0
        self.reader = None
        self.released = threading.Event()
        self.resume = threading.Event()

    def __enter__(self):
        self._lock.acquire()
        self._depth += 1
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # Depth is inspected and changed while holding the real lock.
        self._depth -= 1
        pause = (
            threading.current_thread() is self.reader
            and self._depth == 0
            and not self.released.is_set()
        )
        self._lock.release()

        if pause:
            self.released.set()
            if not self.resume.wait(timeout=5):
                raise AssertionError("Reader was not allowed to resume")

        return False


@pytest.mark.parametrize("operation", [
    "refresh",
    "clear",
    "expire",
    "evict",
])
def test_get_retains_snapshot_after_concurrent_change(clock, operation):
    cache = auth.AuthCache("test", 1, 10)
    cache.set_or_refresh("key", "old-user", {"readers"})
    previous = cache._items["key"]

    gate = _PauseReaderAfterUnlock(cache._lock)
    cache._lock = gate

    results = []
    errors = []

    def read():
        try:
            results.append(cache.get("key"))
        except Exception as exc:
            errors.append(exc)

    def change():
        try:
            if operation == "refresh":
                clock.advance(1)
                cache.set_or_refresh(
                    "key", "new-user", {"editors"})
            elif operation == "clear":
                assert cache.clear("key") is True
            elif operation == "expire":
                clock.advance(10)
                cache.cleanup()
            elif operation == "evict":
                cache.set_or_refresh(
                    "other", "other-user", {"other-group"})
            else:
                raise AssertionError("Unknown operation")
        except Exception as exc:
            errors.append(exc)

    reader = threading.Thread(target=read, daemon=True)
    writer = threading.Thread(target=change, daemon=True)
    gate.reader = reader
    writer_started = False

    reader.start()
    try:
        assert gate.released.wait(timeout=5), (
            "Reader did not reach the unlocked snapshot boundary"
        )

        writer.start()
        writer_started = True
        writer.join(timeout=5)

        assert not writer.is_alive(), (
            "Writer could not finish while the reader was paused"
        )
        if errors:
            raise errors[0]
    finally:
        gate.resume.set()
        reader.join(timeout=5)
        if writer_started:
            writer.join(timeout=5)

    assert not reader.is_alive(), "Reader did not finish"
    assert not writer.is_alive(), "Writer did not finish"
    if errors:
        raise errors[0]

    # The in-progress lookup retains its original, consistent snapshot.
    assert results == [
        (10 * NS, "old-user", {"readers"}),
    ]
    assert (
        previous._expiry_ns,
        previous._login,
        previous._groups,
    ) == (10 * NS, "old-user", frozenset({"readers"}))

    # A subsequent lookup observes the completed modification.
    if operation == "refresh":
        assert cache._items["key"] is not previous
        assert cache.get("key") == (
            11 * NS, "new-user", {"editors"})
    else:
        assert cache.get("key") is None

    if operation == "evict":
        assert cache.get("other") == (
            10 * NS, "other-user", {"other-group"})


