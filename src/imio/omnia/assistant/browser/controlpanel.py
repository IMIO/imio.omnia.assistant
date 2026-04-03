# -*- coding: utf-8 -*-
import logging

from imio.omnia.assistant import _
from imio.omnia.core.browser.controlpanel import OmniaCoreControlPanelFormWrapper
from imio.omnia.core.interfaces import IOmniaOpenAIService
from plone import api
from plone.app.registry.browser.controlpanel import RegistryEditForm
from plone.z3cform import layout
from zope import schema
from zope.component import getMultiAdapter
from zope.globalrequest import getRequest
from zope.interface import Interface
from zope.interface import implementer
from zope.schema.interfaces import IVocabularyFactory
from zope.schema.vocabulary import SimpleTerm
from zope.schema.vocabulary import SimpleVocabulary

logger = logging.getLogger(__name__)

_MODEL_REGISTRY_KEY = (
    "imio.omnia.assistant.browser.controlpanel.IOmniaAssistantSettings.model"
)


@implementer(IVocabularyFactory)
class OmniaModelsVocabularyFactory:
    """Vocabulary of available models from the OpenAI-compatible API."""

    def __call__(self, context):
        terms = []
        try:
            portal = api.portal.get()
            request = getRequest()
            service = getMultiAdapter((portal, request), IOmniaOpenAIService)
            result = service.list_models()
            for model_data in result.get("data", []):
                model_id = model_data["id"]
                terms.append(SimpleTerm(value=model_id, token=model_id, title=model_id))
        except Exception:
            logger.error("Could not fetch models from OpenAI API", exc_info=True)

        if not terms:
            # Fallback: keep the currently saved value so the form still renders.
            try:
                current = api.portal.get_registry_record(
                    _MODEL_REGISTRY_KEY, default=None
                )
                if current:
                    terms = [SimpleTerm(value=current, token=current, title=current)]
            except Exception:
                pass

        return SimpleVocabulary(terms)


class IOmniaAssistantSettings(Interface):
    enabled = schema.Bool(
        title=_("Enabled"),
        description=_("Enable or disable the AI assistant globally."),
        required=False,
        default=True,
    )
    model = schema.Choice(
        title=_("Model"),
        description=_("Model for the OpenAI-compatible API."),
        vocabulary="imio.omnia.assistant.models",
        required=True,
    )
    base_prompt = schema.Text(
        title=_("System prompt"),
        description=_("System prompt sent with every conversation."),
        required=False,
    )
    include_page_content = schema.Bool(
        title=_("Include page content"),
        description=_("Include current page content as context for the AI."),
        required=False,
        default=True,
    )
    page_content_selector = schema.TextLine(
        title=_("Page content CSS selector"),
        description=_("CSS selector to extract page content from."),
        required=False,
        default="#content",
    )
    page_content_clean = schema.Bool(
        title=_("Use plain text"),
        description=_(
            "Use innerText instead of innerHTML for page content extraction."
        ),
        required=False,
        default=False,
    )
    max_context_chars = schema.Int(
        title=_("Max context characters"),
        description=_("Maximum characters of page content to include as context."),
        required=False,
        default=20000,
    )
    max_messages_per_session = schema.Int(
        title=_("Max messages per conversation"),
        description=_(
            "Maximum number of user messages allowed in a single conversation. "
            "Set to 0 for no limit."
        ),
        required=False,
        default=0,
        min=0,
    )
    mode = schema.Choice(
        title=_("Display mode"),
        description=_("Panel display mode: floating (draggable) or fixed."),
        values=["floating", "fixed"],
        required=False,
        default="floating",
    )
    initial_width = schema.Int(
        title=_("Panel width"),
        description=_("Initial panel width in pixels."),
        required=False,
        default=380,
    )
    initial_height = schema.Int(
        title=_("Panel height"),
        description=_("Initial panel height in pixels."),
        required=False,
        default=520,
    )
    disclaimer = schema.Text(
        title=_("Disclaimer"),
        description=_(
            "Disclaimer text shown at the bottom of the chat panel. "
            "Leave empty for the default French disclaimer."
        ),
        required=False,
    )


class OmniaAssistantControlPanelForm(RegistryEditForm):
    label = _("AI Assistant settings")
    schema = IOmniaAssistantSettings


OmniaAssistantControlPanelView = layout.wrap_form(
    OmniaAssistantControlPanelForm, OmniaCoreControlPanelFormWrapper
)
