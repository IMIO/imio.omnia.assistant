Changelog
=========


1.0a4 (2026-04-03)
------------------

- Load imio.omnia.core ZCML.
  [aduchene]


1.0a3 (2026-04-03)
------------------

- Re-release because ZCML files were lacking (2).
  [aduchene]


1.0a2 (2026-04-03)
------------------

- Re-release because ZCML files were lacking.
  [aduchene]


1.0a1 (2026-04-03)
------------------

- Initial release.
  [duchenean]
- Added floating/fixed AI chat assistant widget built with Vite + Preact
  and ``@assistant-ui/react``.
  [duchenean]
- Added real-time SSE streaming of chat completions from the
  OpenAI-compatible Omnia gateway.
  [duchenean]
- Added server-side API proxy (``@@omnia-assistant-api``) so upstream
  credentials are never exposed to the browser.
  [duchenean]
- Added HMAC-signed bearer token authentication (2-hour expiration) for
  proxy requests, signed with the Plone site keyring.
  [duchenean]
- Added automatic page content injection as conversation context, with
  configurable CSS selectors, HTML or plain-text mode, and character limit.
  [duchenean]
- Added server-side system prompt (``base_prompt``) injection — no longer
  exposed to the frontend.
  [duchenean]
- Added control panel tab (``@@omnia-assistant-settings``) in the shared
  Omnia settings UI: enable/disable, model selection, display mode
  (floating/fixed), dimensions, disclaimer, and conversation limits.
  [duchenean]
- Added ``IOmniaAssistantAdapter`` extension point for context-specific
  availability, system prompt composition, and frontend config overrides.
  [duchenean]
- Added dynamic model vocabulary fetched from the ``IOmniaOpenAIService``.
  [duchenean]
- Added ``max_messages_per_session`` enforced both client and server-side.
  [duchenean]
- Added keyboard shortcut (Alt+I) to toggle the assistant panel.
  [duchenean]
- Added i18n support (en, fr).
  [duchenean]
