====================
imio.omnia.assistant
====================

A floating AI chat assistant for Plone 6, part of the
`Omnia <https://gitlab.imio.be/imio/imio.omnia>`_ suite by iMio.

This package adds a chat widget (a floating panel or a right sidebar) to
every page of the Plone site. The assistant streams responses from an
OpenAI-compatible API through a secure server-side proxy, and can read the
current page when a question needs it. It relies on ``imio.omnia.core`` for
API connectivity, authentication, and the shared Omnia control panel.


Features
========

- **Floating panel or sidebar** — a panel opening from a round button in the
  bottom-right corner, or docked on the right and pushing the page. The
  visitor can switch between both from the panel header.
- **Real-time streaming** — SSE-based chat completions streamed token by token.
- **Page reading** — the model calls a ``read_page`` tool, run in the browser,
  that returns the page content (HTML or plain text, selected by a CSS
  selector).
- **Large-context handling** — when the page content exceeds the configured
  limit, the model asks the visitor to quote the relevant passage: selecting
  text shows a « Demander à Omnia » button under it.
- **Keyboard shortcut** — ``Alt+I`` toggles the panel open/closed.
- **Secure by design** — API credentials never reach the browser; all
  requests go through ``@@omnia-assistant-api``, guarded by a Plone
  permission, an Origin check and Plone's CSRF token.
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
``max_context_chars``          Maximum characters of page content
                               ``read_page`` returns (default: ``20000``)
``max_messages_per_session``   Maximum number of user messages allowed in a
                               single conversation (default: ``0``, unlimited)
``layout``                     ``floating`` (round button + popover) or
                               ``sidebar`` (docked right, default:
                               ``floating``)
``initial_width``              Initial panel width in pixels (default: ``380``)
``initial_height``             Initial panel height in pixels (default: ``520``)
``disclaimer``                 Disclaimer text shown at the bottom of the panel
=============================  =================================================


How it works
============

Widget loading
--------------

The default GenericSetup profile registers one Plone resource bundle,
``omnia-assistant``: the self-contained UMD build of
`@imiobe/omnia-assistant-ui <https://gitlab.imio.be/ia/omnia-assistant-ui>`_
(React and styles bundled inside, rendered in a shadow root).

An ``OmniaAssistantConfigViewlet`` registered in ``plone.htmlhead`` sets
``window.omnia_assistant_settings`` from the Plone registry (model, selectors,
layout, dimensions, etc.). The bundle reads it and mounts itself into a
``<div id="omnia-assistant-root">`` it appends to the page body.

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

The widget sends no ``Authorization`` header. The caller must have the
``imio.omnia.core: Access Omnia OpenAI proxy`` permission, which
``imio.omnia.core`` grants to ``Authenticated`` users: the same-origin
``fetch()`` carries the session cookie. Requests whose ``Origin`` host differs
from the portal's are rejected.

Every request must also carry plone.protect's CSRF token in an
``X-CSRF-TOKEN`` header, otherwise the proxy answers ``403``. The viewlet
exposes it as ``csrf_token`` in ``window.omnia_assistant_settings``, for
anonymous visitors too. The widget sends it on the chat and MCP requests.

Projects that need anonymous access can override that permission mapping in
their own GenericSetup ``rolemap.xml``.

The request payload follows the OpenAI Chat Completions format::

    {
      "model": "<configured model>",
      "messages": [
        { "role": "user", "content": "<user message>" }
      ],
      "tools": [{ "type": "function", "function": { "name": "read_page" } }],
      "stream": true
    }

When the model calls ``read_page``, the widget runs it and calls the model
again with the result as a ``tool`` message.

If ``base_prompt`` is configured, the assistant proxy prepends it server-side
as the first ``system`` message before dispatching upstream. The prompt is no
longer exposed in ``window.omnia_assistant_settings``.
Projects can override that behavior with a more specific
``IOmniaAssistantAdapter`` that changes availability rules or returns a custom
system prompt for the current context/request.

Conversation length limit
-------------------------

When ``max_messages_per_session`` is greater than ``0``, the assistant proxy
rejects (HTTP 400) any request whose payload contains more user messages than
the configured limit; the widget shows the error in the reply. Assistant
replies and tool results do not consume the limit. Starting a new conversation
from the panel header ("Nouveau") resets the counter.

Page reading
------------

When ``include_page_content`` is ``True``, the widget offers the model a
``read_page`` tool. It returns the DOM content matched by
``page_content_selector``, as ``innerHTML`` or ``innerText`` (controlled by
``page_content_clean``). The page is never sent up front, so:

- the configured model must support tool calling (``mistral-*`` and
  ``zai-glm-5-2`` on the Omnia gateway do);
- ``base_prompt`` should tell the model to call ``read_page`` before
  answering a question about the page, otherwise it answers without reading
  it.

If the content exceeds ``max_context_chars`` characters, ``read_page`` tells
the model to ask the visitor to quote the relevant passage.

Uninstall
---------

The uninstall profile removes the assistant settings and the
``omnia-assistant`` bundle from the registry.


Frontend development
====================

The widget is developed in its own repository and published to npm as
``@imiobe/omnia-assistant-ui``. ``browser/resources/package.json`` pins the
version; the built file is committed to ``browser/static/`` and served via
``++plone++imio.omnia.assistant/``.

After bumping the version::

    make build-js          # npm ci + copy the UMD bundle to static/
    make clean-js          # remove the built artifact

Tests covering the registry export and proxy enforcement live in
``src/imio/omnia/assistant/tests/`` and should be kept in sync with any
setting or frontend behavior changes.

The frontend stack uses **Vite** (library mode), **React**,
**@assistant-ui/react** (chat runtime), **Mousetrap** (keyboard shortcuts),
and **Tailwind CSS v4**.


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
