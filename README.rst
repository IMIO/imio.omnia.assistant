====================
imio.omnia.assistant
====================

A floating AI chat assistant for Plone 6, part of the
`Omnia <https://gitlab.imio.be/imio/imio.omnia>`_ suite by iMio.

This package adds a draggable, resizable chat widget to every page of the
Plone site. The assistant streams responses from an OpenAI-compatible API
through a secure server-side proxy, and can automatically inject the current
page content as conversation context. It relies on ``imio.omnia.core`` for
API connectivity, authentication, and the shared Omnia control panel.


Features
========

- **Floating or fixed panel** — draggable and resizable floating mode, or a
  fixed sidebar anchored to the page edge.
- **Real-time streaming** — SSE-based chat completions streamed token by token.
- **Page context injection** — current page content (HTML or plain text,
  configurable via a CSS selector) is sent as a system message so the
  assistant can answer questions about the page.
- **Large-context handling** — when the page content exceeds the configured
  limit the assistant prompts the user to select a relevant text excerpt
  instead.
- **Keyboard shortcut** — ``Alt+I`` toggles the panel open/closed.
- **Secure by design** — API credentials never reach the browser; all
  requests go through ``@@omnia-assistant-api`` with an HMAC-signed token.
- **Configurable** — system prompt, disclaimer, model, display dimensions,
  conversation length, and context extraction are all adjustable from the
  control panel.


Installation
============

Add the egg to your buildout::

    [buildout]

    ...

    eggs =
        imio.omnia.assistant

Then run ``bin/buildout``.

The package is auto-included in Plone via ``z3c.autoinclude.plugin``, so no
ZCML slug is needed.

``imio.omnia.core`` must be installed first. Its GenericSetup profile is
declared as a dependency in ``profiles/default/metadata.xml``, so installing
``imio.omnia.assistant`` via the Plone add-on control panel is sufficient.


Configuration
=============

All settings are editable from the **Assistant** tab of the Omnia control
panel (Site Setup > Omnia > ``@@omnia-assistant-settings``).

Registry settings
-----------------

Stored under the prefix
``imio.omnia.assistant.browser.controlpanel.IOmniaAssistantSettings``:

=============================  =================================================
Field                          Purpose
=============================  =================================================
``enabled``                    Enable or disable the assistant globally
                               (default: ``True``)
``model``                      Model name for the OpenAI-compatible API
                               (vocabulary fetched from the API at form load)
``base_prompt``                System prompt prepended server-side to every
                               conversation
``include_page_content``       Include the current page as context
                               (default: ``True``)
