#!/usr/bin/env python3
"""Tests for the pinfo console script entry point (plaso.scripts.pinfo).

Test doubles used:
* mock: the PinfoTool class is replaced by a MagicMock (autospec) so Main() can
  be tested without a storage file and its calls can be verified.
* stub: the mocked tool attributes and return values (CompareStores result,
  ParseArguments result) drive Main() into each branch.
"""

import io
import unittest
from unittest import mock

from plaso.cli import pinfo_tool
from plaso.lib import errors
from plaso.scripts import pinfo


class PinfoMainTest(unittest.TestCase):
    """Tests for the pinfo Main function."""

    def _CreateToolMock(self, parse_result=True, **attributes):
        """Creates a PinfoTool mock with stubbed attributes.

        Args:
          parse_result (Optional[bool]): value returned by ParseArguments().
          attributes (dict): attribute values that override the defaults.

        Returns:
          MagicMock: mocked PinfoTool instance.
        """
        tool = mock.create_autospec(pinfo_tool.PinfoTool, instance=True)
        tool.ParseArguments.return_value = parse_result
        tool.show_troubleshooting = False
        tool.list_reports = False
        tool.list_sections = False
        tool.compare_storage_information = False
        tool.generate_report = False
        for name, value in attributes.items():
            setattr(tool, name, value)
        return tool

    def _RunMain(self, tool):
        """Runs Main() with a mocked PinfoTool.

        Args:
          tool (MagicMock): mocked PinfoTool instance.

        Returns:
          tuple[int, str]: exit code and stdout.
        """
        output = io.StringIO()
        with (
            mock.patch.object(pinfo.pinfo_tool, "PinfoTool", return_value=tool),
            mock.patch.object(pinfo.sys, "argv", ["pinfo.py", "test.plaso"]),
            mock.patch("sys.stdout", output),
        ):
            exit_code = pinfo.Main()
        return exit_code, output.getvalue()

    def testParseArgumentsFails(self):
        """Tests that invalid arguments return 1."""
        tool = self._CreateToolMock(parse_result=False)
        exit_code, _ = self._RunMain(tool)

        self.assertEqual(exit_code, 1)
        tool.ParseArguments.assert_called_once_with(["test.plaso"])
        tool.PrintStorageInformation.assert_not_called()

    def testTroubleshooting(self):
        """Tests the troubleshooting output path."""
        tool = self._CreateToolMock(show_troubleshooting=True)
        tool.GetVersionInformation.return_value = "plaso - pinfo version 1"
        with mock.patch.object(pinfo.dependencies, "CheckDependencies") as mock_check:
            exit_code, output = self._RunMain(tool)

        self.assertEqual(exit_code, 0)
        self.assertIn("plaso - pinfo version 1", output)
        mock_check.assert_called_once_with(verbose_output=True)
        tool.CheckOutDated.assert_not_called()

    def testCheckOutDatedInterrupted(self):
        """Tests a KeyboardInterrupt during the out-of-date check."""
        tool = self._CreateToolMock()
        tool.CheckOutDated.side_effect = KeyboardInterrupt
        exit_code, _ = self._RunMain(tool)
        self.assertEqual(exit_code, 1)

    def testListOptions(self):
        """Tests the list reports and list sections options."""
        tool = self._CreateToolMock(list_reports=True, list_sections=True)
        exit_code, _ = self._RunMain(tool)

        self.assertEqual(exit_code, 0)
        tool.ListReports.assert_called_once_with()
        tool.ListSections.assert_called_once_with()
        tool.PrintStorageInformation.assert_not_called()

    def testPrintStorageInformation(self):
        """Tests the default path that prints storage information."""
        tool = self._CreateToolMock()
        exit_code, _ = self._RunMain(tool)

        self.assertEqual(exit_code, 0)
        tool.PrintStorageInformation.assert_called_once_with()
        tool.CompareStores.assert_not_called()
        tool.GenerateReport.assert_not_called()

    def testGenerateReport(self):
        """Tests the generate report path."""
        tool = self._CreateToolMock(generate_report=True)
        exit_code, _ = self._RunMain(tool)

        self.assertEqual(exit_code, 0)
        tool.GenerateReport.assert_called_once_with()
        tool.PrintStorageInformation.assert_not_called()

    def testCompareStores(self):
        """Tests that the CompareStores result determines the exit code."""
        for stores_identical, expected_exit_code in ((True, 0), (False, 1)):
            with self.subTest(stores_identical=stores_identical):
                tool = self._CreateToolMock(compare_storage_information=True)
                tool.CompareStores.return_value = stores_identical
                exit_code, _ = self._RunMain(tool)

                self.assertEqual(exit_code, expected_exit_code)
                tool.GenerateReport.assert_not_called()

    def testBrokenPipe(self):
        """Tests that a BrokenPipeError (SIGPIPE) is not an error."""
        tool = self._CreateToolMock()
        tool.PrintStorageInformation.side_effect = BrokenPipeError
        exit_code, _ = self._RunMain(tool)
        self.assertEqual(exit_code, 0)

    def testAborted(self):
        """Tests that user aborts return 1."""
        for exception in (KeyboardInterrupt, errors.UserAbort):
            with self.subTest(exception=exception.__name__):
                tool = self._CreateToolMock()
                tool.PrintStorageInformation.side_effect = exception
                with self.assertLogs(level="WARNING"):
                    exit_code, _ = self._RunMain(tool)
                self.assertEqual(exit_code, 1)

    def testBadConfigOption(self):
        """Tests that a BadConfigOption is logged and returns 1."""
        tool = self._CreateToolMock(generate_report=True)
        tool.GenerateReport.side_effect = errors.BadConfigOption("bad report")
        with self.assertLogs(level="WARNING") as logs:
            exit_code, _ = self._RunMain(tool)

        self.assertEqual(exit_code, 1)
        self.assertIn("bad report", logs.output[0])


if __name__ == "__main__":
    unittest.main()
