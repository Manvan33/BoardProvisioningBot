#!/usr/bin/env python3
import base64
import datetime
import secrets
import time
from urllib.parse import urlencode, urlparse
from aiohttp import web
from jinja2 import Environment, FileSystemLoader, select_autoescape

from oauth import OAuthFlow, DEFAULT_SCOPES, WEBEX_AUTH_URL


class OAuthManager:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str, tokens_store_function):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scopes = DEFAULT_SCOPES
        self.tokens_store_function = tokens_store_function
        self.callback_path = urlparse(self.redirect_uri).path
        
        self.pending_auth: dict[str, dict] = {}
        
        self._oauth_flow = OAuthFlow(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=self.redirect_uri,
            scopes=self.scopes
        )
        
        self.jinja_env = Environment(
            loader=FileSystemLoader("templates"),
            autoescape=select_autoescape()
        )

    
    def get_uuid_from_id(self, id: str) -> str:
        try:
            # Add padding just in case
            missing_padding = len(id) % 4
            if missing_padding:
                id += '=' * (4 - missing_padding)
            decoded = base64.b64decode(id).decode("utf-8")
            if "/ROOM/" in decoded:
                return decoded.split('/')[-1]
            return ""
        except Exception as e:
            print(f"Error decoding room ID: {e}")
            return ""

    def create_auth_url(self, room_id: str, request_id: str) -> str:
        state = request_id
        self.pending_auth[state] = {
            "room_id": room_id,
            "created_at": time.time()
        }
        
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.scopes),
            "state": state,
        }
        return f"{WEBEX_AUTH_URL}?{urlencode(params)}"
    
    def exchange_code_for_tokens(self, auth_code: str) -> dict:
        return self._oauth_flow.exchange_code_for_tokens(auth_code)
    
    def refresh_tokens(self, refresh_token: str) -> dict:
        return self._oauth_flow.refresh_tokens(refresh_token)
    
    def validate_state(self, state: str) -> dict | None:
        if state not in self.pending_auth:
            return None
        
        auth_data = self.pending_auth.pop(state)
        if time.time() - auth_data["created_at"] > 600:
            return None
        
        return auth_data

    async def handle_oauth_callback(self, request: web.Request) -> web.Response:
        query_params = request.query
        
        if "error" in query_params:
            error = query_params.get("error", "Unknown error")
            error_desc = query_params.get("error_description", "No description")
            template = self.jinja_env.get_template("oauth_error.html")
            return web.Response(
                status=400,
                content_type="text/html",
                text=template.render(error=error, error_description=error_desc)
            )
        
        code = query_params.get("code")
        state = query_params.get("state")
        
        if not code or not state:
            template = self.jinja_env.get_template("oauth_error.html")
            return web.Response(
                status=400,
                content_type="text/html",
                text=template.render(error="Missing Parameters", error_description="Authorization code or state missing.")
            )
        
        auth_data = self.validate_state(state)
        if not auth_data:
            template = self.jinja_env.get_template("oauth_error.html")
            return web.Response(
                status=400,
                content_type="text/html",
                text=template.render(error="Invalid or Expired State", error_description="Please try the authorization again.")
            )
        
        room_id = auth_data["room_id"]
        
        try:
            tokens = self.exchange_code_for_tokens(code)
            access_token = tokens["access_token"]
            refresh_token = tokens.get("refresh_token")
            expires_in = tokens.get("expires_in", 0)       
            self.tokens_store_function(
                room_id,
                state,
                access_token,
                refresh_token,
                datetime.datetime.fromtimestamp(time.time() + expires_in) if expires_in else None
            )

            space_uuid = self.get_uuid_from_id(room_id)
            template = self.jinja_env.get_template("oauth_success.html")

            return web.Response(
                status=200,
                content_type="text/html",
                text=template.render(space_uuid=space_uuid)
            )
            
        except Exception as e:
            print(f"OAuth callback error: {e}")
            template = self.jinja_env.get_template("oauth_error.html")
            return web.Response(
                status=500,
                content_type="text/html",
                text=template.render(error="Internal Server Error", error_description=str(e))
            )

    async def _start_http_server(self) -> None:
        app = web.Application()
        app.router.add_get(self.callback_path, self.handle_oauth_callback)
        
        self.http_runner = web.AppRunner(app)
        await self.http_runner.setup()
        self.http_site = web.TCPSite(
            self.http_runner,
            '127.0.0.1',
            9999
        )
        await self.http_site.start()
        print(f"OAuth callback server running on {self.redirect_uri}")
    async def _stop_http_server(self) -> None:
        if self.http_runner:
            await self.http_runner.cleanup()
