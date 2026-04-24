# -*- coding: utf-8 -*-
import re

from plone import api
from zope.component import getMultiAdapter

from imio.omnia.assistant.interfaces import IOmniaAssistantAdapter
from imio.omnia.core.browser.proxy import OmniaOpenAIProxyView

_MCP_PATH_RE = re.compile(r"^/[^/]+/mcp(/.*)?$")


_SETTINGS_PREFIX = (
    "imio.omnia.assistant.browser.controlpanel.IOmniaAssistantSettings"
)


class OmniaAssistantOpenAIProxyView(OmniaOpenAIProxyView):
    """Assistant-specific OpenAI proxy with server-side prompt injection."""

    def _get_registry_record(self, key, default=None):
        try:
            return api.portal.get_registry_record(key)
        except (KeyError, api.exc.InvalidParameterError):
            return default

    def _get_assistant_adapter(self):
        return getMultiAdapter((self.context, self.request), IOmniaAssistantAdapter)

    def _is_proxy_enabled(self):
        return self._get_assistant_adapter().is_available()

    def _get_base_prompt(self):
        return self._get_assistant_adapter().get_system_prompt()

    def _get_max_messages_per_session(self):
        return (
            self._get_registry_record(
                f"{_SETTINGS_PREFIX}.max_messages_per_session", 0
            )
            or 0
        )

    def _validate_message_limit(self, body):
        max_messages = self._get_max_messages_per_session()
        if max_messages <= 0:
            return None

        messages = body.get("messages", [])
        user_messages_count = sum(
            1
            for message in messages
            if isinstance(message, dict) and message.get("role") == "user"
        )
        if user_messages_count <= max_messages:
            return None

        return self._json_error(
            400,
            "Maximum messages per conversation exceeded. "
            "Start a new conversation.",
        )

    def _inject_base_prompt(self, body):
        base_prompt = self._get_base_prompt()
        if not base_prompt:
            return body

        messages = body.get("messages", [])
        if not isinstance(messages, list):
            messages = []

        first_message = messages[0] if messages else None
        if (
            isinstance(first_message, dict)
            and first_message.get("role") == "system"
            and first_message.get("content") == base_prompt
        ):
            return body

        updated_body = dict(body)
        updated_body["messages"] = [
            {"role": "system", "content": base_prompt},
            *messages,
        ]
        return updated_body

    def _build_upstream_url(self, openai_url, path):
        """Route MCP paths to the LiteLLM root instead of under /v1."""
        if _MCP_PATH_RE.match(path):
            base = re.sub(r"/v1/?$", "", openai_url.rstrip("/"))
            return f"{base}{path}"
        return super()._build_upstream_url(openai_url, path)

    def _prepare_request_body(self, body):
        limit_error = self._validate_message_limit(body)
        if limit_error is not None:
            return body, limit_error
        return self._inject_base_prompt(body), None
