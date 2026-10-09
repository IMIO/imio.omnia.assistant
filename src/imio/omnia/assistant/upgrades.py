# -*- coding: utf-8 -*-
"""GenericSetup upgrade steps."""


def upgrade_1001_to_1002(context):
    """The UI bundle self-injects styles; clear the stale csscompilation."""
    from plone.registry.interfaces import IRegistry
    from zope.component import getUtility

    registry = getUtility(IRegistry)
    key = "plone.bundles/omnia-assistant.csscompilation"
    if key in registry.records:
        registry[key] = ""


def upgrade_1002_to_1003(context):
    """omnia-assistant-ui 2.x replaced ``mode`` by ``layout``."""
    from imio.omnia.assistant.browser.controlpanel import IOmniaAssistantSettings
    from plone.registry.interfaces import IRegistry
    from zope.component import getUtility

    registry = getUtility(IRegistry)
    registry.registerInterface(IOmniaAssistantSettings)
    key = f"{IOmniaAssistantSettings.__identifier__}.mode"
    if key in registry.records:
        del registry.records[key]
