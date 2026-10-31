#!/usr/bin/env python3
"""Tests for the dependency check functionality (plaso.dependencies).

Test doubles used:
* stub: _StubModule objects stand in for imported Python modules and return
  canned version information (attribute or get_version() method).
* mock: unittest.mock.patch replaces _ImportPythonModule and _CheckPythonModule
  so the tests do not depend on what is installed and so the interaction
  (which arguments were passed, how many times) can be verified.
"""

import io
import unittest
from unittest import mock

from plaso import dependencies


class _StubModule:
    """Stub of an imported Python module with canned version information."""

    def __init__(self, version=None, version_method_result=None):
        """Initializes the stub.

        Args:
          version (Optional[object]): value of the __version__ attribute.
          version_method_result (Optional[object]): value returned by
              get_version(), the method is only defined if this is set.
        """
        super().__init__()
        if version is not None:
            self.__version__ = version
        if version_method_result is not None:
            self.get_version = lambda: version_method_result


class CheckPythonModuleTestCase(unittest.TestCase):
    """Shared helper for the _CheckPythonModule tests."""

    _IMPORT_FUNCTION = "plaso.dependencies._ImportPythonModule"

    def _Check(self, stub_module, version_attribute_name="__version__", **kwargs):
        """Runs _CheckPythonModule with a stubbed module and captured output.

        Args:
          stub_module (object): stub returned instead of the imported module.
          version_attribute_name (Optional[str]): version attribute name.
          kwargs (dict): additional keyword arguments for _CheckPythonModule.

        Returns:
          tuple[bool, str, MagicMock]: check result, printed output and the
              mock that replaced _ImportPythonModule.
        """
        minimum_version = kwargs.pop("minimum_version", "1.0")
        output = io.StringIO()
        with mock.patch(self._IMPORT_FUNCTION, return_value=stub_module) as mock_import:
            with mock.patch("sys.stdout", output):
                result = (
                    dependencies._CheckPythonModule(  # pylint: disable=protected-access
                        "testmodule", version_attribute_name, minimum_version, **kwargs
                    )
                )
        return result, output.getvalue(), mock_import


