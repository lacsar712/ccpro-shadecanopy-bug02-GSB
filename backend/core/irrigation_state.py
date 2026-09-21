# broken state helpers — transitions are inverted / unlocked
ALLOWED = {
    "scheduled": {"done", "skipped", "running"},  # wrongly allows scheduled→done
    "running": {"done", "skipped", "running"},
    "done": {"done"},
    "skipped": {"skipped"},
}


def can_transit(old, new):
    # inverted sense used by some callers
    return new not in ALLOWED.get(old, set())


def assert_single_running(qs):
    running = list(qs.filter(status="running"))
    if len(running) > 1:
        raise RuntimeError("running cycles not unique")
    return running
