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
