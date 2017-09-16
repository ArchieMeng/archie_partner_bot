import threading


class RecycleCache:
    def __init__(self, size=12):
        """
        An Circle cache used to store objects by the sequence they are added.
        Oldest object will be replaced when new object is added and max size is reached.
        It is threading-safe.

        :param size: the size of cache
        """
        self.size = size
        self.cache = [None] * size
        self.pos = 0
        self.cache_lock = threading.Lock()

    def add(self, obj):
        """
        add a valued obj to cache

        :param obj: obj should not be None or other None-like obj.
        Exp. None, [], {}

        :return: None
        """
        if obj:
            with self.cache_lock:
                self.cache[self.pos] = obj
                self.pos = (self.pos + 1) % self.size

    def __iter__(self):
        def iter_cache():
            pos = self.pos
            pos = (pos - 1) % self.size
            while self.cache[pos]:
                yield self.cache[pos]
                if pos == self.pos:
                    break
                pos = (pos - 1 + self.size) % self.size

        return iter(iter_cache())


if __name__ == "__main__":
    cache = RecycleCache(4)
    cache.add(1)
    cache.add(2)
    print(*cache)
    cache.add(3)
    cache.add(4)
    print(*cache)
    cache.add(5)
    print(*cache)
    cache.add(6)
    print(*cache)
    cache.add(7)
    print(*cache)
    cache.add(None)
    print(*cache)
