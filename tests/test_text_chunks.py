import unittest

from app.text import chunk_lines


class TextChunkTest(unittest.TestCase):
    def test_lines_are_chunked_without_exceeding_telegram_limit(self) -> None:
        lines = [f"invite-{index:03d} | active | user" for index in range(250)]

        chunks = chunk_lines(lines, limit=200)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 200 for chunk in chunks))
        restored = [line for chunk in chunks for line in chunk.splitlines()]
        self.assertEqual(restored, lines)

    def test_single_long_line_is_split_safely(self) -> None:
        chunks = chunk_lines(["x" * 25], limit=10)

        self.assertEqual(chunks, ["x" * 10, "x" * 10, "x" * 5])


if __name__ == "__main__":
    unittest.main()

