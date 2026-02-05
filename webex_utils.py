#!/usr/bin/env python3
import base64
from base64 import b64encode
import requests
import aiohttp

WDM_DEVICES_URL = "https://wdm-a.wbx2.com/wdm/api/v1/devices"

DEVICE_DATA = {
    "deviceName": "board-provisioning-bot-ws",
    "deviceType": "DESKTOP",
    "localizedModel": "python",
    "model": "python",
    "name": "board-provisioning-bot-ws",
    "systemName": "board-provisioning-bot-ws",
    "systemVersion": "1.0"
}
def get_device_info(bot_token):
    result = {}
    headers = {
        "Authorization": f"Bearer {bot_token}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.get(WDM_DEVICES_URL, headers=headers)
        if response.status_code == 200:
            devices = response.json().get("devices", [])
            for device in devices:
                if device.get("name") == DEVICE_DATA["name"]:
                    print(f"Using existing device: {device.get('url')}")
                    result = device
                    break
    except Exception as e:
        print(f"Error checking existing devices: {e}")
    return result

async def get_device_info_async(bot_token):
    result = {}
    headers = {
        "Authorization": f"Bearer {bot_token}",
        "Content-Type": "application/json"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(WDM_DEVICES_URL, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    devices = data.get("devices", [])
                    for device in devices:
                        if device.get("name") == DEVICE_DATA["name"]:
                            print(f"Using existing device: {device.get('url')}")
                            result = device
                            break
    except Exception as e:
        print(f"Error checking existing devices: {e}")
    return result

def activity_id_to_message_id(activity_id: str) -> str:
    base_string = f"ciscospark://us/MESSAGE/{activity_id}"
    return b64encode(base_string.encode("utf-8")).decode("utf-8").rstrip("=")


def activity_id_to_attachment_action_id(activity_id: str) -> str:
    base_string = f"ciscospark://us/ATTACHMENT_ACTION/{activity_id}"
    return b64encode(base_string.encode("utf-8")).decode("utf-8").rstrip("=")


def extract_room_id_from_target(target: dict) -> str:
    target_id = target.get("id", "")
    if not target_id:
        return ""
    
    base_string = f"ciscospark://us/ROOM/{target_id}"
    return b64encode(base_string.encode("utf-8")).decode("utf-8").rstrip("=")


def is_bot_id(bot_id: str, person_id: str) -> bool:
    try:
        decoded = base64.b64decode(bot_id + "==").decode("utf-8")
        if "/PEOPLE/" in decoded:
            bot_uuid = decoded.split("/PEOPLE/")[-1]
            return person_id == bot_uuid
    except Exception:
        pass
    
    return person_id == bot_id
