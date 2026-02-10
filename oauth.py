#!/usr/bin/env python3
"""
Webex Integration OAuth Flow Handler

This module handles the OAuth 2.0 authorization flow for Webex Integrations.
It spins up a local HTTP server to receive the OAuth callback and exchange
the authorization code for access and refresh tokens.

Usage:
    1. Set environment variables in .env:
       - OAUTH_CLIENT_ID
       - OAUTH_CLIENT_SECRET
       - OAUTH_REDIRECT_URI (default: http://127.0.0.1:9999/auth)
    
    2. Run: python3 oauth.py
    
    3. Open the printed URL in your browser and authorize the app
    
    4. Tokens will be saved to oauth_tokens.json
"""

import http.server
import json
import os
import secrets
import socketserver
import sys
import threading
import webbrowser
from urllib.parse import urlencode, urlparse, parse_qs

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Webex OAuth endpoints
WEBEX_AUTH_URL = "https://webexapis.com/v1/authorize"
WEBEX_TOKEN_URL = "https://webexapis.com/v1/access_token"

# spark-admin:devices_read Identity:one_time_password spark:people_read spark-admin:organizations_read spark-admin:workspaces_read spark-admin:devices_write spark-compliance:rooms_read&state=set_state_here

DEFAULT_SCOPES = [
    "spark-compliance:memberships_read",
    "spark-admin:workspaces_write",
    "spark:kms",
    "spark-admin:devices_read",
    "Identity:one_time_password",
    "spark:people_read",
    "spark-admin:organizations_read",
    "spark-admin:workspaces_read",
    "spark-admin:devices_write",
    "spark-compliance:rooms_read",
    "spark:xapi_statuses"
]


# Token storage file
TOKEN_FILE = "oauth_tokens.json"


class OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    auth_code = None
    received_state = None
    error = None
    callback_path = "/auth"
    
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == OAuthCallbackHandler.callback_path:
            query_params = parse_qs(parsed_path.query)
            
            # Check for error
            if "error" in query_params:
                OAuthCallbackHandler.error = query_params.get("error", ["Unknown error"])[0]
                error_desc = query_params.get("error_description", ["No description"])[0]
                self._send_response(
                    500,
                    f"<h1>Authorization Failed</h1><p>Error: {OAuthCallbackHandler.error}</p>"
                    f"<p>Description: {error_desc}</p>"
                )
                return
            
            # Get authorization code and state
            if "code" in query_params:
                OAuthCallbackHandler.auth_code = query_params["code"][0]
                OAuthCallbackHandler.received_state = query_params.get("state", [None])[0]
                self._send_response(
                    200,
                    "<h1>Authorization Successful!</h1>"
                    "<p>You can close this window and return to the terminal.</p>"
                    "<script>window.close();</script>"
                )
            else:
                self._send_response(
                    400,
                    "<h1>Missing Authorization Code</h1>"
                    "<p>The callback did not include an authorization code.</p>"
                )
        else:
            self._send_response(404, "<h1>Not Found</h1>")
    
    def _send_response(self, status_code: int, body: str):
        """Send HTTP response."""
        self.send_response(status_code)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body.encode())