class CheckPythonModuleTest(CheckPythonModuleTestCase):
    """Tests for the _CheckPythonModule function."""

    def testMissingRequiredModule(self):
        """Tests a required module that cannot be imported."""
        result, output, mock_import = self._Check(None)
        self.assertFalse(result)
        self.assertIn("[FAILURE]\tmissing: testmodule.", output)
        mock_import.assert_called_once_with("testmodule")

    def testMissingOptionalModule(self):
        """Tests an optional module that cannot be imported."""
        result, output, _ = self._Check(None, is_required=False)
        self.assertTrue(result)
        self.assertIn("[OPTIONAL]\tmissing: testmodule.", output)

    def testNoVersionRequirement(self):
        """Tests a module without a minimum version requirement."""
        result, output, _ = self._Check(_StubModule(), "", minimum_version="")
        self.assertTrue(result)
        self.assertEqual(output, "[OK]\t\ttestmodule\n")

    def testNoVersionRequirementQuiet(self):
        """Tests that verbose_output=False suppresses the OK message."""
        result, output, _ = self._Check(
            _StubModule(), "", minimum_version="", verbose_output=False
        )
        self.assertTrue(result)
        self.assertEqual(output, "")

    def testVersionAttribute(self):
        """Tests a version read from an attribute."""
        result, output, _ = self._Check(_StubModule(version="1.2.3"))
        self.assertTrue(result)
        self.assertIn("[OK]\t\ttestmodule version: 1.2.3", output)

    def testVersionMethod(self):
        """Tests a version read from a get_version() method."""
        stub_module = _StubModule(version_method_result="20240101")
        result, output, _ = self._Check(
            stub_module, "get_version()", minimum_version="20230101"
        )
        self.assertTrue(result)
        self.assertIn("version: 20240101", output)

    def testVersionMethodMissing(self):
        """Tests a module that does not provide the version method."""
        result, output, _ = self._Check(_StubModule(), "get_version()")
        self.assertFalse(result)
        self.assertIn("unable to determine version information", output)

    def testIntegerVersion(self):
        """Tests that a non-string version is converted to a string."""
        stub_module = _StubModule(version_method_result=20240101)
        result, _, _ = self._Check(
            stub_module, "get_version()", minimum_version="20230101"
        )
        self.assertTrue(result)

    def testUnknownVersionRequired(self):
        """Tests a required module without version information."""
        result, output, _ = self._Check(_StubModule())
        self.assertFalse(result)
        self.assertIn("[FAILURE]\tunable to determine version information", output)

    def testUnknownVersionOptional(self):
        """Tests an optional module without version information."""
        result, output, _ = self._Check(_StubModule(), is_required=False)
        self.assertTrue(result)
        self.assertIn("[OPTIONAL]\tunable to determine version information", output)

    def testVersionSuffixIsIgnored(self):
        """Tests that a non-numeric version suffix such as rc1 is removed."""
        result, _, _ = self._Check(
            _StubModule(version="2.0-rc1"), minimum_version="2.0"
        )
        self.assertTrue(result)

    def testNumericComparison(self):
        """Tests that versions are compared numerically, not as strings."""
        # As strings "1.10" < "1.9", numerically 1.10 > 1.9.
        result, _, _ = self._Check(_StubModule(version="1.10"), minimum_version="1.9")
        self.assertTrue(result)

    def testTooOldRequired(self):
        """Tests a required module that is too old."""
        result, output, _ = self._Check(
            _StubModule(version="0.9"), minimum_version="1.0"
        )
        self.assertFalse(result)
        self.assertIn("is too old, 1.0 or later required", output)

    def testTooOldOptional(self):
        """Tests an optional module that is too old."""
        result, output, _ = self._Check(
            _StubModule(version="0.9"), minimum_version="1.0", is_required=False
        )
        self.assertTrue(result)
        self.assertIn("[OPTIONAL]\ttestmodule version: 0.9 is too old", output)

    def testTooRecentRequired(self):
        """Tests a required module that is more recent than the maximum."""
        result, output, _ = self._Check(
            _StubModule(version="3.0"), minimum_version="1.0", maximum_version="2.0"
        )
        self.assertFalse(result)
        self.assertIn("is too recent, 2.0 or earlier required", output)

    def testWithinMaximumVersion(self):
        """Tests a module within the minimum and maximum version."""
        result, _, _ = self._Check(
            _StubModule(version="1.5"), minimum_version="1.0", maximum_version="2.0"
        )
        self.assertTrue(result)


class CheckPythonModuleBugTest(CheckPythonModuleTestCase):
    """Tests that reveal defects in _CheckPythonModule.

    These tests are expected to FAIL against the current implementation.
    """

    def testTooRecentOptionalReportsMaximumVersion(self):
        """Tests the message for an optional module above the maximum version.

        Defect: the message prints the minimum version ("1.0 or earlier
        required") instead of the maximum version ("2.0 or earlier required"),
        unlike the message for required modules.
        """
        result, output, _ = self._Check(
            _StubModule(version="3.0"),
            minimum_version="1.0",
            maximum_version="2.0",
            is_required=False,
        )
        self.assertTrue(result)
        self.assertIn("is too recent, 2.0 or earlier required", output)

    def testSemanticVersionPreRelease(self):
        """Tests a semantic versioning pre-release version such as 1.0.0-beta.2.

        Defect: the suffix removal only drops the last component when it is not
        numeric. For "1.0.0-beta.2" the last component "2" is numeric, so
        "beta" stays in the list and int("beta") raises an uncaught ValueError
        instead of the check returning a result.
        """
        try:
            result, _, _ = self._Check(
                _StubModule(version="1.0.0-beta.2"), minimum_version="0.5"
            )
        except ValueError as exception:
            self.fail(f"_CheckPythonModule raised ValueError: {exception!s}")
        self.assertTrue(result)


