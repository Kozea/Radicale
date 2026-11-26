from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace

import pytest

from radicale import auth, config
from radicale.auth import _AuthLimiter
from radicale.tests import BaseTest

# Watchdog for test-owned events and futures. The timeout test configures
# a shorter application deadline independently.
WATCHDOG = 10


def make_auth(monkeypatch, backend, *, cache=True, total=2, active=1,
              per_login=1, timeout=5.0):
    configuration = config.load()
    configuration.update({
        "auth": {
            "type": "htpasswd",
            "delay": "0",
            "cache_logins": str(cache),
            "cache_successful_logins_expiry": "60",
            "cache_failed_logins_expiry": "60",
            "concurrency_limit_enabled": "true",
            "concurrency_total_limit": str(total),
            "concurrency_active_limit": str(active),
            "concurrency_per_user_limit": str(per_login),
            "concurrency_wait_timeout": str(timeout),
        },
    }, "test", privileged=True)
    instance = auth.BaseAuth(configuration)
    monkeypatch.setattr(instance, "_login_ext_with_groups", backend)
    return instance


def login(instance, username, password):
    return instance.login(username, password, auth.AuthContext())


def admit(limiter, username, digest, token=None):
    reason, acquired = limiter.try_to_acquire(username, digest, token)
    assert reason == 0
    assert len(acquired) == 5
    return acquired


def queue(limiter, username, digest):
    reason, token = limiter.try_to_acquire(username, digest)
    assert reason != 0
    assert len(token) == 2
    return token


@pytest.mark.parametrize(
    "active_limit,per_login_limit,waiting_login",
    [(1, 2, "bob"), (2, 1, "alice")],
    ids=["active-limit", "per-login-limit"],
)
def test_each_active_limit_with_digest_check_disabled(
    active_limit, per_login_limit, waiting_login,
):
    limiter = _AuthLimiter(3, active_limit, per_login_limit, False)
    running = admit(limiter, "alice", "first")
    waiting = queue(limiter, waiting_login, "second")
    if active_limit == 2:
        # Alice is at her own cap. Bob can use the remaining active slot.
        another = admit(limiter, "bob", "third")
        limiter.release(another)

    limiter.release(running)
    promoted = admit(limiter, waiting_login, "second", waiting)
    limiter.release(promoted)


def test_waiter_can_be_promoted_at_total_cap():
    limiter = _AuthLimiter(3, 2, 1, False)
    alice = admit(limiter, "alice", "a1")
    bob = admit(limiter, "bob", "b1")
    waiting_alice = queue(limiter, "alice", "a2")

    reason, rejected = limiter.try_to_acquire("carol", "c1")
    assert reason != 0
    assert len(rejected) == 1

    limiter.release(alice)
    # Bob's second request refills total capacity while leaving one active
    # slot open. Alice's waiter already owns a total slot.
    waiting_bob = queue(limiter, "bob", "b2")
    promoted_alice = admit(limiter, "alice", "a2", waiting_alice)

    reason, rejected = limiter.try_to_acquire("carol", "c1")
    assert reason != 0
    assert len(rejected) == 1

    limiter.release(waiting_bob)
    limiter.release(promoted_alice)
    carol = admit(limiter, "carol", "c1")
    limiter.release(carol)
    limiter.release(bob)


def test_both_cache_outcomes_bypass_full_limiter(monkeypatch):
    blocker_entered = Event()
    unblock = Event()
    calls = []

    def backend(username, password, context):
        calls.append((username, password))
        if username == "blocker":
            blocker_entered.set()
            assert unblock.wait(WATCHDOG)
        if password == "bad":
            return "", set()
        return username, {"calendar-users"}

    instance = make_auth(monkeypatch, backend, total=1)
    assert login(instance, "alice", "good") == (
        "alice", {"calendar-users"}, "htpasswd",
    )
    assert login(instance, "alice", "bad") == ("", set(), "htpasswd")

    with ThreadPoolExecutor(max_workers=1) as pool:
        blocker = pool.submit(login, instance, "blocker", "good")
        try:
            assert blocker_entered.wait(WATCHDOG)
            rejected_user, groups, source = login(instance, "fresh", "good")
            assert (rejected_user, groups) == ("", set())
            assert source not in {"htpasswd", "htpasswd/cached"}

            def unexpected_admission(*args, **kwargs):
                pytest.fail("A cache hit attempted limiter admission")

            with monkeypatch.context() as patch:
                patch.setattr(_AuthLimiter, "try_to_acquire", unexpected_admission)
                assert login(instance, "alice", "good") == (
                    "alice", {"calendar-users"}, "htpasswd/cached",
                )
                assert login(instance, "alice", "bad") == (
                    "", set(), "htpasswd/cached",
                )
        finally:
            unblock.set()
        assert blocker.result(WATCHDOG)[0] == "blocker"

    # The temporary rejection must not become a failed-credential hit.
    assert login(instance, "fresh", "good")[0] == "fresh"
    assert calls == [
        ("alice", "good"), ("alice", "bad"), ("blocker", "good"),
        ("fresh", "good"),
    ]