class OAuthFlow:
    """Handles the complete OAuth 2.0 flow for Webex Integrations."""
    
    def __init__(
        self,
        client_id: str = None,
        client_secret: str = None,
        redirect_uri: str = None,
        scopes: list = None
    ):
        """
        Initialize OAuth flow.
        
        Args:
            client_id: OAuth client ID (or set OAUTH_CLIENT_ID env var)
            client_secret: OAuth client secret (or set OAUTH_CLIENT_SECRET env var)
            redirect_uri: Redirect URI (or set OAUTH_REDIRECT_URI env var)
            scopes: List of OAuth scopes (defaults to device provisioning scopes)
        """
        self.client_id = client_id or os.getenv("OAUTH_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("OAUTH_CLIENT_SECRET")
        self.redirect_uri = redirect_uri or os.getenv("OAUTH_REDIRECT_URI", "http://127.0.0.1:9999/auth")
        self.scopes = scopes or DEFAULT_SCOPES
        
        # Validate required parameters
        if not self.client_id:
            raise ValueError("Missing OAUTH_CLIENT_ID. Set it in .env or pass client_id parameter.")
        if not self.client_secret:
            raise ValueError("Missing OAUTH_CLIENT_SECRET. Set it in .env or pass client_secret parameter.")
        
        # Parse redirect URI for server configuration
        parsed_uri = urlparse(self.redirect_uri)
        self.callback_host = parsed_uri.hostname or "localhost"
        self.callback_port = parsed_uri.port or 8080
        self.callback_path = parsed_uri.path or "/callback"
        
        # Generate state for CSRF protection
        self.state = secrets.token_urlsafe(32)
        
        # Token storage
        self.tokens = None
    
    def get_authorization_url(self) -> str:
        """
        Generate the authorization URL for the user to visit.
        
        Returns:
            The full authorization URL
        """
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.scopes),
            "state": self.state,
        }
        return f"{WEBEX_AUTH_URL}?{urlencode(params)}"
    
    def exchange_code_for_tokens(self, auth_code: str) -> dict:
        """
        Exchange authorization code for access and refresh tokens.
        
        Args:
            auth_code: The authorization code from the callback
            
        Returns:
            Dictionary containing access_token, refresh_token, expires_in, etc.
        """
        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": auth_code,
            "redirect_uri": self.redirect_uri,
        }
        
        response = requests.post(WEBEX_TOKEN_URL, data=data)
        
        if response.status_code != 200:
            raise Exception(f"Token exchange failed: {response.status_code} - {response.text}")
        
        self.tokens = response.json()
        return self.tokens
    
    def refresh_tokens(self, refresh_token: str = None) -> dict:
        """
        Refresh the access token using the refresh token.
        
        Args:
            refresh_token: The refresh token (uses stored token if not provided)
            
        Returns:
            Dictionary containing new access_token, refresh_token, expires_in, etc.
        """
        token = refresh_token or (self.tokens and self.tokens.get("refresh_token"))
        if not token:
            raise ValueError("No refresh token available")
        
        data = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": token,
        }
        
        response = requests.post(WEBEX_TOKEN_URL, data=data)
        
        if response.status_code != 200:
            raise Exception(f"Token refresh failed: {response.status_code} - {response.text}")
        
        self.tokens = response.json()
        return self.tokens
    
    def save_tokens(self, filepath: str = TOKEN_FILE):
        """Save tokens to a JSON file."""
        if not self.tokens:
            raise ValueError("No tokens to save")
        
        with open(filepath, "w") as f:
            json.dump(self.tokens, f, indent=2)
        print(f"Tokens saved to {filepath}")
    
    def load_tokens(self, filepath: str = TOKEN_FILE) -> dict:
        """Load tokens from a JSON file."""
        if not os.path.exists(filepath):
            return None
        
        with open(filepath, "r") as f:
            self.tokens = json.load(f)
        return self.tokens
    
    def run_callback_server(self, timeout: int = 120) -> str:
        OAuthCallbackHandler.auth_code = None
        OAuthCallbackHandler.received_state = None
        OAuthCallbackHandler.error = None
        OAuthCallbackHandler.callback_path = self.callback_path
        
        with socketserver.TCPServer(
            (self.callback_host, self.callback_port),
            OAuthCallbackHandler
        ) as httpd:
            httpd.timeout = timeout
            
            print(f"Waiting for OAuth callback on {self.redirect_uri}...")
            print(f"(Timeout: {timeout} seconds)")
            
            while OAuthCallbackHandler.auth_code is None and OAuthCallbackHandler.error is None:
                httpd.handle_request()
            
            if OAuthCallbackHandler.error:
                raise Exception(f"OAuth error: {OAuthCallbackHandler.error}")
            
            if OAuthCallbackHandler.received_state != self.state:
                raise Exception("State mismatch - possible CSRF attack")
            
            return OAuthCallbackHandler.auth_code
    
    def run_flow(self, open_browser: bool = False, timeout: int = 120) -> dict:
        """
        Run the complete OAuth flow.
        
        Args:
            open_browser: Whether to automatically open the browser
            timeout: Maximum time to wait for callback (seconds)
            
        Returns:
            Dictionary containing the tokens
        """
        # Generate authorization URL
        auth_url = self.get_authorization_url()
        
        print("\n" + "=" * 60)
        print("WEBEX OAUTH AUTHORIZATION")
        print("=" * 60)
        print(f"\nPlease visit this URL to authorize the application:\n")
        print(auth_url)
        print()
        
        if open_browser:
            print("Opening browser...")
            webbrowser.open(auth_url)
        
        # Wait for callback
        auth_code = self.run_callback_server(timeout=timeout)
        
        print("\nAuthorization code received!")
        print("Exchanging code for tokens...")
        
        # Exchange code for tokens
        tokens = self.exchange_code_for_tokens(auth_code)
        
        print("\nTokens received successfully!")
        print(f"  Access Token: {tokens['access_token'][:20]}...")
        print(f"  Expires In: {tokens.get('expires_in', 'N/A')} seconds")
        print(f"  Refresh Token: {tokens.get('refresh_token', 'N/A')[:20]}...")
        
        # Save tokens
        self.save_tokens()
        
        return tokens


def main():
    """Run the OAuth flow from command line."""
    print("Webex Integration OAuth Flow")
    print("-" * 40)
    
    try:
        oauth = OAuthFlow()
        tokens = oauth.run_flow()
        
        print("\n" + "=" * 60)
        print("SUCCESS!")
        print("=" * 60)
        print(f"\nTokens have been saved to {TOKEN_FILE}")
        print("\nYou can now use these tokens in your application.")
        
        return tokens
        
    except ValueError as e:
        print(f"\nConfiguration Error: {e}")
        print("\nPlease ensure you have set the following in your .env file:")
        print("  OAUTH_CLIENT_ID=your_client_id")
        print("  OAUTH_CLIENT_SECRET=your_client_secret")
        print("  OAUTH_REDIRECT_URI=http://localhost:8080/callback  (optional)")
        sys.exit(1)
        
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
