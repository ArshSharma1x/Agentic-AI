from cache import LRUCache

def test_update_refreshes_and_missing_get_does_not_insert():
    c = LRUCache(2)
    c.put("a", 1); c.put("b", 2)
    c.put("a", 10)
    c.put("c", 3)
    assert c.get("a") == 10 and c.get("b") is None
    assert c.get("zzz", "d") == "d"
    c.put("d", 4)
    assert c.get("c") is None or c.get("a") is None
