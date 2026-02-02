from __future__ import print_function
import requests
import json
from webexteamssdk import WebexTeamsAPI, ApiError
import helper


class WebexAdmin:

    def __init__(self, my_token: str, room_id: str, use_proxy: bool = False):
        self.my_token = my_token
        self.room_id = room_id
        self.use_proxy = use_proxy
        self.proxies = {
            'http': 'http://127.0.0.1:8080',
            'https': 'http://127.0.0.1:8080'
        } if use_proxy else None
        self.api = WebexTeamsAPI(access_token=self.my_token)
        self.headers = self.get_headers()
        
        self.org_id = ""
        self.my_id = ""
        
        try:
            me = self.api.people.me()
            self.my_id = me.id
            self.org_id = self._get_org_id()
        except ApiError:
            pass

    def _get_org_id(self) -> str:
        try:
            response = requests.get(
                url='https://webexapis.com/v1/people/me',
                headers=self.headers,
                proxies=self.proxies,
                verify=not self.use_proxy
            )
            if response.status_code == 200:
                return response.json().get("orgId", "")
        except Exception as e:
            print(f"Error getting org ID: {e}")
        return ""

    def token_is_valid(self):
        if not self.org_id:
            self.org_id = self._get_org_id()
            if not self.org_id:
                print("Token assumed invalid: could not get org ID")
                return False
        
        response = requests.get(
            url=f'https://webexapis.com/v1/workspaces?orgId={self.org_id}',
            headers=self.headers,
            proxies=self.proxies,
            verify=not self.use_proxy
        )
        response = helper.load_text(response)
        if isinstance(response, dict) and "items" in response.keys():
            print("Token valid.")
            return True
        else:
            print(f"Token assumed invalid. Response received: {response}")
            return False

    def update_token(self, token):
        self.my_token = token
        self.headers = self.get_headers()
        self.api = WebexTeamsAPI(access_token=self.my_token)
        try:
            self.my_id = self.api.people.me().id
            self.org_id = self._get_org_id()
        except ApiError:
            self.my_id = ""
            self.org_id = ""
        return self.my_id

    def get_headers(self) -> dict:
        return {
            "Authorization": "Bearer " + self.my_token,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def get_workspace_id(self, workspace_name) -> str:
        if not self.org_id:
            return ""
        
        workspace_id = ""
        try:
            response = requests.get(
                url=f'https://webexapis.com/v1/workspaces?orgId={self.org_id}&displayName={workspace_name}',
                headers=self.headers,
                proxies=self.proxies,
                verify=not self.use_proxy
            )
        except Exception:
            return ""
        
        if helper.is_json(response) and "items" in response.json().keys():
            for workspace in response.json()["items"]:
                workspace_id = workspace["id"]
        else:
            print(f"Something went wrong. Response: {helper.load_text(response)}")
            return ""
        
        if workspace_id == "":
            print(f"Creating workspace {workspace_name}.")
            payload = {
                "displayName": workspace_name,
                "orgId": self.org_id
            }
            try:
                response = requests.post(
                    url="https://webexapis.com/v1/workspaces",
                    data=json.dumps(payload),
                    headers=self.headers,
                    proxies=self.proxies,
                    verify=not self.use_proxy
                )
            except Exception:
                return ""
            
            if helper.is_json(response):
                workspace_id = json.loads(response.content)["id"]
            else:
                print(f"Something went wrong. Response: {helper.load_text(response)}")
                return ""
        else:
            print(f"Workspace {workspace_id} exists.")
        
        return workspace_id

    def get_activation_code(self, workspace_name, model=None) -> str:
        if not self.token_is_valid():
            return ""
        
        workspace_id = self.get_workspace_id(workspace_name)
        if workspace_id == "":
            return ""
        
        payload = {"workspaceId": workspace_id}
        if model:
            payload["model"] = model
        
        try:
            response = requests.post(
                url=f"https://webexapis.com/v1/devices/activationCode?orgId={self.org_id}",
                data=json.dumps(payload),
                headers=self.headers,
                proxies=self.proxies,
                verify=not self.use_proxy
            )
        except Exception:
            return ""
        
        if helper.is_json(response):
            activation_code = json.loads(response.content)["code"]
            return activation_code
        else:
            print(f"Something went wrong. Response: {helper.load_text(response)}")
            return ""

    def save(self):
        return {
            "admin_token": self.my_token,
            "org_id": self.org_id
        }
