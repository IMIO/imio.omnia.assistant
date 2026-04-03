# -*- coding: utf-8 -*-
from plone.app.robotframework.testing import REMOTE_LIBRARY_BUNDLE_FIXTURE
from plone.app.testing import applyProfile
from plone.app.testing import FunctionalTesting
from plone.app.testing import IntegrationTesting
from plone.app.testing import PloneSandboxLayer
from plone.testing import z2

import imio.omnia.assistant
from imio.omnia.core.testing import IMIO_OMNIA_CORE_FIXTURE


class ImioOmniaAssistantLayer(PloneSandboxLayer):

    defaultBases = (IMIO_OMNIA_CORE_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        self.loadZCML(package=imio.omnia.assistant)

    def setUpPloneSite(self, portal):
        applyProfile(portal, "imio.omnia.assistant:default")


IMIO_OMNIA_ASSISTANT_FIXTURE = ImioOmniaAssistantLayer()


IMIO_OMNIA_ASSISTANT_INTEGRATION_TESTING = IntegrationTesting(
    bases=(IMIO_OMNIA_ASSISTANT_FIXTURE,),
    name="ImioOmniaAssistantLayer:IntegrationTesting",
)


IMIO_OMNIA_ASSISTANT_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(IMIO_OMNIA_ASSISTANT_FIXTURE,),
    name="ImioOmniaAssistantLayer:FunctionalTesting",
)


IMIO_OMNIA_ASSISTANT_ACCEPTANCE_TESTING = FunctionalTesting(
    bases=(
        IMIO_OMNIA_ASSISTANT_FIXTURE,
        REMOTE_LIBRARY_BUNDLE_FIXTURE,
        z2.ZSERVER_FIXTURE,
    ),
    name="ImioOmniaAssistantLayer:AcceptanceTesting",
)
