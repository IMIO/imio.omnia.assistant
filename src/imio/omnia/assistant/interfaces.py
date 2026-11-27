# -*- coding: utf-8 -*-
from zope.interface import Interface
from zope.publisher.interfaces.browser import IDefaultBrowserLayer


class IImioOmniaAssistantLayer(IDefaultBrowserLayer):
    """Marker interface that defines a browser layer."""


class IOmniaAssistantAdapter(Interface):
    """Expose assistant availability, prompt and frontend overrides."""

    def is_available():
        """Return True when the assistant should be exposed and callable."""

    def get_system_prompt():
        """Return the server-side system prompt prepended to conversations."""

    def get_mcp_server_urls():
        """Return the MCP servers the assistant may use, as {name: endpoint URL}."""

    def is_tracing_enabled():
        """Return True when the widget's replies are traced in Langfuse."""

    def get_config():
        """Return frontend runtime config overrides as a dict."""
