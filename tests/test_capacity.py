import unittest

from app.capacity import CapacityLimiter


class CapacityLimiterTest(unittest.TestCase):
    def test_rejects_work_after_capacity_is_full(self) -> None:
        limiter = CapacityLimiter(2)

        self.assertTrue(limiter.try_acquire())
        self.assertTrue(limiter.try_acquire())
        self.assertFalse(limiter.try_acquire())

    def test_released_capacity_can_be_reused(self) -> None:
        limiter = CapacityLimiter(1)
        self.assertTrue(limiter.try_acquire())

        limiter.release()

        self.assertTrue(limiter.try_acquire())

    def test_rejects_non_positive_limit(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least 1"):
            CapacityLimiter(0)

    def test_release_without_admission_is_an_error(self) -> None:
        limiter = CapacityLimiter(1)

        with self.assertRaisesRegex(RuntimeError, "without admission"):
            limiter.release()


if __name__ == "__main__":
    unittest.main()
