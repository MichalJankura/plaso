#!/usr/bin/env python3
"""Tests for the psort console script entry point (plaso.scripts.psort).

Test doubles used:
* mock: the PsortTool class is replaced by a MagicMock (autospec) so Main() can
  be tested without a storage file and its calls can be verified.
* stub: the mocked tool attributes (list_* flags, show_troubleshooting) and
  ParseArguments() return canned values that drive Main() into each branch.
"""

import io
import unittest
from unittest import mock

from plaso.cli import psort_tool
from plaso.lib import errors
from plaso.scripts import psort


class PsortMainTest(unittest.TestCase):
    """Tests for the psort Main function."""

    _LIST_OPTIONS = {
        "list_analysis_plugins": "ListAnalysisPlugins",
        "list_language_tags": "ListLanguageTags",
        "list_output_modules": "ListOutputModules",
        "list_profilers": "ListProfilers",
        "list_time_zones": "ListTimeZones",
    }

    def _CreateToolMock(self, parse_result=True, **attributes):
        """Creates a PsortTool mock with stubbed attributes.

        Args:
          parse_result (Optional[bool]): value returned by ParseArguments().
          attributes (dict): attribute values that override the defaults.

        Returns:
          MagicMock: mocked PsortTool instance.
        """
        tool = mock.create_autospec(psort_tool.PsortTool, instance=True)
        tool.ParseArguments.return_value = parse_result
        tool.show_troubleshooting = False
        for option_name in self._LIST_OPTIONS:
            setattr(tool, option_name, False)
        for name, value in attributes.items():
            setattr(tool, name, value)
        return tool

    def _RunMain(self, tool, argv=None):
        """Runs Main() with a mocked PsortTool.

        Args:
          tool (MagicMock): mocked PsortTool instance.
          argv (Optional[list[str]]): command line arguments.

        Returns:
          tuple[int, str, MagicMock]: exit code, stdout and the class mock.
        """
        output = io.StringIO()
        argv = argv or ["psort.py", "test.plaso"]
        with (
            mock.patch.object(
                psort.psort_tool, "PsortTool", return_value=tool
            ) as mock_class,
            mock.patch.object(psort.sys, "argv", argv),
            mock.patch("sys.stdout", output),
        ):
            exit_code = psort.Main()
        return exit_code, output.getvalue(), mock_class

    def testParseArgumentsFails(self):
        """Tests that invalid arguments return 1 and nothing is processed."""
        tool = self._CreateToolMock(parse_result=False)
        exit_code, _, _ = self._RunMain(tool, ["psort.py", "--bogus"])

        self.assertEqual(exit_code, 1)
        tool.ParseArguments.assert_called_once_with(["--bogus"])
        tool.ProcessStorage.assert_not_called()

    def testToolCreatedWithStdinReader(self):
        """Tests that the tool is created with a stdin input reader."""
        tool = self._CreateToolMock()
        _, _, mock_class = self._RunMain(tool)

        _, kwargs = mock_class.call_args
        self.assertEqual(type(kwargs["input_reader"]).__name__, "StdinInputReader")

    def testTroubleshooting(self):
        """Tests the troubleshooting output path."""
        tool = self._CreateToolMock(show_troubleshooting=True)
        tool.GetVersionInformation.return_value = "plaso - psort version 1"

        with mock.patch.object(
            psort.dependencies, "CheckDependencies", return_value=True
        ) as mock_check:
            exit_code, output, _ = self._RunMain(tool)

        self.assertEqual(exit_code, 0)
        self.assertIn("Using Python version", output)
        self.assertIn("plaso - psort version 1", output)
        self.assertIn("Troubleshooting.html", output)
        mock_check.assert_called_once_with(verbose_output=True)
        tool.CheckOutDated.assert_not_called()
        tool.ProcessStorage.assert_not_called()

    def testCheckOutDatedInterrupted(self):
        """Tests a KeyboardInterrupt during the out-of-date check."""
        tool = self._CreateToolMock()
        tool.CheckOutDated.side_effect = KeyboardInterrupt
        exit_code, _, _ = self._RunMain(tool)

        self.assertEqual(exit_code, 1)
        tool.ProcessStorage.assert_not_called()

    def testEachListOption(self):
        """Tests that each list option calls its method and skips processing."""
        for option_name, method_name in self._LIST_OPTIONS.items():
            with self.subTest(option=option_name):
                tool = self._CreateToolMock(**{option_name: True})
                exit_code, _, _ = self._RunMain(tool)

                self.assertEqual(exit_code, 0)
                getattr(tool, method_name).assert_called_once_with()
                tool.ProcessStorage.assert_not_called()

    def testAllListOptions(self):
        """Tests that all list options can be combined."""
        tool = self._CreateToolMock(**{name: True for name in self._LIST_OPTIONS})
        exit_code, _, _ = self._RunMain(tool)

        self.assertEqual(exit_code, 0)
        for method_name in self._LIST_OPTIONS.values():
            getattr(tool, method_name).assert_called_once_with()

    def testProcessStorage(self):
        """Tests the normal processing path."""
        tool = self._CreateToolMock()
        exit_code, _, _ = self._RunMain(tool)

        self.assertEqual(exit_code, 0)
        tool.CheckOutDated.assert_called_once_with()
        tool.ProcessStorage.assert_called_once_with()

    def testProcessStorageBrokenPipe(self):
        """Tests that a BrokenPipeError (SIGPIPE) is not an error."""
        tool = self._CreateToolMock()
        tool.ProcessStorage.side_effect = BrokenPipeError
        exit_code, _, _ = self._RunMain(tool)
        self.assertEqual(exit_code, 0)

    def testProcessStorageAborted(self):
        """Tests that user aborts return 1."""
        for exception in (KeyboardInterrupt, errors.UserAbort):
            with self.subTest(exception=exception.__name__):
                tool = self._CreateToolMock()
                tool.ProcessStorage.side_effect = exception
                with self.assertLogs(level="WARNING") as logs:
                    exit_code, _, _ = self._RunMain(tool)

                self.assertEqual(exit_code, 1)
                self.assertIn("Aborted by user.", logs.output[0])

    def testProcessStorageRuntimeError(self):
        """Tests that a RuntimeError is printed and returns 1."""
        tool = self._CreateToolMock()
        tool.ProcessStorage.side_effect = RuntimeError("storage is broken")
        exit_code, output, _ = self._RunMain(tool)

        self.assertEqual(exit_code, 1)
        self.assertIn("storage is broken", output)

    def testProcessStorageBadConfigOption(self):
        """Tests that a BadConfigOption is logged and returns 1."""
        tool = self._CreateToolMock()
        tool.ProcessStorage.side_effect = errors.BadConfigOption("bad option")
        with self.assertLogs(level="WARNING") as logs:
            exit_code, _, _ = self._RunMain(tool)

        self.assertEqual(exit_code, 1)
        self.assertIn("bad option", logs.output[0])


if __name__ == "__main__":
    unittest.main()