@pytest.mark.parametrize("accepted", [True, False], ids=["success", "rejection"])
def test_identical_waiter_reuses_result_when_release_precedes_sleep(
    monkeypatch, accepted,
):
    first_entered = Event()
    finish_first = Event()
    waiter_at_wait = Event()
    allow_wait = Event()
    calls = []
    expected = ("alice", {"calendar-users"}) if accepted else ("", set())
    original_wait = _AuthLimiter.wait_to_acquire

    def backend(username, password, context):
        calls.append((username, password))
        if (username, password) == ("alice", "pw"):
            first_entered.set()
            assert finish_first.wait(WATCHDOG)
            return expected
        return username, set()

    def pause_before_wait(self, token, timeout):
        waiter_at_wait.set()
        assert allow_wait.wait(WATCHDOG)
        return original_wait(self, token, timeout)

    monkeypatch.setattr(_AuthLimiter, "wait_to_acquire", pause_before_wait)
    # Only the digest check can force the second Alice request to wait.
    instance = make_auth(monkeypatch, backend, total=2, active=2, per_login=2)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(login, instance, "alice", "pw")
        try:
            assert first_entered.wait(WATCHDOG)
            second = pool.submit(login, instance, "alice", "pw")
            assert waiter_at_wait.wait(WATCHDOG)
            finish_first.set()
            assert first.result(WATCHDOG) == (*expected, "htpasswd")
            allow_wait.set()
            assert second.result(WATCHDOG) == (*expected, "htpasswd/cached")
        finally:
            finish_first.set()
            allow_wait.set()

    assert calls == [("alice", "pw")]
    assert login(instance, "bob", "pw")[0] == "bob"


def test_timeout_releases_waiting_capacity_without_caching_failure(monkeypatch):
    blocker_entered = Event()
    unblock = Event()
    calls = []

    def backend(username, password, context):
        calls.append(username)
        if username == "blocker":
            blocker_entered.set()
            assert unblock.wait(WATCHDOG)
        return username, set()

    instance = make_auth(monkeypatch, backend, timeout=0.25)
    with ThreadPoolExecutor(max_workers=2) as pool:
        blocker = pool.submit(login, instance, "blocker", "pw")
        try:
            assert blocker_entered.wait(WATCHDOG)
            waiting = pool.submit(login, instance, "alice", "pw")
            result, groups, source = waiting.result(WATCHDOG)
            assert (result, groups) == ("", set())
            assert source not in {"htpasswd", "htpasswd/cached"}
            assert calls == ["blocker"]
            assert not blocker.done()
        finally:
            unblock.set()
        assert blocker.result(WATCHDOG)[0] == "blocker"

    assert login(instance, "alice", "pw") == ("alice", set(), "htpasswd")
    assert calls == ["blocker", "alice"]


def test_backend_exception_does_not_poison_digest_or_leak_capacity(monkeypatch):
    class BackendError(Exception):
        pass

    calls = []

    def backend(username, password, context):
        calls.append((username, password))
        if len(calls) == 1:
            raise BackendError("transient test failure")
        return username, set()

    instance = make_auth(monkeypatch, backend, total=1)
    try:
        result, _, source = login(instance, "alice", "pw")
    except BackendError:
        pass
    else:
        # Also allow an implementation that translates the exception.
        assert result == ""
        assert not source.endswith("/cached")

    assert login(instance, "alice", "pw") == ("alice", set(), "htpasswd")
    assert calls == [("alice", "pw"), ("alice", "pw")]


def test_identical_credentials_can_overlap_with_cache_disabled(monkeypatch):
    first_entered = Event()
    second_entered = Event()
    unblock = Event()
    calls = []

    def backend(username, password, context):
        calls.append((username, password))
        if (username, password) == ("alice", "pw"):
            # Each invocation signals via its distinct AuthContext.
            context.entered.set()
            assert unblock.wait(WATCHDOG)
        return username, set()

    instance = make_auth(
        monkeypatch, backend, cache=False, total=2, active=2, per_login=2,
    )
    first_context = auth.AuthContext()
    first_context.entered = first_entered
    second_context = auth.AuthContext()
    second_context.entered = second_entered

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(instance.login, "alice", "pw", first_context)
        try:
            assert first_entered.wait(WATCHDOG)
            second = pool.submit(instance.login, "alice", "pw", second_context)
            assert second_entered.wait(WATCHDOG)

            result, groups, source = login(instance, "bob", "pw")
            assert (result, groups) == ("", set())
            assert source not in {"htpasswd", "htpasswd/cached"}
        finally:
            unblock.set()
        assert first.result(WATCHDOG) == ("alice", set(), "htpasswd")
        assert second.result(WATCHDOG) == ("alice", set(), "htpasswd")

    assert calls == [("alice", "pw"), ("alice", "pw")]
    assert login(instance, "bob", "pw")[0] == "bob"


