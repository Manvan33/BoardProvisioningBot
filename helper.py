from webexteamssdk.models.cards import AdaptiveCard, TextBlock, Text, Choice
from webexteamssdk.models.cards.actions import Submit
from webexteamssdk.models.cards.inputs import Choices
from json import JSONDecodeError
import json


def make_code_card(workspaces: dict) -> AdaptiveCard:
    greeting = TextBlock("New activation code request", size="Medium", weight="Bolder")
    instruction = TextBlock(
        "Please select an existing workspace, or enter a name for a new workspace.",
        wrap=True
    )
    existing_workspaces = Choices(
        id="existing-workspace",
        choices=[Choice(title=v, value=k) for k, v in workspaces.items()]
    )
    workspace = Text('workspace', placeholder="New workspace")
    submit = Submit(title="Provision")
    card = AdaptiveCard(
        body=[greeting, instruction, existing_workspaces, workspace], actions=[submit]
    )
    return card

def split_code(code) -> str:
    return code[:4] + '-' + code[4:8] + '-' + code[8:12] + '-' + code[12:]


def load_text(text):
    try:
        text = json.loads(text.content)
        return text
    except JSONDecodeError:
        return text


def is_json(text):
    try:
        text.json()
        return True
    except JSONDecodeError:
        return False


def create_admin(token, org_id, room_id):
    from webex_admin import WebexAdmin
    return WebexAdmin(token)


def make_init_card() -> AdaptiveCard:
    greeting = TextBlock("Welcome! Please initialize the bot.", size="Medium", weight="Bolder")
    instruction = TextBlock(
        "Please enter your Organization ID and Personal Access Token.",
        wrap=True
    )
    org_id = Text('org_id', placeholder="Organization ID")
    access_token = Text('access_token', placeholder="Personal Access Token")
    submit = Submit(title="Initialize")
    card = AdaptiveCard(
        body=[greeting, instruction, org_id, access_token], actions=[submit]
    )
    return card
