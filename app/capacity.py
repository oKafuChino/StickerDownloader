class CapacityLimiter:
    def __init__(self, limit: int) -> None:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        self._limit = limit
        self._in_use = 0

    def try_acquire(self) -> bool:
        if self._in_use >= self._limit:
            return False
        self._in_use += 1
        return True

    def release(self) -> None:
        if self._in_use == 0:
            raise RuntimeError("cannot release capacity without admission")
        self._in_use -= 1
