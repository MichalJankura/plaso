#!/usr/bin/env python3
"""Tests for the task merge helpers (plaso.multi_process.merge_helpers).

Test doubles used:
* fake: plaso.storage.fake.fake_store.FakeStore, a working in-memory attribute
  container store, replaces the SQLite task storage reader.
* mock: unittest.mock.MagicMock replaces the storage reader to verify which
  container types are requested, in which order, and that Close() is called.
"""

import unittest
from unittest import mock

from plaso.containers import events
from plaso.containers import reports
from plaso.containers import warnings
from plaso.multi_process import merge_helpers
from plaso.storage.fake import fake_store


class ExtractionTaskMergeHelperTest(unittest.TestCase):
    """Tests for the extraction task merge helper using a fake store."""

    def setUp(self):
        """Sets up a fake task store with extraction containers."""
        self._store = fake_store.FakeStore()
        self._store.Open()

        # Added in an order that differs from the required merge order.
        self._event_data = events.EventData(data_type="test:event")
        self._store.AddAttributeContainer(self._event_data)

        self._warning = warnings.ExtractionWarning(message="test warning")
        self._store.AddAttributeContainer(self._warning)

        self._event_data_stream = events.EventDataStream()
        self._store.AddAttributeContainer(self._event_data_stream)

    def tearDown(self):
        """Cleans up the fake store."""
        if self._store._is_open:  # pylint: disable=protected-access
            self._store.Close()

    def testInitialize(self):
        """Tests the initial state of the helper."""
        helper = merge_helpers.ExtractionTaskMergeHelper(self._store, "task1")
        self.assertEqual(helper.task_identifier, "task1")
        self.assertFalse(helper.fully_merged)

    def testGetAttributeContainerMergeOrder(self):
        """Tests that containers are returned in dependency order."""
        helper = merge_helpers.ExtractionTaskMergeHelper(self._store, "task1")

        container_types = []
        container = helper.GetAttributeContainer()
        while container:
            container_types.append(container.CONTAINER_TYPE)
            container = helper.GetAttributeContainer()

        # Event data streams must be merged before event data that reference
        # them and warnings come last.
        self.assertEqual(
            container_types,
            [
                events.EventDataStream.CONTAINER_TYPE,
                events.EventData.CONTAINER_TYPE,
                warnings.ExtractionWarning.CONTAINER_TYPE,
            ],
        )
        self.assertTrue(helper.fully_merged)

    def testFullyMergedOnlyAfterExhaustion(self):
        """Tests that fully_merged is set only after the last container."""
        helper = merge_helpers.ExtractionTaskMergeHelper(self._store, "task1")

        for _ in range(3):
            self.assertIsNotNone(helper.GetAttributeContainer())
            self.assertFalse(helper.fully_merged)

        self.assertIsNone(helper.GetAttributeContainer())
        self.assertTrue(helper.fully_merged)

        # Further calls keep returning None.
        self.assertIsNone(helper.GetAttributeContainer())

    def testEmptyStore(self):
        """Tests merging a task without containers."""
        empty_store = fake_store.FakeStore()
        empty_store.Open()
        helper = merge_helpers.ExtractionTaskMergeHelper(empty_store, "empty")

        self.assertIsNone(helper.GetAttributeContainer())
        self.assertTrue(helper.fully_merged)
        empty_store.Close()

    def testIdentifierMappings(self):
        """Tests Get/SetAttributeContainerIdentifier."""
        helper = merge_helpers.ExtractionTaskMergeHelper(self._store, "task1")
        identifier = self._event_data_stream.GetIdentifier()

        self.assertIsNone(helper.GetAttributeContainerIdentifier("stream:1"))

        helper.SetAttributeContainerIdentifier("stream:1", identifier)
        self.assertIs(helper.GetAttributeContainerIdentifier("stream:1"), identifier)

        # Overwriting a mapping replaces the previous value.
        helper.SetAttributeContainerIdentifier("stream:1", None)
        self.assertIsNone(helper.GetAttributeContainerIdentifier("stream:1"))

    def testClose(self):
        """Tests that Close closes the fake store and releases it."""
        helper = merge_helpers.ExtractionTaskMergeHelper(self._store, "task1")
        helper.Close()

        self.assertFalse(self._store._is_open)  # pylint: disable=protected-access
        self.assertIsNone(
            helper._task_storage_reader
        )  # pylint: disable=protected-access


class AnalysisTaskMergeHelperTest(unittest.TestCase):
    """Tests for the analysis task merge helper using a fake store."""

    def testGetAttributeContainer(self):
        """Tests that only analysis container types are merged."""
        store = fake_store.FakeStore()
        store.Open()
        store.AddAttributeContainer(reports.AnalysisReport(plugin_name="test"))
        store.AddAttributeContainer(events.EventTag())
        # Extraction containers must be ignored by the analysis helper.
        store.AddAttributeContainer(events.EventDataStream())

        helper = merge_helpers.AnalysisTaskMergeHelper(store, "task2")

        container_types = []
        container = helper.GetAttributeContainer()
        while container:
            container_types.append(container.CONTAINER_TYPE)
            container = helper.GetAttributeContainer()

        self.assertEqual(
            container_types,
            [events.EventTag.CONTAINER_TYPE, reports.AnalysisReport.CONTAINER_TYPE],
        )
        store.Close()


class BaseTaskMergeHelperMockTest(unittest.TestCase):
    """Tests for the merge helper interaction with a mocked storage reader."""

    def testLazyRetrieval(self):
        """Tests that the reader is not queried until a container is needed."""
        mock_reader = mock.MagicMock()
        merge_helpers.ExtractionTaskMergeHelper(mock_reader, "task1")
        mock_reader.GetAttributeContainers.assert_not_called()

    def testRequestsAllContainerTypesInOrder(self):
        """Tests that every container type is requested once, in order."""
        mock_reader = mock.MagicMock()
        mock_reader.GetAttributeContainers.return_value = iter([])

        helper = merge_helpers.ExtractionTaskMergeHelper(mock_reader, "task1")
        mock_reader.GetAttributeContainers.side_effect = lambda _: iter([])
        self.assertIsNone(helper.GetAttributeContainer())

        expected_calls = [
            mock.call(container_type)
            for container_type in merge_helpers.ExtractionTaskMergeHelper._CONTAINER_TYPES  # pylint: disable=protected-access
        ]
        self.assertEqual(
            mock_reader.GetAttributeContainers.call_args_list, expected_calls
        )

    def testBaseHelperHasNoContainerTypes(self):
        """Tests that the base helper merges nothing and never queries."""
        mock_reader = mock.MagicMock()
        helper = merge_helpers.BaseTaskMergeHelper(mock_reader, "task0")

        self.assertIsNone(helper.GetAttributeContainer())
        self.assertTrue(helper.fully_merged)
        mock_reader.GetAttributeContainers.assert_not_called()

    def testCloseCallsReaderClose(self):
        """Tests that Close delegates to the reader exactly once."""
        mock_reader = mock.MagicMock()
        helper = merge_helpers.AnalysisTaskMergeHelper(mock_reader, "task2")
        helper.Close()
        mock_reader.Close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