TEMPORARY = "htpasswd/error:temp:concurrent-session-limit"
EMPTY_LIMITER = (0, 0, {}, set())


def limiter_state(limiter):
    with limiter._condition:
        return (
            limiter._curr_total,
            limiter._curr_active,
            dict(limiter._curr_per_login),
            set(limiter._curr_per_digest),
        )


@pytest.mark.parametrize("accepted", [True, False], ids=["success", "rejection"])
@pytest.mark.parametrize(
    "pause_at", ["queued", "before-sleep", "before-promotion"],
)
def test_identical_waiter_reuses_published_result(monkeypatch, accepted, pause_at):
    first_entered = Event()
    finish_first = Event()
    waiter_paused = Event()
    resume_waiter = Event()
    about_to_wait = Event()
    calls = []
    expected = ("alice", {"calendar-users"}) if accepted else ("", set())

    def backend(username, password, context):
        calls.append((username, password))
        first_entered.set()
        assert finish_first.wait(WATCHDOG)
        return expected

    instance = make_auth(
        monkeypatch, backend, total=3, active=3, per_login=3,
    )
    limiter = instance._limiter
    acquire = limiter.try_to_acquire
    wait = limiter.wait_to_acquire

    def pause():
        waiter_paused.set()
        assert resume_waiter.wait(WATCHDOG)

    def acquire_with_pause(username, digest, token=None):
        if pause_at == "before-promotion" and token is not None:
            pause()
        outcome = acquire(username, digest, token)
        if pause_at == "queued" and len(outcome[1]) == 2:
            pause()
        return outcome

    def wait_with_pause(token, timeout):
        about_to_wait.set()
        if pause_at == "before-sleep":
            pause()
        return wait(token, timeout)

    monkeypatch.setattr(limiter, "try_to_acquire", acquire_with_pause)
    monkeypatch.setattr(limiter, "wait_to_acquire", wait_with_pause)

    # Wake the waiter for a retry while Alice's first call still owns its
    # digest and has yet to publish. Pause that retry before admission.
    unrelated = None
    if pause_at == "before-promotion":
        unrelated = admit(limiter, "bob", "unrelated")

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(login, instance, "alice", "pw")
        try:
            assert first_entered.wait(WATCHDOG)
            second = pool.submit(login, instance, "alice", "pw")
            if unrelated is not None:
                assert about_to_wait.wait(WATCHDOG)
                limiter.release(unrelated)
                unrelated = None

            assert waiter_paused.wait(WATCHDOG)
            finish_first.set()
            assert first.result(WATCHDOG) == (*expected, "htpasswd")
            assert limiter_state(limiter) == (1, 0, {}, set())

            resume_waiter.set()
            assert second.result(WATCHDOG) == (*expected, "htpasswd/cached")
        finally:
            if unrelated is not None:
                limiter.release(unrelated)
            finish_first.set()
            resume_waiter.set()

    assert calls == [("alice", "pw")]
    assert limiter_state(limiter) == EMPTY_LIMITER
    assert login(instance, "alice", "different")[2] == "htpasswd"
    assert calls == [("alice", "pw"), ("alice", "different")]


def test_unrelated_releases_do_not_extend_configured_deadline(monkeypatch):
    calls = []
    now_ns = 0
    wait_budgets = []

    def backend(username, password, context):
        calls.append((username, password))
        return username, set()

    instance = make_auth(
        monkeypatch, backend, total=3, active=2, per_login=1, timeout=1.0,
    )
    limiter = instance._limiter
    holder = admit(limiter, "alice", "held-digest")
    unrelated = admit(limiter, "bob", "unrelated-digest")
    real_wait = limiter.wait_to_acquire
    monkeypatch.setattr(
        auth, "time", SimpleNamespace(monotonic_ns=lambda: now_ns),
    )

    def wait_with_controlled_clock(token, timeout):
        nonlocal now_ns, unrelated
        wait_budgets.append(timeout)
        if len(wait_budgets) <= 2:
            # Alice stays blocked by the per-login cap on both wakes.
            now_ns += (250_000_000, 500_000_000)[len(wait_budgets) - 1]
            limiter.release(unrelated)
            notified = real_wait(token, 0)
            unrelated = admit(limiter, "bob", "unrelated-digest")
            return notified

        now_ns += 250_000_000
        return real_wait(token, 0)

    monkeypatch.setattr(limiter, "wait_to_acquire", wait_with_controlled_clock)

    try:
        assert login(instance, "alice", "pw") == ("", set(), TEMPORARY)
        assert calls == []
        assert limiter_state(limiter) == (
            2, 2, {"alice": 1, "bob": 1},
            {"held-digest", "unrelated-digest"},
        )
    finally:
        limiter.release(holder)
        limiter.release(unrelated)

    assert limiter_state(limiter) == EMPTY_LIMITER
    assert login(instance, "alice", "pw") == ("alice", set(), "htpasswd")
    assert calls == [("alice", "pw")]
    assert wait_budgets == pytest.approx([1.0, 0.75, 0.25])