``page_content_selector``      CSS selector(s) to extract page content
                               (default: ``#content``)
``page_content_clean``         Use ``innerText`` instead of ``innerHTML``
                               for cleaner extraction (default: ``False``)
``max_context_chars``          Maximum characters of page content to send
                               (default: ``20000``)
``max_messages_per_session``   Maximum number of user messages allowed in a
                               single conversation (default: ``0``, unlimited)
``mode``                       Panel display mode: ``floating`` (draggable)
                               or ``fixed`` (sidebar, default: ``floating``)
``initial_width``              Initial panel width in pixels (default: ``380``)
``initial_height``             Initial panel height in pixels (default: ``520``)
``disclaimer``                 Disclaimer text shown at the bottom of the panel
=============================  =================================================


How it works
============

Widget loading
--------------

Two Plone resource bundles are registered by the default GenericSetup profile:

- ``omnia-assistant-preact`` — Preact UMD (loaded first as a global).
- ``omnia-assistant`` — the assistant UI library (depends on the preact
  bundle).

An ``OmniaAssistantConfigViewlet`` registered in ``plone.htmlhead`` renders a
``<script>`` tag that:

1. Sets ``window.omnia_assistant_settings`` with configuration from the Plone
   registry (model, selectors, dimensions, etc.).
2. Waits for the ``OmniaAssistantUI`` global to be available (exported by the
   bundle).
3. Calls ``OmniaAssistantUI.mount('omnia-assistant-root', window.omnia_assistant_settings)``
   to mount the Preact widget into a ``<div id="omnia-assistant-root">`` that
   the viewlet template appends to the page body.

The widget is not rendered when the ``enabled`` setting is ``False``.
More generally, page-level availability and server-side prompt composition are
exposed through the ``IOmniaAssistantAdapter`` multi-adapter. The default
implementation reads ``enabled`` and ``base_prompt`` from the registry.

Streaming chat
--------------

Chat messages are sent as POST requests to
``<portal_url>/@@omnia-assistant-api/chat/completions`` with ``stream: true``.
The assistant proxy inherits from the shared
``imio.omnia.core.browser.proxy.OmniaOpenAIProxyView`` implementation, keeps
the shared auth/streaming behavior, and forwards the request to the
configured OpenAI-compatible gateway in real time.

Authentication uses an HMAC Bearer token generated server-side by the viewlet
(``imio.omnia.core.tokens.generate_token()``). Tokens are signed with the
Plone site keyring and expire after 2 hours. By default, the caller must also
have the ``imio.omnia.core: Access Omnia OpenAI proxy`` permission, which
``imio.omnia.core`` grants to ``Authenticated`` users.

Projects that need anonymous access can override that permission mapping in
their own GenericSetup ``rolemap.xml``.

The request payload follows the OpenAI Chat Completions format::

    {
      "model": "<configured model>",
      "messages": [
        { "role": "system", "content": "<page content>" },
        { "role": "user",   "content": "<user message>" }
      ],
      "stream": true
    }

If ``base_prompt`` is configured, the assistant proxy prepends it server-side
as the first ``system`` message before dispatching upstream. The prompt is no
longer exposed in ``window.omnia_assistant_settings``.
Projects can override that behavior with a more specific
``IOmniaAssistantAdapter`` that changes availability rules or returns a custom
system prompt for the current context/request.

Conversation length limit
-------------------------

When ``max_messages_per_session`` is greater than ``0``, the assistant counts
user prompts in the current thread. Assistant replies do not consume the
limit.

Once the limit is reached:

- the composer is disabled for the current thread,
- the UI tells the user to start a new conversation,
- the backend proxy also rejects any request whose payload contains more user
  messages than the configured limit.

Starting a new conversation from the panel header resets the counter because
the limit is applied per thread, not across the whole browser session.

Page content injection
----------------------

When ``include_page_content`` is ``True``, the widget extracts DOM content
using the CSS selector(s) in ``page_content_selector`` (a single selector
string, or a JSON array of selectors). Each matching element contributes
either its ``innerHTML`` or ``innerText`` (controlled by ``page_content_clean``),
joined by blank lines.

If the extracted content exceeds ``max_context_chars`` characters, the widget
displays a warning banner and invites the user to select a specific text
excerpt on the page. The selected text replaces the full page content as
context for that turn.

Uninstall
---------

The uninstall handler disables both Plone bundles (``omnia-assistant`` and
``omnia-assistant-preact``) by setting their ``enabled`` registry flag to
``False``.


Frontend development
====================

The assistant widget source lives in ``browser/resources/``. Built artifacts
are committed to ``browser/static/`` and served via
``++plone++imio.omnia.assistant/``.

Rebuild after JS changes::

    make build-js          # npm ci + vite build + copy to static/
    make clean-js          # remove built artifacts

Tests covering the registry export and proxy enforcement live in
``src/imio/omnia/assistant/tests/`` and should be kept in sync with any
setting or frontend behavior changes.

The frontend stack uses **Vite** (library mode), **Preact**,
**@assistant-ui/react** (chat runtime), **Framer Motion** (animations),
**Mousetrap** (keyboard shortcuts), and **Tailwind CSS v3**.


Translations
============

This product has been translated into:

- English
- French


Authors
=======

- `iMio, SCRL <https://imio.be>`_
- Antoine Duchene


License
=======

The project is licensed under the GPLv2.
