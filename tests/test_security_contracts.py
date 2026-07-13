import unittest

from app.settings import Settings


BASE_ENVIRONMENT = {
    "BOT_TOKEN": "123:token",
    "OWNER_TELEGRAM_ID": "42",
    "DATABASE_PATH": "/data/bot.sqlite3",
    "TEMP_ROOT": "/tmp/bot",
    "CONVERSION_CONCURRENCY": "2",
}


class PendingConversionSettingsTest(unittest.TestCase):
    def test_old_environment_defaults_to_eight_pending_tasks(self) -> None:
        settings = Settings.from_env(BASE_ENVIRONMENT)

        self.assertEqual(settings.max_pending_conversions, 8)

    def test_explicit_non_negative_values_are_accepted(self) -> None:
        for value in (0, 12):
            with self.subTest(value=value):
                settings = Settings.from_env(
                    {
                        **BASE_ENVIRONMENT,
                        "MAX_PENDING_CONVERSIONS": str(value),
                    }
                )
                self.assertEqual(settings.max_pending_conversions, value)

    def test_negative_value_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "MAX_PENDING_CONVERSIONS"):
            Settings.from_env(
                {
                    **BASE_ENVIRONMENT,
                    "MAX_PENDING_CONVERSIONS": "-1",
                }
            )

    def test_non_integer_value_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "MAX_PENDING_CONVERSIONS"):
            Settings.from_env(
                {
                    **BASE_ENVIRONMENT,
                    "MAX_PENDING_CONVERSIONS": "many",
                }
            )


if __name__ == "__main__":
    unittest.main()
