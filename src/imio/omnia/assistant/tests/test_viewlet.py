# -*- coding: utf-8 -*-
"""Tests for assistant config viewlet generation."""
import json
import unittest
from unittest.mock import patch

from plone import api
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID

from imio.omnia.assistant.testing import IMIO_OMNIA_ASSISTANT_INTEGRATION_TESTING


class DummyOmniaAssistantAdapter:
    def __init__(self, available=True, system_prompt="", config=None):
        self.available = available
        self.system_prompt = system_prompt
        self.config = config or {}

    def is_available(self):
        return self.available

    def get_system_prompt(self):
        return self.system_prompt

    def get_config(self):
        if not self.available:
            return None
        return self.config


class TestOmniaAssistantConfigViewlet(unittest.TestCase):
    layer = IMIO_OMNIA_ASSISTANT_INTEGRATION_TESTING

    PREFIX = (
        "imio.omnia.assistant.browser.controlpanel.IOmniaAssistantSettings"
    )

    def setUp(self):
        self.portal = self.layer["portal"]
        self.request = self.layer["request"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])

    def _make_viewlet(self):
        from imio.omnia.assistant.browser.viewlets import (
            OmniaAssistantConfigViewlet,
        )

        return OmniaAssistantConfigViewlet(
            self.portal, self.request, None, None
        )

    def _get_config(self):
        payload = self._make_viewlet().config_json()
        if payload is None:
            return None
        return json.loads(payload)

    def _registry_getter(self, **overrides):
        values = {
            f"{self.PREFIX}.enabled": True,
            f"{self.PREFIX}.model": "",
            f"{self.PREFIX}.base_prompt": None,
            f"{self.PREFIX}.include_page_content": True,
            f"{self.PREFIX}.page_content_selector": "#content",
            f"{self.PREFIX}.page_content_clean": False,
            f"{self.PREFIX}.max_context_chars": 20000,
            f"{self.PREFIX}.max_messages_per_session": 0,
            f"{self.PREFIX}.mode": "floating",
            f"{self.PREFIX}.initial_width": 380,
            f"{self.PREFIX}.initial_height": 520,
            f"{self.PREFIX}.disclaimer": None,
        }
        values.update(overrides)

        def _get(key):
            if key not in values:
                raise KeyError(key)
            return values[key]

        return _get

    def test_available_returns_false_when_disabled(self):
        api.portal.set_registry_record(f"{self.PREFIX}.enabled", False)

        self.assertFalse(self._make_viewlet().available())

    def test_config_json_returns_none_when_disabled(self):
        api.portal.set_registry_record(f"{self.PREFIX}.enabled", False)

        self.assertIsNone(self._make_viewlet().config_json())

    @patch("imio.omnia.assistant.browser.viewlets.getMultiAdapter")
    def test_available_returns_false_when_adapter_marks_assistant_unavailable(
        self, mock_get_multi_adapter
    ):
        mock_get_multi_adapter.return_value = DummyOmniaAssistantAdapter(
            available=False
        )

        self.assertFalse(self._make_viewlet().available())

    @patch("imio.omnia.assistant.browser.viewlets.getMultiAdapter")
    def test_config_json_returns_none_when_adapter_marks_assistant_unavailable(
        self, mock_get_multi_adapter
    ):
        mock_get_multi_adapter.return_value = DummyOmniaAssistantAdapter(
            available=False
        )

        self.assertIsNone(self._make_viewlet().config_json())

    @patch("imio.omnia.assistant.adapters.generate_token")
    def test_config_json_uses_registry_values_and_defaults(self, mock_token):
        mock_token.return_value = "signed-token"
        with patch(
            "imio.omnia.assistant.adapters.api.portal.get_registry_record",
            side_effect=self._registry_getter(
                **{
                    f"{self.PREFIX}.model": "gpt-4.1-mini",
                    f"{self.PREFIX}.base_prompt": "Stay concise.",
                    f"{self.PREFIX}.disclaimer": (
                        "Generated content may contain errors."
                    ),
                    f"{self.PREFIX}.max_messages_per_session": 5,
                }
            ),
        ):
            config = self._get_config()

        self.assertEqual(
            config["api_service_url"],
            f"{self.portal.absolute_url()}/@@omnia-assistant-api",
        )
        self.assertEqual(config["api_key"], "signed-token")
        self.assertEqual(config["model"], "gpt-4.1-mini")
        self.assertNotIn("base_prompt", config)
        self.assertEqual(
            config["disclaimer"], "Generated content may contain errors."
        )
        self.assertTrue(config["include_page_content"])
        self.assertEqual(config["page_content_selector"], "#content")
        self.assertFalse(config["page_content_clean"])
        self.assertEqual(config["max_context_chars"], 20000)
        self.assertEqual(config["max_messages_per_session"], 5)
        self.assertEqual(config["mode"], "floating")
        self.assertEqual(config["initial_width"], 380)
        self.assertEqual(config["initial_height"], 520)
        mock_token.assert_called_once_with(self.portal.absolute_url())

    @patch("imio.omnia.assistant.adapters.generate_token")
    def test_optional_fields_are_omitted_when_empty(self, mock_token):
        mock_token.return_value = "signed-token"
        with patch(
            "imio.omnia.assistant.adapters.api.portal.get_registry_record",
            side_effect=self._registry_getter(
                **{
                    f"{self.PREFIX}.model": "gpt-4.1-mini",
                    f"{self.PREFIX}.base_prompt": "",
                    f"{self.PREFIX}.disclaimer": "",
                }
            ),
        ):
            config = self._get_config()

        self.assertNotIn("base_prompt", config)
        self.assertNotIn("disclaimer", config)

    @patch("imio.omnia.assistant.adapters.generate_token")
    def test_config_json_serializes_config(self, mock_token):
        mock_token.return_value = "signed-token"
        with patch(
            "imio.omnia.assistant.adapters.api.portal.get_registry_record",
            side_effect=self._registry_getter(
                **{f"{self.PREFIX}.model": "gpt-4.1-mini"}
            ),
        ):
            payload = self._make_viewlet().config_json()

        self.assertEqual(json.loads(payload)["api_key"], "signed-token")

    @patch("imio.omnia.assistant.browser.viewlets.getMultiAdapter")
    def test_config_json_exposes_adapter_frontend_keys(
        self, mock_get_multi_adapter
    ):
        mock_get_multi_adapter.return_value = DummyOmniaAssistantAdapter(
            config={
                "api_key": "signed-token",
                "api_service_url": (
                    f"{self.portal.absolute_url()}/@@omnia-assistant-api"
                ),
                "model": "gpt-4.1-mini",
                "welcome_message": "Bonjour depuis l'addon.",
                "suggestions": [{"prompt": "Resumer cette page"}],
                "system_messages": ["Contexte additionnel."],
            }
        )
        config = self._get_config()

        self.assertEqual(config["api_key"], "signed-token")
        self.assertEqual(config["model"], "gpt-4.1-mini")
        self.assertEqual(config["welcome_message"], "Bonjour depuis l'addon.")
        self.assertEqual(
            config["suggestions"], [{"prompt": "Resumer cette page"}]
        )
        self.assertEqual(config["system_messages"], ["Contexte additionnel."])
