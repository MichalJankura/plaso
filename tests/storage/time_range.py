#!/usr/bin/env python3
"""Tests for the storage time range object."""

import unittest

from plaso.storage import time_range


class TimeRangeTest(unittest.TestCase):
    """Tests for the TimeRange object."""

    def testInitialize(self):
        """Tests a valid time range."""
        range_object = time_range.TimeRange(1000000, 3000000)
        self.assertEqual(range_object.start_timestamp, 1000000)
        self.assertEqual(range_object.end_timestamp, 3000000)
        self.assertEqual(range_object.duration, 2000000)

    def testZeroDuration(self):
        """Tests a time range where start equals end."""
        range_object = time_range.TimeRange(5, 5)
        self.assertEqual(range_object.duration, 0)

    def testNegativeTimestamps(self):
        """Tests a time range before the POSIX epoch."""
        range_object = time_range.TimeRange(-2000, -1000)
        self.assertEqual(range_object.duration, 1000)

    def testStartAfterEnd(self):
        """Tests that a start later than the end raises ValueError."""
        with self.assertRaises(ValueError):
            time_range.TimeRange(10, 5)

    def testMissingTimestamps(self):
        """Tests that a missing start or end raises ValueError."""
        with self.assertRaises(ValueError):
            time_range.TimeRange(None, 5)
        with self.assertRaises(ValueError):
            time_range.TimeRange(5, None)
        with self.assertRaises(ValueError):
            time_range.TimeRange(None, None)

    def testZeroIsAValidTimestamp(self):
        """Tests that 0 (the epoch) is not treated as a missing value."""
        range_object = time_range.TimeRange(0, 0)
        self.assertEqual(range_object.start_timestamp, 0)


if __name__ == "__main__":
    unittest.main()
