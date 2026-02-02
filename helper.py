from webexteamssdk.models.cards import AdaptiveCard, TextBlock, Text
from webexteamssdk.models.cards.actions import Submit
from json import JSONDecodeError
import json


def make_code_card() -> AdaptiveCard:
    greeting = TextBlock("Get an activation code:")
    workspace = Text('workspace', placeholder="Enter Workspace Name")
    submit = Submit(title="Provision")

    card = AdaptiveCard(
        body=[greeting, workspace], actions=[submit]
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