@pytest.mark.parametrize("limit", ["active", "normalized-login"])
def test_login_enforces_each_active_limit_without_cache(monkeypatch, limit):
    holder_entered = Event()
    finish_holder = Event()
    waiter_entered_wait = Event()
    calls = []

    def backend(username, password, context):
        calls.append((username, password))
        if password == "hold":
            holder_entered.set()
            assert finish_holder.wait(WATCHDOG)
        return username, set()

    active = 1 if limit == "active" else 2
    instance = make_auth(
        monkeypatch, backend, cache=False, total=3, active=active, per_login=1,
    )
    monkeypatch.setattr(instance, "_lc_username", True)
    limiter = instance._limiter
    real_wait = limiter.wait_to_acquire

    def observe_wait(token, timeout):
        waiter_entered_wait.set()
        return real_wait(token, timeout)

    monkeypatch.setattr(limiter, "wait_to_acquire", observe_wait)
    waiting_name = "bob" if limit == "active" else "alice"

    with ThreadPoolExecutor(max_workers=2) as pool:
        holder = pool.submit(login, instance, "ALICE", "hold")
        try:
            assert holder_entered.wait(WATCHDOG)
            waiter = pool.submit(login, instance, waiting_name, "second")
            assert waiter_entered_wait.wait(WATCHDOG)
            assert limiter_state(limiter) == (2, 1, {"alice": 1}, set())
            assert calls == [("alice", "hold")]
            if limit == "normalized-login":
                assert login(instance, "carol", "pw") == (
                    "carol", set(), "htpasswd",
                )
        finally:
            finish_holder.set()

        assert holder.result(WATCHDOG) == ("alice", set(), "htpasswd")
        assert waiter.result(WATCHDOG) == (waiting_name, set(), "htpasswd")

    assert limiter_state(limiter) == EMPTY_LIMITER


class TestAuthConcurrencyHTTP(BaseTest):
    def test_full_cap_backend_exception_and_fresh_retry(self, tmp_path, monkeypatch):
        users = tmp_path / "users"
        users.write_text("alice:pw\n", encoding="utf-8")
        self.configure({
            "auth": {
                "type": "htpasswd",
                "htpasswd_filename": str(users),
                "htpasswd_encryption": "plain",
                "cache_logins": "true",
                "concurrency_limit_enabled": "true",
                "concurrency_total_limit": "1",
                "concurrency_active_limit": "1",
                "concurrency_per_user_limit": "1",
                "delay": "0",
            },
        })
        instance = self.application._auth
        limiter = instance._limiter
        backend = instance._login_ext_with_groups
        calls = []
        credential_digest = "alice:" + instance._cache_digest(
            "alice", "pw", instance._secret_salt,
        )

        def fail_once(username, password, context):
            calls.append((username, password))
            if len(calls) == 1:
                raise RuntimeError("test backend failure")
            return backend(username, password, context)

        monkeypatch.setattr(instance, "_login_ext_with_groups", fail_once)

        holder = admit(limiter, "blocker", "held-digest")
        try:
            self.request("PROPFIND", "/", login="alice:pw", check=503)
            assert calls == []
            assert limiter_state(limiter) == (
                1, 1, {"blocker": 1}, {"held-digest"},
            )
        finally:
            limiter.release(holder)

        self.request("PROPFIND", "/", login="alice:pw", check=500)
        assert instance._cache_failed.get(credential_digest) is None
        assert limiter_state(limiter) == EMPTY_LIMITER

        self.request("PROPFIND", "/", login="alice:pw", check=207)
        assert calls == [("alice", "pw"), ("alice", "pw")]
        assert limiter_state(limiter) == EMPTY_LIMITER

        _, headers, _ = self.request(
            "PROPFIND", "/", login="alice:bad", check=401,
        )
        assert headers["WWW-Authenticate"].startswith("Basic ")
