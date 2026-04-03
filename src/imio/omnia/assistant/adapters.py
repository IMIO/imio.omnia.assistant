# -*- coding: utf-8 -*-
from plone import api
from zope.component import adapter
from zope.interface import Interface
from zope.interface import implementer
from zope.publisher.interfaces.browser import IBrowserRequest

from imio.omnia.assistant.interfaces import IOmniaAssistantAdapter
from imio.omnia.core.tokens import generate_token


_SETTINGS_PREFIX = (
    "imio.omnia.assistant.browser.controlpanel.IOmniaAssistantSettings"
)


@adapter(Interface, IBrowserRequest)
@implementer(IOmniaAssistantAdapter)
class OmniaAssistantAdapter:
    """Default assistant configuration hook.

    Product add-ons can register more specific multi-adapters to override
    assistant availability, server-side prompt and frontend initialization
    settings.
    """

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def _get_registry_record(self, key, default=None):
        try:
            return api.portal.get_registry_record(key)
        except (KeyError, api.exc.InvalidParameterError):
            return default

    def is_available(self):
        return self._get_registry_record(f"{_SETTINGS_PREFIX}.enabled", True)

    def get_system_prompt(self):
        return self._get_registry_record(f"{_SETTINGS_PREFIX}.base_prompt", "")

    def _get_registry_config(self):
        config = {
            "model": self._get_registry_record(f"{_SETTINGS_PREFIX}.model", ""),
            "include_page_content": self._get_registry_record(
                f"{_SETTINGS_PREFIX}.include_page_content", True
            ),
            "page_content_selector": self._get_registry_record(
                f"{_SETTINGS_PREFIX}.page_content_selector", "#content"
            ),
            "page_content_clean": self._get_registry_record(
                f"{_SETTINGS_PREFIX}.page_content_clean", False
            ),
            "max_context_chars": self._get_registry_record(
                f"{_SETTINGS_PREFIX}.max_context_chars", 20000
            ),
            "max_messages_per_session": self._get_registry_record(
                f"{_SETTINGS_PREFIX}.max_messages_per_session", 0
            ),
            "mode": self._get_registry_record(f"{_SETTINGS_PREFIX}.mode", "floating"),
            "initial_width": self._get_registry_record(
                f"{_SETTINGS_PREFIX}.initial_width", 380
            ),
            "initial_height": self._get_registry_record(
                f"{_SETTINGS_PREFIX}.initial_height", 520
            ),
        }
        disclaimer = self._get_registry_record(f"{_SETTINGS_PREFIX}.disclaimer")
        if disclaimer:
            config["disclaimer"] = disclaimer
        return config

    def _merge_config(self, config, overrides):
        if not overrides:
            return config
        merged = dict(config)
        merged.update(overrides)
        return merged

    def _get_config_overrides(self):
        return {}

    def get_config(self):
        if not self.is_available():
            return None

        config = self._get_registry_config()
        config = self._merge_config(config, self._get_config_overrides())
        config["api_service_url"] = (
            f"{self.context.absolute_url()}/@@omnia-assistant-api"
        )
        config["api_key"] = generate_token(api.portal.get().absolute_url())
        return config
