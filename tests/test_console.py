import unittest
from unittest.mock import patch

from ingestion_common.console import enable_utf8


class RecordingStream:
    def __init__(self):
        self.encodings = []

    def reconfigure(self, *, encoding):
        self.encodings.append(encoding)


class ConsoleTests(unittest.TestCase):
    def test_enable_utf8_reconfigures_both_windows_console_streams(self):
        stdout = RecordingStream()
        stderr = RecordingStream()

        with (
            patch("ingestion_common.console.sys.platform", "win32"),
            patch("ingestion_common.console.sys.stdout", stdout),
            patch("ingestion_common.console.sys.stderr", stderr),
        ):
            enable_utf8()

        self.assertEqual(["utf-8"], stdout.encodings)
        self.assertEqual(["utf-8"], stderr.encodings)

    def test_enable_utf8_leaves_non_windows_streams_unchanged(self):
        stdout = RecordingStream()
        stderr = RecordingStream()

        with (
            patch("ingestion_common.console.sys.platform", "linux"),
            patch("ingestion_common.console.sys.stdout", stdout),
            patch("ingestion_common.console.sys.stderr", stderr),
        ):
            enable_utf8()

        self.assertEqual([], stdout.encodings)
        self.assertEqual([], stderr.encodings)


if __name__ == "__main__":
    unittest.main()
