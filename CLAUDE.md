# imio.omnia.assistant

Plone 6 add-on providing the Omnia AI chat assistant for Plone. It adds a configurable assistant widget to pages, uses the shared Omnia settings and proxy infrastructure from `imio.omnia.core`, and streams chat completions through the OpenAI-compatible Omnia gateway.

## Project layout

```
src/imio/omnia/assistant/
├── browser/
│   ├── controlpanel.py         # @@omnia-assistant-settings registry form + model vocabulary
│   ├── viewlets.py             # Injects runtime config and signed proxy token into pages
│   ├── templates/
│   │   └── omnia_assistant_config.pt
│   │                           # <script> setting window.omnia_assistant_settings
│   ├── resources/              # package.json pinning the published npm UI bundle
│   ├── static/                 # Built JS bundle served by Plone
│   │   └── omnia-assistant-ui.js
│   └── configure.zcml          # Static resources, viewlet, vocabulary, control panel
├── profiles/
│   ├── default/
│   │   ├── actions.xml         # Control panel tab registration
│   │   ├── browserlayer.xml    # Browser layer registration
│   │   ├── metadata.xml        # Profile metadata & dependency on imio.omnia.core
│   │   ├── registry/
│   │   │   └── main.xml        # Assistant settings + Plone bundle registry
│   │   └── rolemap.xml         # Role-permission mappings
│   └── uninstall/              # GenericSetup uninstall profile
├── locales/                    # i18n (en, fr)
├── tests/                      # Setup, proxy, viewlet, robot tests
├── interfaces.py               # IImioOmniaAssistantLayer
├── setuphandlers.py            # HiddenProfiles, post_install, uninstall hooks
├── testing.py                  # IMIO_OMNIA_ASSISTANT_*_TESTING fixtures
├── configure.zcml              # Root ZCML — profiles, browser include
└── permissions.zcml            # Permission definitions
```

## Frontend (JS)

The chat widget is developed in its own repository and published to npm as
[`@imiobe/omnia-assistant-ui`](https://gitlab.imio.be/ia/omnia-assistant-ui).
`browser/resources/package.json` pins the version consumed here; `make
build-js` copies its built `dist/` file into the committed asset under
`browser/static/`.

The published package ships a single self-contained UMD bundle (Preact and
CSS both bundled inside, styles injected at runtime) — there is no separate
CSS file to copy.

### Bumping the UI version

1. Edit `browser/resources/package.json` — bump the
   `@imiobe/omnia-assistant-ui` version.
2. `cd src/imio/omnia/assistant/browser/resources && npm install` (refreshes
   `package-lock.json`).
3. `make build-js` from the package root (copies the new
   `omnia-assistant-ui.umd.cjs` to `browser/static/omnia-assistant-ui.js`).
4. Commit `package.json`, `package-lock.json`, and the updated
   `browser/static/omnia-assistant-ui.js` together.

```bash
make build-js                   # npm ci + copy dist to static/
make clean-js                   # Remove built artifact from static/
```

### How the widget is loaded

1. `omnia-assistant-ui.js` (self-contained, Preact and styles bundled inside) is registered as the `plone.bundles/omnia-assistant` bundle.
2. The `OmniaAssistantConfigViewlet` injects `window.omnia_assistant_settings` into the page header.
3. The frontend bundle auto-mounts the assistant using that config.

### Config bridge (viewlet)

The `OmniaAssistantConfigViewlet` reads registry values, points the frontend at the local proxy, and generates a short-lived HMAC Bearer token:

- `api_service_url` → `context.absolute_url()/@@omnia-assistant-api`
- `api_key` → signed token from `imio.omnia.core.tokens.generate_token()`
- `model`, `include_page_content`, `page_content_selector`, `page_content_clean`, `max_context_chars`, `mode`, `initial_width`, `initial_height`, `disclaimer` → from `IOmniaAssistantSettings`

This keeps upstream credentials server-side.

The `base_prompt` registry setting is no longer exposed to the browser for the
Plone integration. It is injected server-side by the assistant proxy.

## Development

This package is developed inside the parent `imio.omnia` buildout. From the buildout root (`../../..`):

```bash
bin/buildout                    # Install all develop eggs
bin/instance fg                 # Start Plone on port 8080 (admin:admin)
```

### Running tests

From this package directory:

```bash
tox -e py312-Plone61            # Run tests against Plone 6.1
tox -l                          # List all test environments
```

Or via the parent buildout:

```bash
../../bin/test -s imio.omnia.assistant
```

### Code quality

```bash
tox -e black-check              # Check formatting
tox -e black-enforce            # Apply formatting
tox -e py312-lint               # isort + flake8
tox -e isort-apply              # Fix import order
```

## Code style

- Formatter: **Black** (line length 120)
- Import sorting: **isort** with `profile = plone`
- Linter: **flake8** (ignores: W503, C812, E501, T001, C813, C101)
- i18n domain: `imio.omnia.assistant` — use `from imio.omnia.assistant import _` for message strings
- Editor config: 4-space indent for Python/cfg, 2-space for XML/HTML/JS

## Registry settings

Stored under `imio.omnia.assistant.browser.controlpanel.IOmniaAssistantSettings`:

- `enabled` — Enable or disable the assistant globally
- `model` — Model name selected from the OpenAI-compatible API
- `base_prompt` — System prompt injected server-side for every conversation
- `include_page_content` — Include current page content as context
- `page_content_selector` — CSS selector used to extract page content
- `page_content_clean` — Use plain text (`innerText`) instead of HTML
- `max_context_chars` — Max characters of page content injected as context
- `max_messages_per_session` — Max number of user messages allowed per conversation
- `mode` — Panel mode: `floating` or `fixed`
- `initial_width` — Initial panel width in pixels
- `initial_height` — Initial panel height in pixels
- `disclaimer` — Optional disclaimer shown at the bottom of the panel

The install profile registers the assistant JS bundle in Plone's bundle registry.

## Architecture notes

- Depends on `imio.omnia.core` for the shared control panel wrapper, token generation, and the base OpenAI proxy implementation that the assistant subclasses at `@@omnia-assistant-api`.
- Auto-included in Plone via `z3c.autoinclude.plugin` entry point (target: `plone`).
- Browser layer `IImioOmniaAssistantLayer` gates all views and overrides — only active when the add-on is installed.
- Control panel view is registered at `@@omnia-assistant-settings` and requires `cmf.ManagePortal`.
- `IOmniaAssistantAdapter` is the assistant extension point for context/request-specific availability, server-side system prompt composition, and frontend config overrides. The default `OmniaAssistantAdapter` reads `enabled` and `base_prompt` from the registry.
- Available models are fetched dynamically through the `IOmniaOpenAIService` adapter exposed by `imio.omnia.core`.
- The frontend talks only to the local proxy, not directly to the upstream OpenAI-compatible endpoint.
