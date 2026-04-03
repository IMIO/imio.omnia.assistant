# -*- coding: utf-8 -*-
"""Tests for OmniaAssistantOpenAIProxyView and SSEStreamIterator."""
import json
import unittest
from unittest.mock import MagicMock, patch

import httpx
from plone import api
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from ZPublisher.Iterators import IUnboundStreamIterator
from zope.component import getMultiAdapter

from imio.omnia.core.browser.proxy import SSEStreamIterator
from imio.omnia.assistant.browser.proxy import OmniaAssistantOpenAIProxyView
from imio.omnia.core.tokens import generate_token
from imio.omnia.assistant.testing import IMIO_OMNIA_ASSISTANT_INTEGRATION_TESTING

_UPSTREAM_URL = "https://api.example.com"
_SETTINGS_PREFIX = (
    "imio.omnia.assistant.browser.controlpanel.IOmniaAssistantSettings"
)


class DummyOmniaAssistantAdapter:
    def __init__(self, available=True, system_prompt=""):
        self.available = available
        self.system_prompt = system_prompt

    def is_available(self):
        return self.available

    def get_system_prompt(self):
        return self.system_prompt


class TestOmniaAssistantOpenAIProxyView(unittest.TestCase):
    """Test OmniaAssistantOpenAIProxyView security gates and request shaping.

    Security gates (in order):
      1. Origin header: if present, must match the portal's domain → 403
      2. Bearer token: must be present → 401; must be valid HMAC → 403
      3. assistant must be enabled → 404
      4. openai_api_url: must be non-empty → 503
      5. Request body: must be valid JSON → 400

    All Plone machinery (registry, tokens, component lookup) runs for real.
    Only httpx and getMultiAdapter are mocked for upstream tests.
    """

    layer = IMIO_OMNIA_ASSISTANT_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        self.request = self.layer["request"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        api.portal.set_registry_record(f"{_SETTINGS_PREFIX}.enabled", True)
        api.portal.set_registry_record(
            f"{_SETTINGS_PREFIX}.max_messages_per_session", 0
        )
        api.portal.set_registry_record(f"{_SETTINGS_PREFIX}.base_prompt", "")
        # Clean up any auth state from a previous test.
        self.request._auth = ""
        self.request.environ.pop("HTTP_ORIGIN", None)

    def _make_view(self, body=None, with_auth=True, path_segments=None):
        """Instantiate OmniaAssistantOpenAIProxyView directly."""
        self.request.BODY = body if body is not None else b""
        if with_auth:
            token = generate_token(self.portal.absolute_url())
            self.request._auth = f"Bearer {token}"
        else:
            self.request._auth = ""
        view = OmniaAssistantOpenAIProxyView(self.portal, self.request)
        for seg in path_segments or []:
            view.publishTraverse(self.request, seg)
        return view

    def _mock_service(self, mock_adapter):
        """Configure a mock IOmniaOpenAIService that returns empty headers."""
        svc = MagicMock()
        svc._headers.return_value = {}
        mock_adapter.return_value = svc

    def test_view_reachable_with_browser_layer(self):
        """The assistant proxy is registered under the new endpoint name."""
        view = getMultiAdapter(
            (self.portal, self.request), name="omnia-assistant-api"
        )
        self.assertIsInstance(view, OmniaAssistantOpenAIProxyView)

    # --- Origin check (gate 1) ---

    def test_mismatched_origin_returns_403(self):
        """A cross-origin request whose domain doesn't match the portal returns 403."""
        self.request.environ["HTTP_ORIGIN"] = "https://evil.example.com"
        view = self._make_view()
        result = json.loads(view())
        self.assertEqual(self.request.response.getStatus(), 403)
        self.assertEqual(result, {"error": "Origin not allowed"})

    def test_matching_origin_passes_through(self):
        """A same-origin request passes the origin check and reaches the next gate."""
        from urllib.parse import urlparse
        portal_url = self.portal.absolute_url()
        scheme = urlparse(portal_url).scheme
        netloc = urlparse(portal_url).netloc
        self.request.environ["HTTP_ORIGIN"] = f"{scheme}://{netloc}"
        # Next gate: upstream URL missing → 503
        view = self._make_view()
        view()
        self.assertEqual(self.request.response.getStatus(), 503)

    def test_no_origin_header_skips_origin_check(self):
        """Requests without an Origin header bypass the origin check entirely."""
        # No HTTP_ORIGIN in environ; next gate: upstream URL missing → 503
        view = self._make_view()
        view()
        self.assertEqual(self.request.response.getStatus(), 503)

    # --- Bearer token check (gate 2) ---

    def test_missing_auth_header_returns_401(self):
        """A request without an Authorization header returns 401."""
        view = self._make_view(with_auth=False)
        result = json.loads(view())
        self.assertEqual(self.request.response.getStatus(), 401)
        self.assertEqual(result, {"error": "Missing authorization"})

    def test_malformed_bearer_returns_401(self):
        """An Authorization header that doesn't start with 'Bearer ' returns 401."""
        self.request._auth = "Basic dXNlcjpwYXNz"
        view = OmniaAssistantOpenAIProxyView(self.portal, self.request)
        result = json.loads(view())
        self.assertEqual(self.request.response.getStatus(), 401)
        self.assertEqual(result, {"error": "Missing authorization"})

    def test_invalid_token_returns_403(self):
        """A Bearer token that fails HMAC validation returns 403."""
        self.request._auth = "Bearer 9999999999:deadbeef"
        view = OmniaAssistantOpenAIProxyView(self.portal, self.request)
        result = json.loads(view())
        self.assertEqual(self.request.response.getStatus(), 403)
        self.assertEqual(result, {"error": "Invalid or expired token"})

    # --- assistant availability (gate 3) ---

    def test_proxy_disabled_returns_404(self):
        """When the default adapter sees the assistant as disabled, return 404."""
        api.portal.set_registry_record(f"{_SETTINGS_PREFIX}.enabled", False)
        view = self._make_view()
        result = json.loads(view())
        self.assertEqual(self.request.response.getStatus(), 404)
        self.assertEqual(result, {"error": "Not found"})

    @patch("imio.omnia.assistant.browser.proxy.getMultiAdapter")
    def test_proxy_returns_404_when_adapter_marks_assistant_unavailable(
        self, mock_adapter
    ):
        """Adapter availability rules can hide the assistant proxy."""
        mock_adapter.return_value = DummyOmniaAssistantAdapter(available=False)

        view = self._make_view()
        result = json.loads(view())

        self.assertEqual(self.request.response.getStatus(), 404)
        self.assertEqual(result, {"error": "Not found"})

    # --- OpenAI URL not configured (gate 4) ---

    def test_missing_openai_url_returns_503(self):
        """When openai_api_url is empty the view returns 503."""
        with patch(
            "imio.omnia.core.browser.proxy.get_openai_api_url", return_value=""
        ):
            view = self._make_view()
            result = json.loads(view())
        self.assertEqual(self.request.response.getStatus(), 503)
        self.assertEqual(result, {"error": "OpenAI API URL not configured"})

    # --- Body validation (gate 5) ---

    def test_invalid_json_body_returns_400(self):
        """A non-JSON request body returns 400."""
        with patch(
            "imio.omnia.core.browser.proxy.get_openai_api_url",
            return_value=_UPSTREAM_URL,
        ):
            view = self._make_view(body=b"not-json")
            result = json.loads(view())
        self.assertEqual(self.request.response.getStatus(), 400)
        self.assertEqual(result, {"error": "Invalid JSON body"})

    def test_empty_body_returns_400(self):
        """An empty request body returns 400."""
        with patch(
            "imio.omnia.core.browser.proxy.get_openai_api_url",
            return_value=_UPSTREAM_URL,
        ):
            view = self._make_view(body=b"")
            json.loads(view())
        self.assertEqual(self.request.response.getStatus(), 400)

    def test_message_limit_is_not_enforced_when_unlimited(self):
        """A zero message limit keeps the proxy behavior unchanged."""
        api.portal.set_registry_record(
            f"{_SETTINGS_PREFIX}.max_messages_per_session", 0
        )
        payload = json.dumps(
            {
                "stream": False,
                "messages": [
                    {"role": "user", "content": "one"},
                    {"role": "assistant", "content": "two"},
                    {"role": "user", "content": "three"},
                ],
            }
        ).encode()

        with patch(
            "imio.omnia.core.browser.proxy.get_openai_api_url",
            return_value=_UPSTREAM_URL,
        ), patch(
            "imio.omnia.core.browser.proxy.getMultiAdapter"
        ) as mock_adapter, patch(
            "imio.omnia.core.browser.proxy.httpx.request",
            return_value=MagicMock(status_code=200, text="{}"),
        ):
            self._mock_service(mock_adapter)
            self._make_view(body=payload)()

        self.assertEqual(self.request.response.getStatus(), 200)

    def test_message_limit_allows_requests_up_to_configured_count(self):
        """Requests with exactly the configured number of user messages still pass."""
        api.portal.set_registry_record(
            f"{_SETTINGS_PREFIX}.max_messages_per_session", 2
        )
        payload = json.dumps(
            {
                "stream": False,
                "messages": [
                    {"role": "system", "content": "context"},
                    {"role": "user", "content": "one"},
                    {"role": "assistant", "content": "reply"},
                    {"role": "user", "content": "two"},
                ],
            }
        ).encode()

        with patch(
            "imio.omnia.core.browser.proxy.get_openai_api_url",
            return_value=_UPSTREAM_URL,
        ), patch(
            "imio.omnia.core.browser.proxy.getMultiAdapter"
        ) as mock_adapter, patch(
            "imio.omnia.core.browser.proxy.httpx.request",
            return_value=MagicMock(status_code=200, text="{}"),
        ):
            self._mock_service(mock_adapter)
            self._make_view(body=payload)()

        self.assertEqual(self.request.response.getStatus(), 200)

    def test_message_limit_rejects_requests_beyond_configured_count(self):
        """Requests with too many user messages are rejected before reaching upstream."""
        api.portal.set_registry_record(
            f"{_SETTINGS_PREFIX}.max_messages_per_session", 2
        )
        payload = json.dumps(
            {
                "stream": False,
                "messages": [
                    {"role": "user", "content": "one"},
                    {"role": "assistant", "content": "reply"},
                    {"role": "user", "content": "two"},
                    {"role": "assistant", "content": "reply"},
                    {"role": "user", "content": "three"},
                ],
            }
        ).encode()

        with patch(
            "imio.omnia.core.browser.proxy.get_openai_api_url",
            return_value=_UPSTREAM_URL,
        ), patch("imio.omnia.core.browser.proxy.httpx.request") as mock_request:
            result = json.loads(self._make_view(body=payload)())

        self.assertEqual(self.request.response.getStatus(), 400)
        self.assertEqual(
            result,
            {
                "error": (
                    "Maximum messages per conversation exceeded. "
                    "Start a new conversation."
                )
            },
        )
        mock_request.assert_not_called()

    def test_base_prompt_is_injected_server_side(self):
        """Configured base prompt is prepended before the upstream call."""
        api.portal.set_registry_record(
            f"{_SETTINGS_PREFIX}.base_prompt", "Stay concise."
        )
        payload = json.dumps(
            {
                "stream": False,
                "messages": [
                    {"role": "system", "content": "Page context"},
                    {"role": "user", "content": "Hello"},
                ],
            }
        ).encode()

        with patch(
            "imio.omnia.core.browser.proxy.get_openai_api_url",
            return_value=_UPSTREAM_URL,
        ), patch(
            "imio.omnia.core.browser.proxy.getMultiAdapter"
        ) as mock_adapter, patch(
            "imio.omnia.core.browser.proxy.httpx.request",
            return_value=MagicMock(status_code=200, text="{}"),
        ) as mock_request:
            self._mock_service(mock_adapter)
            self._make_view(body=payload)()

        forwarded_messages = mock_request.call_args[1]["json"]["messages"]
        self.assertEqual(
            forwarded_messages[0],
            {"role": "system", "content": "Stay concise."},
        )
        self.assertEqual(
            forwarded_messages[1],
            {"role": "system", "content": "Page context"},
        )

    def test_base_prompt_is_not_duplicated_when_already_first_message(self):
        """An identical leading system prompt is not added twice."""
        api.portal.set_registry_record(
            f"{_SETTINGS_PREFIX}.base_prompt", "Stay concise."
        )
        payload = json.dumps(
            {
                "stream": False,
                "messages": [
                    {"role": "system", "content": "Stay concise."},
                    {"role": "user", "content": "Hello"},
                ],
            }
        ).encode()

        with patch(
            "imio.omnia.core.browser.proxy.get_openai_api_url",
            return_value=_UPSTREAM_URL,
        ), patch(
            "imio.omnia.core.browser.proxy.getMultiAdapter"
        ) as mock_adapter, patch(
            "imio.omnia.core.browser.proxy.httpx.request",
            return_value=MagicMock(status_code=200, text="{}"),
        ) as mock_request:
            self._mock_service(mock_adapter)
            self._make_view(body=payload)()

        forwarded_messages = mock_request.call_args[1]["json"]["messages"]
        self.assertEqual(
            forwarded_messages,
            [
                {"role": "system", "content": "Stay concise."},
                {"role": "user", "content": "Hello"},
            ],
        )

    def test_adapter_system_prompt_is_injected_server_side(self):
        """The assistant proxy uses the adapter-provided system prompt."""
        payload = json.dumps(
            {
                "stream": False,
                "messages": [
                    {"role": "system", "content": "Page context"},
                    {"role": "user", "content": "Hello"},
                ],
            }
        ).encode()

        with patch(
            "imio.omnia.assistant.browser.proxy.getMultiAdapter",
            return_value=DummyOmniaAssistantAdapter(
                available=True, system_prompt="Adapter prompt."
            ),
        ), patch(
            "imio.omnia.core.browser.proxy.get_openai_api_url",
            return_value=_UPSTREAM_URL,
        ), patch(
            "imio.omnia.core.browser.proxy.getMultiAdapter"
        ) as mock_service_adapter, patch(
            "imio.omnia.core.browser.proxy.httpx.request",
            return_value=MagicMock(status_code=200, text="{}"),
        ) as mock_request:
            self._mock_service(mock_service_adapter)
            self._make_view(body=payload)()

        forwarded_messages = mock_request.call_args[1]["json"]["messages"]
        self.assertEqual(
            forwarded_messages[0],
            {"role": "system", "content": "Adapter prompt."},
        )
        self.assertEqual(
            forwarded_messages[1],
            {"role": "system", "content": "Page context"},
        )

    # --- publishTraverse ---

    def test_publish_traverse_accumulates_segments(self):
        """Each publishTraverse call appends a segment and order is preserved."""
        view = OmniaAssistantOpenAIProxyView(self.portal, self.request)
        view.publishTraverse(self.request, "v1")
        view.publishTraverse(self.request, "chat")
        view.publishTraverse(self.request, "completions")
        self.assertEqual(view._path_segments, ["v1", "chat", "completions"])

    def test_publish_traverse_returns_self(self):
        """publishTraverse returns the view itself to support chained traversal."""
        view = OmniaAssistantOpenAIProxyView(self.portal, self.request)
        self.assertIs(view.publishTraverse(self.request, "v1"), view)

    # --- Non-streaming requests ---

    @patch("imio.omnia.core.browser.proxy.getMultiAdapter")
    @patch("imio.omnia.core.browser.proxy.get_openai_api_url", return_value=_UPSTREAM_URL)
    def test_non_streaming_forwards_upstream_response(self, _url, mock_adapter):
        """A successful non-streaming call returns the upstream response text."""
        self._mock_service(mock_adapter)
        upstream_text = '{"id": "cmpl-1", "choices": [{"message": {"content": "hello"}}]}'
        mock_resp = MagicMock(status_code=200, text=upstream_text)

        payload = json.dumps({"stream": False, "messages": []}).encode()
        with patch("imio.omnia.core.browser.proxy.httpx.request", return_value=mock_resp):
            result = self._make_view(body=payload)()

        self.assertEqual(self.request.response.getStatus(), 200)
        self.assertEqual(result, upstream_text)

    @patch("imio.omnia.core.browser.proxy.getMultiAdapter")
    @patch("imio.omnia.core.browser.proxy.get_openai_api_url", return_value=_UPSTREAM_URL)
    def test_non_streaming_path_segments_in_upstream_url(self, _url, mock_adapter):
        """Path segments are assembled and appended to the upstream base URL."""
        self._mock_service(mock_adapter)
        mock_resp = MagicMock(status_code=200, text="{}")

        payload = json.dumps({"stream": False}).encode()
        with patch("imio.omnia.core.browser.proxy.httpx.request", return_value=mock_resp) as mock_req:
            self._make_view(
                body=payload, path_segments=["v1", "chat", "completions"]
            )()

        call_url = mock_req.call_args[0][1]
        self.assertEqual(call_url, f"{_UPSTREAM_URL}/v1/chat/completions")

    @patch("imio.omnia.core.browser.proxy.getMultiAdapter")
    @patch("imio.omnia.core.browser.proxy.get_openai_api_url", return_value=_UPSTREAM_URL)
    def test_non_streaming_body_forwarded_verbatim(self, _url, mock_adapter):
        """The parsed JSON body is forwarded after assistant-specific processing."""
        self._mock_service(mock_adapter)
        mock_resp = MagicMock(status_code=200, text="{}")
        payload_dict = {"stream": False, "messages": [{"role": "user", "content": "hi"}]}

        with patch("imio.omnia.core.browser.proxy.httpx.request", return_value=mock_resp) as mock_req:
            self._make_view(body=json.dumps(payload_dict).encode())()

        self.assertEqual(mock_req.call_args[1].get("json"), payload_dict)

    @patch("imio.omnia.core.browser.proxy.getMultiAdapter")
    @patch("imio.omnia.core.browser.proxy.get_openai_api_url", return_value=_UPSTREAM_URL)
    def test_non_streaming_upstream_http_error_forwarded(self, _url, mock_adapter):
        """An HTTPStatusError from upstream is forwarded with the upstream status code."""
        self._mock_service(mock_adapter)
        bad_response = MagicMock(status_code=429)

        payload = json.dumps({"stream": False}).encode()
        with patch(
            "imio.omnia.core.browser.proxy.httpx.request",
            side_effect=httpx.HTTPStatusError(
                "Too Many Requests", request=MagicMock(), response=bad_response
            ),
        ):
            result = json.loads(self._make_view(body=payload)())

        self.assertEqual(self.request.response.getStatus(), 429)
        self.assertIn("error", result)

    @patch("imio.omnia.core.browser.proxy.getMultiAdapter")
    @patch("imio.omnia.core.browser.proxy.get_openai_api_url", return_value=_UPSTREAM_URL)
    def test_non_streaming_connection_error_returns_502(self, _url, mock_adapter):
        """A connection error during a non-streaming request returns 502."""
        self._mock_service(mock_adapter)

        payload = json.dumps({"stream": False}).encode()
        with patch(
            "imio.omnia.core.browser.proxy.httpx.request",
            side_effect=ConnectionError("unreachable"),
        ):
            result = json.loads(self._make_view(body=payload)())

        self.assertEqual(self.request.response.getStatus(), 502)
        self.assertEqual(result, {"error": "Upstream API error"})

    # --- Streaming requests ---

    @patch("imio.omnia.core.browser.proxy.getMultiAdapter")
    @patch("imio.omnia.core.browser.proxy.get_openai_api_url", return_value=_UPSTREAM_URL)
    def test_streaming_returns_sse_iterator(self, _url, mock_adapter):
        """A streaming request returns an SSEStreamIterator (IUnboundStreamIterator)."""
        self._mock_service(mock_adapter)
        mock_client = MagicMock()
        mock_upstream = MagicMock()
        mock_upstream.iter_bytes.return_value = iter([b"data: hi\n\n"])
        mock_client.send.return_value = mock_upstream

        payload = json.dumps({"stream": True, "messages": []}).encode()
        with patch("imio.omnia.core.browser.proxy.httpx.Client", return_value=mock_client):
            result = self._make_view(body=payload)()

        self.assertIsInstance(result, SSEStreamIterator)
        self.assertTrue(IUnboundStreamIterator.providedBy(result))

    @patch("imio.omnia.core.browser.proxy.getMultiAdapter")
    @patch("imio.omnia.core.browser.proxy.get_openai_api_url", return_value=_UPSTREAM_URL)
    def test_streaming_sets_sse_response_headers(self, _url, mock_adapter):
        """A streaming request sets Content-Type: text/event-stream and Cache-Control."""
        self._mock_service(mock_adapter)
        mock_client = MagicMock()
        mock_upstream = MagicMock()
        mock_upstream.iter_bytes.return_value = iter([])
        mock_client.send.return_value = mock_upstream

        payload = json.dumps({"stream": True}).encode()
        with patch("imio.omnia.core.browser.proxy.httpx.Client", return_value=mock_client):
            self._make_view(body=payload)()

        self.assertTrue(
            self.request.response.getHeader("Content-Type").startswith(
                "text/event-stream"
            )
        )
        self.assertEqual(
            self.request.response.getHeader("Cache-Control"), "no-cache"
        )

    @patch("imio.omnia.core.browser.proxy.getMultiAdapter")
    @patch("imio.omnia.core.browser.proxy.get_openai_api_url", return_value=_UPSTREAM_URL)
    def test_streaming_upstream_http_error_returns_json(self, _url, mock_adapter):
        """An HTTP error from the streaming upstream returns JSON with the upstream status."""
        self._mock_service(mock_adapter)
        bad_response = MagicMock(status_code=503)
        bad_response.read.return_value = b"Service Unavailable"
        mock_client = MagicMock()
        mock_client.send.side_effect = httpx.HTTPStatusError(
            "Service Unavailable", request=MagicMock(), response=bad_response
        )

        payload = json.dumps({"stream": True}).encode()
        with patch("imio.omnia.core.browser.proxy.httpx.Client", return_value=mock_client):
            result = json.loads(self._make_view(body=payload)())

        self.assertEqual(self.request.response.getStatus(), 503)
        self.assertIn("error", result)

    @patch("imio.omnia.core.browser.proxy.getMultiAdapter")
    @patch("imio.omnia.core.browser.proxy.get_openai_api_url", return_value=_UPSTREAM_URL)
    def test_streaming_connection_error_returns_502(self, _url, mock_adapter):
        """A connection error during streaming setup returns 502."""
        self._mock_service(mock_adapter)
        mock_client = MagicMock()
        mock_client.send.side_effect = ConnectionError("unreachable")

        payload = json.dumps({"stream": True}).encode()
        with patch("imio.omnia.core.browser.proxy.httpx.Client", return_value=mock_client):
            result = json.loads(self._make_view(body=payload)())

        self.assertEqual(self.request.response.getStatus(), 502)
        self.assertEqual(result, {"error": "Upstream API error"})


class TestSSEStreamIterator(unittest.TestCase):
    """Unit tests for SSEStreamIterator — streaming, error handling, resource cleanup."""

    def _make_iterator(self, chunks):
        client = MagicMock()
        response = MagicMock()
        response.iter_bytes.return_value = iter(chunks)
        return SSEStreamIterator(client, response)

    def test_yields_chunks_in_order(self):
        """Bytes chunks from the upstream response are yielded in order."""
        chunks = [b"data: first\n\n", b"data: second\n\n", b"data: [DONE]\n\n"]
        it = self._make_iterator(chunks)
        self.assertEqual(list(it), chunks)

    def test_exhaustion_closes_client_and_response(self):
        """After all chunks are consumed, both the client and response are closed."""
        it = self._make_iterator([b"data: only\n\n"])
        list(it)
        it._client.close.assert_called_once()
        it._response.close.assert_called_once()

    def test_exception_during_iteration_sends_error_sse_frame(self):
        """A mid-stream exception sends one SSE error data frame before stopping."""
        client = MagicMock()
        response = MagicMock()

        def failing_gen():
            yield b"data: ok\n\n"
            raise RuntimeError("connection reset")

        response.iter_bytes.return_value = failing_gen()
        it = SSEStreamIterator(client, response)

        collected = list(it)

        self.assertEqual(len(collected), 2)
        self.assertEqual(collected[0], b"data: ok\n\n")
        error_payload = json.loads(
            collected[1].decode().removeprefix("data: ").strip()
        )
        self.assertIn("error", error_payload)

    def test_only_one_error_frame_sent_on_repeated_calls(self):
        """A second __next__ after an exception raises StopIteration, not another error frame."""
        client = MagicMock()
        response = MagicMock()
        response.iter_bytes.return_value = iter([])
        it = SSEStreamIterator(client, response)
        # Force the iterator closed
        it._close()
        with self.assertRaises(StopIteration):
            next(it)

    def test_close_is_idempotent(self):
        """Calling _close multiple times closes resources exactly once each."""
        it = self._make_iterator([])
        it._close()
        it._close()
        it._client.close.assert_called_once()
        it._response.close.assert_called_once()

    def test_implements_unbound_stream_iterator_interface(self):
        """SSEStreamIterator declares IUnboundStreamIterator so Zope streams it."""
        it = self._make_iterator([])
        self.assertTrue(IUnboundStreamIterator.providedBy(it))
