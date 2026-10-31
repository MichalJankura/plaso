#!/usr/bin/env python3
"""Tests for the function decorators."""

import unittest
import warnings

from plaso.lib import decorators


@decorators.deprecated
def _OldFunction(value, multiplier=2):
    """Old function docstring."""
    return value * multiplier


class DeprecatedDecoratorTest(unittest.TestCase):
    """Tests for the deprecated decorator."""

    def testIssuesDeprecationWarning(self):
        """Tests that calling the function issues a DeprecationWarning."""
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always")
            _OldFunction(1)

        self.assertEqual(len(caught_warnings), 1)
        self.assertIs(caught_warnings[0].category, DeprecationWarning)
        self.assertEqual(
            str(caught_warnings[0].message),
            "Call to deprecated function: _OldFunction.",
        )

    def testWarningPointsToCaller(self):
        """Tests that stacklevel=2 attributes the warning to the caller."""
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always")
            _OldFunction(1)

        self.assertEqual(caught_warnings[0].filename, __file__)

    def testPassesArgumentsAndReturnsResult(self):
        """Tests that positional and keyword arguments are passed through."""
        with warnings.catch_warnings(record=True):
            self.assertEqual(_OldFunction(3), 6)
            self.assertEqual(_OldFunction(3, multiplier=4), 12)

    def testPreservesMetadata(self):
        """Tests that the name and docstring are preserved."""
        self.assertEqual(_OldFunction.__name__, "_OldFunction")
        self.assertEqual(_OldFunction.__doc__, "Old function docstring.")

    def testCopiesFunctionAttributes(self):
        """Tests that attributes set on the original function are copied."""

        def _Function():
            """Function."""

        _Function.marker = 42
        wrapped = decorators.deprecated(_Function)
        self.assertEqual(wrapped.marker, 42)


class DeprecatedDecoratorBugTest(unittest.TestCase):
    """Tests that reveal defects in the deprecated decorator.

    These tests are expected to FAIL against the current implementation.
    """

    def testRespectsCallerWarningFilters(self):
        """Tests that the caller can silence the deprecation warning.

        Defect: the wrapper calls warnings.simplefilter("default", ...) on every
        call, which inserts a filter in front of the caller's filters. A caller
        that ignores DeprecationWarning (for example a test runner or a library
        user) still gets the warning and its warning filters are modified.
        """
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("ignore")
            filters_before = list(warnings.filters)
            _OldFunction(1)
            filters_after = list(warnings.filters)

        self.assertEqual(caught_warnings, [])
        self.assertEqual(filters_before, filters_after)


if __name__ == "__main__":
    unittest.main()
