import logging
import runpy
from pathlib import Path
from unittest import TestCase

module = runpy.run_path(str(Path(__file__).resolve().parents[3] / "django_app" / "lib" / "logs.py"))
get_logger, logged = module["get_logger"], module["logged"]


class LoggingTestCase(TestCase):
    def test_call_and_result_are_summarized_without_leaking_content(self):
        @logged
        def process(payload, *, api_key):
            return {"evidence": payload["secret"], "count": 2}

        with self.assertLogs("tests.django_app.lib.test_logs", level="DEBUG") as captured:
            result = process({"secret": "private patient text"}, api_key="top-secret-key")

        self.assertEqual(result, {"evidence": "private patient text", "count": 2})
        output = "\n".join(captured.output)
        self.assertIn("process called args=", output)
        self.assertIn("kwargs=", output)
        self.assertIn("process returned", output)
        self.assertNotIn("private patient text", output)
        self.assertNotIn("top-secret-key", output)
        self.assertNotIn(f"str(len={len('top-secret-key')})", output)

    def test_exception_is_logged_once_and_propagated(self):
        @logged
        def fail():
            raise ValueError("private patient text")

        with self.assertLogs("tests.django_app.lib.test_logs", level="DEBUG") as captured:
            with self.assertRaisesRegex(ValueError, "private patient text"):
                fail()

        self.assertEqual([record.levelno for record in captured.records], [logging.DEBUG, logging.ERROR])
        self.assertNotIn("private patient text", "\n".join(captured.output))
        self.assertIn("ValueError", captured.output[-1])

    def test_get_logger_respects_explicit_level(self):
        logger = get_logger("tests.logging.example", level="WARNING")
        self.assertEqual(logger.level, logging.WARNING)

    def test_formatter_does_not_change_other_loggers_using_same_handler(self):
        shared = logging.StreamHandler()
        first = logging.getLogger("tests.shared.first")
        second = logging.getLogger("tests.shared.second")
        original = logging.Formatter("original: %(message)s")
        shared.setFormatter(original)
        first.addHandler(shared)
        second.addHandler(shared)
        try:
            get_logger(first.name, formatter="custom: %(message)s")
            self.assertIs(second.handlers[0].formatter, original)
        finally:
            first.handlers.clear()
            second.handlers.clear()
            first.propagate = True

    def test_nested_calls_log_one_error(self):
        @logged
        def inner():
            raise RuntimeError("secret")

        @logged
        def outer():
            inner()

        with self.assertLogs("tests.django_app.lib.test_logs", level="DEBUG") as captured:
            with self.assertRaises(RuntimeError):
                outer()

        self.assertEqual([record.levelno for record in captured.records].count(logging.ERROR), 1)
