# -*- coding: utf-8 -*-
from Products.CMFPlone.interfaces import INonInstallable
from zope.interface import implementer


@implementer(INonInstallable)
class HiddenProfiles(object):

    def getNonInstallableProfiles(self):
        """Hide uninstall profile from site-creation and quickinstaller."""
        return [
            "imio.omnia.assistant:uninstall",
        ]

    def getNonInstallableProducts(self):
        """Hide the upgrades package from site-creation and quickinstaller."""
        return ["imio.omnia.assistant.upgrades"]


def post_install(context):
    """Post install script"""


def uninstall(context):
    """Uninstall script"""
    from plone.registry.interfaces import IRegistry
    from zope.component import getUtility

    registry = getUtility(IRegistry)

    # Disable assistant bundles
    for bundle_name in ("omnia-assistant-preact", "omnia-assistant"):
        key = f"plone.bundles/{bundle_name}.enabled"
        if key in registry.records:
            registry[key] = False
