# -*- coding: utf-8 -*-
import json

from plone.app.layout.viewlets.common import ViewletBase
from zope.component import getMultiAdapter

from imio.omnia.assistant.interfaces import IOmniaAssistantAdapter


class OmniaAssistantConfigViewlet(ViewletBase):
    """Inject window.omnia_assistant_settings from Plone registry into the page."""

    def available(self):
        adapter = getMultiAdapter(
            (self.context, self.request), IOmniaAssistantAdapter
        )
        return adapter.is_available()

    def config_json(self):
        if not self.available():
            return None
        adapter = getMultiAdapter(
            (self.context, self.request), IOmniaAssistantAdapter
        )
        return json.dumps(adapter.get_config())
