from __future__ import print_function
import requests
import json
from webexteamssdk import WebexTeamsAPI, ApiError
import helper


class WebexAdmin:

    def __init__(self, my_token: str, use_proxy: bool = False):
        self.my_token = my_token
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
            self.my_email = me.emails[0] if me.emails else ""
            self.name = me.displayName
            self.my_id = me.id
            self.org_id = me.orgId
            self.org_name = self._get_org_name()
        except ApiError:
            print('Invalid token provided.')
            pass

    def _get_org_name(self) -> str:
        self.api.organizations.get(self.org_id)
        return self.api.organizations.get(self.org_id).displayName

    def token_is_valid(self):
        try:
            response = requests.get(
                url=f'https://webexapis.com/v1/workspaces?orgId={self.org_id}',
                headers=self.headers,
                proxies=self.proxies,
                verify=not self.use_proxy
            )
            if response.status_code / 100 != 2:
                return False
            return True
        except Exception:
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

    def _get_all_items(self, url):
        items = []
        while url:
            try:
                response = requests.get(
                    url=url,
                    headers=self.headers,
                    proxies=self.proxies,
                    verify=not self.use_proxy
                )
                if helper.is_json(response) and "items" in response.json().keys():
                    items.extend(response.json()["items"])

                    # Check for Link header for pagination
                    links = response.headers.get("Link")
                    next_url = None
                    if links:
                        parts = links.split(",")
                        for part in parts:
                            if 'rel="next"' in part:
                                next_url = part.split(";")[0].strip("<> ")
                                break
                    url = next_url
                else:
                    print(f"Something went wrong. Response: {helper.load_text(response)}")
                    break
            except Exception as e:
                print(f"Error fetching items: {e}")
                break
        return items

    def create_workspace(self, workspace_name) -> str:
        if not self.org_id:
            return ""
        
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
        
        return workspace_id

    def list_workspaces(self) -> dict:
        url_workspaces = f'https://webexapis.com/v1/workspaces?orgId={self.org_id}'
        workspaces = self._get_all_items(url_workspaces)
        result = {}
        for workspace in workspaces:
            ws_id = workspace["id"]
            name = workspace["displayName"]
            result[ws_id] = name
        return result
    
    def list_workspaces_with_devices(self) -> dict:
        result = {}
        workspaces = self.list_workspaces()
        for workspace_id, workspace_name in workspaces.items():
            devices = self.get_devices(workspace_id)
            result[workspace_id] = f"{workspace_name} - {len(devices)} device{'s' if devices and len(devices) != 1 else ''}" if devices is not None else workspace_name
        return result
    
    def get_activation_code(self, new_workspace_name, existing_workspace_id, model=None) -> str:
        if not self.token_is_valid():
            return ""
        
        if new_workspace_name:
            workspace_id = self.create_workspace(new_workspace_name)
        else:
            workspace_id = existing_workspace_id
        
        payload = {"workspaceId": workspace_id}
        
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

    def get_workspace_id(self, name) -> str:
        workspaces = self.list_workspaces()
        for id, display_name in workspaces.items():
            if display_name == name:
                return id
        return ""

    def get_devices(self, workspace_id) -> list:
        if not self.org_id:
            return None

        try:
            response = requests.get(
                url=f'https://webexapis.com/v1/devices?workspaceId={workspace_id}',
                headers=self.headers,
                proxies=self.proxies,
                verify=not self.use_proxy
            )
        except Exception:
            return None

        if helper.is_json(response) and "items" in response.json().keys():
            return response.json()["items"]
        else:
            print(f"Something went wrong. Response: {helper.load_text(response)}")
            return None

    def save(self):
        return {
            "admin_token": self.my_token,
            "org_id": self.org_id
        }
