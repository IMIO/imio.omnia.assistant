# -*- coding: utf-8 -*-
"""Setup tests for this package."""
from plone import api
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.registry.interfaces import IRegistry
from imio.omnia.assistant.testing import IMIO_OMNIA_ASSISTANT_INTEGRATION_TESTING
from zope.component import getUtility

import unittest


try:
    from Products.CMFPlone.utils import get_installer
except ImportError:
    get_installer = None


class TestSetup(unittest.TestCase):
    """Test that imio.omnia.assistant is properly installed."""

    layer = IMIO_OMNIA_ASSISTANT_INTEGRATION_TESTING

    def setUp(self):
        """Custom shared utility setup for tests."""
        self.portal = self.layer['portal']
        if get_installer:
            self.installer = get_installer(self.portal, self.layer['request'])
        else:
            self.installer = api.portal.get_tool('portal_quickinstaller')

    def test_product_installed(self):
        """Test if imio.omnia.assistant is installed."""
        self.assertTrue(self.installer.is_product_installed(
            'imio.omnia.assistant'))

    def test_browserlayer(self):
        """Test that IImioOmniaAssistantLayer is registered."""
        from imio.omnia.assistant.interfaces import IImioOmniaAssistantLayer
        from plone.browserlayer import utils
        self.assertIn(
            IImioOmniaAssistantLayer,
            utils.registered_layers())


class TestUninstall(unittest.TestCase):

    layer = IMIO_OMNIA_ASSISTANT_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer['portal']
        if get_installer:
            self.installer = get_installer(self.portal, self.layer['request'])
        else:
            self.installer = api.portal.get_tool('portal_quickinstaller')
        self.registry = getUtility(IRegistry)
        roles_before = api.user.get_roles(TEST_USER_ID)
        setRoles(self.portal, TEST_USER_ID, ['Manager'])
        self.installer.uninstall_product('imio.omnia.assistant')
        setRoles(self.portal, TEST_USER_ID, roles_before)

    def test_product_uninstalled(self):
        """Test if imio.omnia.assistant is cleanly uninstalled."""
        self.assertFalse(self.installer.is_product_installed(
            'imio.omnia.assistant'))

    def test_browserlayer_removed(self):
        """Test that IImioOmniaAssistantLayer is removed."""
        from imio.omnia.assistant.interfaces import IImioOmniaAssistantLayer
        from plone.browserlayer import utils
        self.assertNotIn(IImioOmniaAssistantLayer, utils.registered_layers())

    def test_controlpanel_tab_removed(self):
        """Test that the assistant tab is removed from Omnia settings."""
        portal_actions = api.portal.get_tool("portal_actions")
        tabs = portal_actions.omnia_controlpanel_tabs
        self.assertNotIn("imio.omnia.assistant", tabs.objectIds())

    def test_registry_records_removed(self):
        """Test that assistant settings and bundles are removed."""
        self.assertNotIn(
            "imio.omnia.assistant.browser.controlpanel.IOmniaAssistantSettings.enabled",
            self.registry.records,
        )
        self.assertNotIn("plone.bundles/omnia-assistant.enabled", self.registry.records)
        self.assertNotIn(
            "plone.bundles/omnia-assistant-preact.enabled", self.registry.records
        )
