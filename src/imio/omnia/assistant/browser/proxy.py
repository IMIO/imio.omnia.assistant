# -*- coding: utf-8 -*-

import logging
from urllib.parse import urlparse

import httpx2
from plone import api
from plone.protect.authenticator import check as check_csrf
from plone.protect.interfaces import IDisableCSRFProtection
from zExceptions import Forbidden
from zope.component import getMultiAdapter
from zope.interface import alsoProvides

from imio.omnia.assistant.interfaces import IOmniaAssistantAdapter
from imio.omnia.core import oauth
from imio.omnia.core.browser.proxy import OmniaOpenAIProxyView
from imio.omnia.core.interfaces import IOmniaOpenAIService


logger = logging.getLogger(__name__)

_SETTINGS_PREFIX = (
    "imio.omnia.assistant.browser.controlpanel.IOmniaAssistantSettings"
)
# Tool calls such as image generation can take a while.
_MCP_TIMEOUT = 120.0
_MCP_SESSION_HEADER = "Mcp-Session-Id"


def _is_imio_host(url):
    host = urlparse(url).hostname or ""
    return host == "imio.be" or host.endswith(".imio.be")


class OmniaAssistantOpenAIProxyView(OmniaOpenAIProxyView):
    """Assistant-specific OpenAI proxy with server-side prompt injection.

    Also relays the widget's MCP requests: ``{name}/mcp`` goes to the
    endpoint URL of the selected MCP server ``name``.
    """

    def __call__(self):
        if self._get_mcp_server_name() is None:
            return super().__call__()
        return self._proxy_mcp_request()

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

    def _prepare_request_body(self, body):
        limit_error = self._validate_message_limit(body)
        if limit_error is not None:
            return body, limit_error
        return self._inject_base_prompt(body), None

    # --- MCP relay ---

    def _get_mcp_server_name(self):
        """Return the server name of a ``{name}/mcp`` request, else None."""
        if len(self._path_segments) == 2 and self._path_segments[1] == "mcp":
            return self._path_segments[0]
        return None

    def _check_access(self):
        """The base proxy's gates: Origin, CSRF token, assistant enabled."""
        origin = self.request.getHeader("Origin")
        if origin:
            portal_url = api.portal.get().absolute_url()
            if urlparse(origin).netloc != urlparse(portal_url).netloc:
                return self._json_error(403, "Origin not allowed")
        try:
            check_csrf(self.request)
        except Forbidden:
            return self._json_error(403, "Invalid CSRF token")
        if not self._is_proxy_enabled():
            return self._json_error(404, "Not found")
        return None

    def _proxy_mcp_request(self):
        # The CSRF token is checked explicitly in _check_access, as in the base proxy.
        alsoProvides(self.request, IDisableCSRFProtection)
        error = self._check_access()
        if error is not None:
            return error

        name = self._get_mcp_server_name()
        url = self._get_assistant_adapter().get_mcp_server_urls().get(name)
        if not url:
            return self._json_error(404, "Unknown MCP server")

        # JSON-RPC: no prompt injection nor message limit here.
        body, error = self._read_json_body()
        if error is not None:
            return error

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        session_id = self.request.getHeader(_MCP_SESSION_HEADER)
        if session_id:
            headers[_MCP_SESSION_HEADER] = session_id

        try:
            upstream = self._send_mcp_request(url, headers, body)
        except Exception:
            logger.exception("MCP proxy error for server %s", name)
            return self._json_error(502, "Upstream MCP error")

        if upstream.status_code >= 400:
            logger.warning(
                "MCP proxy upstream HTTP %s from server %s: %s",
                upstream.status_code,
                name,
                upstream.text[:500],
            )
        response = self.request.response
        response.setStatus(upstream.status_code)
        # The widget reads plain JSON as well as a single SSE event.
        response.setHeader(
            "Content-Type", upstream.headers.get("content-type", "application/json")
        )
        if upstream.headers.get(_MCP_SESSION_HEADER):
            response.setHeader(_MCP_SESSION_HEADER, upstream.headers[_MCP_SESSION_HEADER])
        return upstream.text

    def _send_mcp_request(self, url, headers, body):
        """POST to the MCP server; the Omnia credentials only go to iMio hosts."""
        if _is_imio_host(url):
            service = getMultiAdapter(
                (self.context, self.request), IOmniaOpenAIService
            )
            headers = {**service._headers(), **headers}
            if service._use_oauth():
                return oauth.get_oauth_client().request(
                    "POST", url, headers=headers, json=body, timeout=_MCP_TIMEOUT
                )
        return httpx2.request(
            "POST", url, headers=headers, json=body, timeout=_MCP_TIMEOUT
        )