class ImportPythonModuleTest(unittest.TestCase):
    """Tests for the _ImportPythonModule function."""

    # pylint: disable=protected-access

    def testImportExistingModule(self):
        """Tests importing a module that exists."""
        module_object = dependencies._ImportPythonModule("json")
        self.assertIsNotNone(module_object)
        self.assertEqual(module_object.__name__, "json")

    def testImportMissingModule(self):
        """Tests importing a module that does not exist."""
        module_object = dependencies._ImportPythonModule("plaso_no_such_module_xyz")
        self.assertIsNone(module_object)

    def testImportDottedModule(self):
        """Tests that a dotted name returns the innermost module."""
        module_object = dependencies._ImportPythonModule("os.path")
        self.assertIsNotNone(module_object)
        self.assertTrue(hasattr(module_object, "join"))

    def testImportErrorIsHandled(self):
        """Tests that an ImportError raised by __import__ is handled (mock)."""
        with mock.patch("builtins.__import__", side_effect=ImportError("boom")):
            module_object = dependencies._ImportPythonModule("json")
        self.assertIsNone(module_object)


class CheckDependenciesTest(unittest.TestCase):
    """Tests for the CheckDependencies function."""

    _TEST_DEPENDENCIES = {
        "zzz": ("__version__", "1.0", None, False),
        "aaa": ("get_version()", "2.0", "3.0", True),
    }

    def testAllDependenciesAvailable(self):
        """Tests the result and the calls when all checks pass (mock)."""
        output = io.StringIO()
        with (
            mock.patch.dict(
                dependencies.PYTHON_DEPENDENCIES, self._TEST_DEPENDENCIES, clear=True
            ),
            mock.patch(
                "plaso.dependencies._CheckPythonModule", return_value=True
            ) as mock_check,
            mock.patch("sys.stdout", output),
        ):
            result = dependencies.CheckDependencies(verbose_output=False)

        self.assertTrue(result)
        self.assertIn("[OK]", output.getvalue())

        # Dependencies must be checked in sorted order with the tuple values
        # mapped to the right keyword arguments.
        self.assertEqual(
            mock_check.call_args_list,
            [
                mock.call(
                    "aaa",
                    "get_version()",
                    "2.0",
                    is_required=True,
                    maximum_version="3.0",
                    verbose_output=False,
                ),
                mock.call(
                    "zzz",
                    "__version__",
                    "1.0",
                    is_required=False,
                    maximum_version=None,
                    verbose_output=False,
                ),
            ],
        )

    def testOneDependencyFails(self):
        """Tests that one failing check makes the overall result False."""
        output = io.StringIO()
        with (
            mock.patch.dict(
                dependencies.PYTHON_DEPENDENCIES, self._TEST_DEPENDENCIES, clear=True
            ),
            mock.patch(
                "plaso.dependencies._CheckPythonModule", side_effect=[False, True]
            ) as mock_check,
            mock.patch("sys.stdout", output),
        ):
            result = dependencies.CheckDependencies(verbose_output=False)

        self.assertFalse(result)
        # A failure must not stop the remaining checks.
        self.assertEqual(mock_check.call_count, 2)
        self.assertNotIn("[OK]", output.getvalue())

    def testVerboseOutputHasNoSummary(self):
        """Tests that verbose mode does not print the [OK] summary line."""
        output = io.StringIO()
        with (
            mock.patch.dict(
                dependencies.PYTHON_DEPENDENCIES, self._TEST_DEPENDENCIES, clear=True
            ),
            mock.patch("plaso.dependencies._CheckPythonModule", return_value=True),
            mock.patch("sys.stdout", output),
        ):
            result = dependencies.CheckDependencies(verbose_output=True)

        self.assertTrue(result)
        self.assertEqual(
            output.getvalue(), "Checking availability and versions of dependencies.\n\n"
        )


if __name__ == "__main__":
    unittest.main()
