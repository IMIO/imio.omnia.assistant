# -*- coding: utf-8 -*-
from imio.omnia.assistant.browser.controlpanel import MCP_SERVERS
from imio.omnia.assistant.interfaces import IOmniaAssistantAdapter
from plone import api
from plone.protect.authenticator import createToken
from zope.component import adapter
from zope.interface import implementer
from zope.interface import Interface
from zope.publisher.interfaces.browser import IBrowserRequest


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
        if not self._get_registry_record(f"{_SETTINGS_PREFIX}.enabled", False):
            return False
        visible_to = self._get_registry_record(f"{_SETTINGS_PREFIX}.visible_to")
        if visible_to == "authenticated":
            return not api.user.is_anonymous()
        return True

    def get_system_prompt(self):
        return self._get_registry_record(f"{_SETTINGS_PREFIX}.base_prompt", "")

    def is_tracing_enabled(self):
        return bool(self._get_registry_record(f"{_SETTINGS_PREFIX}.tracing", False))

    def get_mcp_server_urls(self):
        """Map the selected MCP server names to their endpoint URLs.

        Empty without an MCP URL. A selected server no longer offered by the
        package is dropped.
        """
        base_url = (self._get_registry_record(f"{_SETTINGS_PREFIX}.mcp_url") or "").strip().rstrip("/")
        if not base_url:
            return {}
        selected = self._get_registry_record(f"{_SETTINGS_PREFIX}.mcp_servers", []) or []
        return {name: f"{base_url}/{name}/mcp" for name in selected if name in MCP_SERVERS}

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
            "layout": self._get_registry_record(
                f"{_SETTINGS_PREFIX}.layout", "floating"
            ),
            "initial_width": self._get_registry_record(
                f"{_SETTINGS_PREFIX}.initial_width", 380
            ),
            "initial_height": self._get_registry_record(
                f"{_SETTINGS_PREFIX}.initial_height", 520
            ),
            # Names only: the widget calls @@omnia-assistant-api/{name}/mcp and
            # the proxy resolves the URL server-side.
            "mcp_servers": list(self.get_mcp_server_urls()),
            # The widget then posts its spans to @@omnia-assistant-api/traces.
            "tracing": self.is_tracing_enabled(),
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
        # The widget (>= 2.9) adds these headers to its chat and MCP requests.
        config["request_headers"] = {
            **config.get("request_headers", {}),
            "X-CSRF-TOKEN": createToken(),
        }
        return config
