#!/usr/bin/env python3
from datetime import date
import secrets
import time
from urllib.parse import urlencode, urlparse
from aiohttp import web

from oauth import OAuthFlow, DEFAULT_SCOPES, WEBEX_AUTH_URL

REDIRECT_URI = "http://127.0.0.1:9999/auth"

class OAuthManager:
    def __init__(self, client_id: str, client_secret: str, tokens_store_function):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = REDIRECT_URI
        self.scopes = DEFAULT_SCOPES
        self.tokens_store_function = tokens_store_function
        
        parsed_uri = urlparse(self.redirect_uri)
        self.callback_host = parsed_uri.hostname or "127.0.0.1"
        self.callback_port = parsed_uri.port or 9999
        self.callback_path = parsed_uri.path or "/auth"
        
        self.pending_auth: dict[str, dict] = {}
        
        self._oauth_flow = OAuthFlow(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=self.redirect_uri,
            scopes=self.scopes
        )
        
    
    def create_auth_url(self, room_id: str) -> str:
        state = secrets.token_urlsafe(32)
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
            return web.Response(
                status=400,
                content_type="text/html",
                text=f"<h1>Authorization Failed</h1><p>Error: {error}</p><p>{error_desc}</p>"
            )
        
        code = query_params.get("code")
        state = query_params.get("state")
        
        if not code or not state:
            return web.Response(
                status=400,
                content_type="text/html",
                text="<h1>Missing Parameters</h1><p>Authorization code or state missing.</p>"
            )
        
        auth_data = self.validate_state(state)
        if not auth_data:
            return web.Response(
                status=400,
                content_type="text/html",
                text="<h1>Invalid or Expired State</h1><p>Please try the authorization again.</p>"
            )
        
        room_id = auth_data["room_id"]
        
        try:
            tokens = self.exchange_code_for_tokens(code)
            access_token = tokens["access_token"]
            refresh_token = tokens.get("refresh_token")
            expires_in = tokens.get("expires_in", 0)       
            self.tokens_store_function(
                room_id,
                access_token,
                refresh_token,
                date.fromtimestamp(time.time() + expires_in) if expires_in else None
            )
            return web.Response(
                status=200,
                content_type="text/html",
                text="<h1>Authorization Successful!</h1><p>You can close this window and return to Webex.</p><script>window.close();</script>"
            )
            
        except Exception as e:
            print(f"OAuth callback error: {e}")
            return web.Response(
                status=500,
                content_type="text/html",
                text=f"<h1>Authorization Failed</h1><p>{e}</p>"
            )

    async def _start_http_server(self) -> None:
        app = web.Application()
        app.router.add_get(self.callback_path, self.handle_oauth_callback)
        
        self.http_runner = web.AppRunner(app)
        await self.http_runner.setup()
        self.http_site = web.TCPSite(
            self.http_runner,
            self.callback_host,
            self.callback_port
        )
        await self.http_site.start()
        print(f"OAuth callback server running on {self.redirect_uri}")
    async def _stop_http_server(self) -> None:
        if self.http_runner:
            await self.http_runner.cleanup()
