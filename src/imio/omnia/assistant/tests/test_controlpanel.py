# -*- coding: utf-8 -*-
"""Tests for assistant control-panel helpers."""
import unittest
from unittest.mock import MagicMock
from unittest.mock import patch

from imio.omnia.assistant.browser.controlpanel import (
    OmniaModelsVocabularyFactory,
)


class TestOmniaModelsVocabularyFactory(unittest.TestCase):
    def test_returns_models_from_service(self):
        service = MagicMock()
        service.list_models.return_value = {
            "data": [{"id": "gpt-4.1-mini"}, {"id": "gpt-4.1"}]
        }

        with patch(
            "imio.omnia.assistant.browser.controlpanel.api.portal.get",
            return_value=object(),
        ), patch(
            "imio.omnia.assistant.browser.controlpanel.getRequest",
            return_value=object(),
        ), patch(
            "imio.omnia.assistant.browser.controlpanel.getMultiAdapter",
            return_value=service,
        ):
            vocabulary = OmniaModelsVocabularyFactory()(None)

        self.assertEqual(
            [term.value for term in vocabulary],
            ["gpt-4.1-mini", "gpt-4.1"],
        )

    def test_falls_back_to_current_registry_value_when_service_fails(self):
        with patch(
            "imio.omnia.assistant.browser.controlpanel.api.portal.get",
            return_value=object(),
        ), patch(
            "imio.omnia.assistant.browser.controlpanel.getRequest",
            return_value=object(),
        ), patch(
            "imio.omnia.assistant.browser.controlpanel.getMultiAdapter",
            side_effect=RuntimeError("boom"),
        ), patch(
            "imio.omnia.assistant.browser.controlpanel.api.portal.get_registry_record",
            return_value="saved-model",
        ), patch(
            "imio.omnia.assistant.browser.controlpanel.logger.error"
        ) as mock_error:
            vocabulary = OmniaModelsVocabularyFactory()(None)

        self.assertEqual([term.value for term in vocabulary], ["saved-model"])
        mock_error.assert_called_once()

    def test_returns_empty_vocabulary_when_no_models_are_available(self):
        service = MagicMock()
        service.list_models.return_value = {"data": []}

        with patch(
            "imio.omnia.assistant.browser.controlpanel.api.portal.get",
            return_value=object(),
        ), patch(
            "imio.omnia.assistant.browser.controlpanel.getRequest",
            return_value=object(),
        ), patch(
            "imio.omnia.assistant.browser.controlpanel.getMultiAdapter",
            return_value=service,
        ), patch(
            "imio.omnia.assistant.browser.controlpanel.api.portal.get_registry_record",
            return_value=None,
        ):
            vocabulary = OmniaModelsVocabularyFactory()(None)

        self.assertEqual(list(vocabulary), [])
