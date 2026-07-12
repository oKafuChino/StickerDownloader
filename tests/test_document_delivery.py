import ast
import unittest
from pathlib import Path


class DocumentDeliveryContractTest(unittest.TestCase):
    def test_gif_upload_disables_telegram_content_type_detection(self) -> None:
        source = Path("app/handlers.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        document_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "answer_document"
        ]

        self.assertEqual(len(document_calls), 1)
        keyword = next(
            (
                item
                for item in document_calls[0].keywords
                if item.arg == "disable_content_type_detection"
            ),
            None,
        )
        self.assertIsNotNone(keyword)
        self.assertIsInstance(keyword.value, ast.Constant)
        self.assertIs(keyword.value.value, True)


if __name__ == "__main__":
    unittest.main()

