class LRUCache:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.data: dict = {}

    def get(self, key, default=None):
        return self.data.get(key, default)

    def put(self, key, value):
        if key in self.data:
            del self.data[key]
        elif len(self.data) >= self.capacity:
            del self.data[next(iter(self.data))]
        self.data[key] = value
