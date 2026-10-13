"""Live-cache: kun ændringer publiceres, og en langsom klient mister aldrig en ændring (BUGS v0.27.0 #3)."""

from app.services.live_cache import LiveCache, LiveValue


def _v(value, quality="good"):
    return LiveValue(value=value, quality=quality, ts=1.0)


def _drain(queue):
    out = []
    while not queue.empty():
        out.append(queue.get_nowait())
    return out


def test_only_changes_are_published():
    cache = LiveCache()
    q = cache.subscribe()
    cache.update({"Pumpe": _v(True)})
    cache.update({"Pumpe": _v(True)})          # uændret → intet nyt
    assert [list(d) for d in _drain(q)] == [["Pumpe"]]


def test_full_queue_merges_instead_of_dropping():
    """Pumpe skifter til TIL i den første delta og ændres ikke igen. Når køen løber fuld, må den ændring
    ikke forsvinde — ellers viser Overview pumpen som stoppet, indtil den skifter igen."""
    cache = LiveCache()
    q = cache.subscribe(maxsize=2)
    cache.update({"Pumpe": _v(True)})
    cache.update({"Niveau": _v(10)})
    cache.update({"Niveau": _v(11)})           # køen er fuld her
    cache.update({"Niveau": _v(12), "Temp": _v(20.5)})
    merged = {}
    for delta in _drain(q):
        merged.update(delta)
    assert merged["Pumpe"]["value"] is True    # den første ændring er bevaret
    assert merged["Niveau"]["value"] == 12     # seneste værdi vinder
    assert merged["Temp"]["value"] == 20.5


def test_merged_queue_keeps_order_latest_wins():
    cache = LiveCache()
    q = cache.subscribe(maxsize=1)
    for n in range(5):
        cache.update({"Niveau": _v(n)})
    deltas = _drain(q)
    assert len(deltas) == 1 and deltas[0]["Niveau"]["value"] == 4


def test_other_subscribers_are_not_affected():
    cache = LiveCache()
    slow, fast = cache.subscribe(maxsize=1), cache.subscribe(maxsize=10)
    cache.update({"A": _v(1)})
    cache.update({"B": _v(2)})
    assert [list(d) for d in _drain(fast)] == [["A"], ["B"]]
    assert _drain(slow) == [{"A": _v(1).as_dict(), "B": _v(2).as_dict()}]
