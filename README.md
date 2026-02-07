# Webex Board Provisioning Bot

Credits go to @schachem for his echo bot which I used as a skeleton to build the test version for this bot! Find it at: https://github.com/schachem/EchoBot.

### Why use this bot?

- Do you have a Control Hub instance that you use to add Webex devices? 
- Do you have a space of people who you'd like to retrieve activation codes without having to ask you to do it for them? 
- Do you simply want to create a device activation code from the Webex App?

If any of those are true, this bot could make your life a bit easier. 

### How to interact with the bot:

- Add it to a Webex space or direct message it (email: **board-provisioning@webex.bot**).
- It will send you an initialization card. Fill it out with your organization ID and personal Webex API access token (you have to be admin for that organization). You can find your personal temporary access token on developer.webex.com under Documentation -> Access The API and your organization ID on the Webex Control Hub under Account. To get the organization ID usable with the API, send a GET to https://webexapis.com/v1/organizations/{orgId}. You can do this easily at https://developer.webex.com/docs/api/v1/organizations/get-organization-details. The ID you need will be in the response payload.
- After initialization, mention the bot and it will send you a card. Fill out the card with a workspace name, submit, and get your code!
- Remember to mention the bot when in a space, it cannot see your message otherwise. In direct messages, this is not necessary.

### Other commands:

- ```help```: Print all available commands
- ```add [email]```: Add an authorized user to your organization. You can provide several at once separated by a space. Provided emails must be in your organization.  By default, **only the admin** can perform operations using the bot. If you have the bot in several spaces for the same organization, the list of authorized users will be **the same** for each space.
- ```remove [email]```: Remove a user from your organization's authorized list.
- ```token [token]```: Update your access token. If you're using a temporary token, it is only valid for 48hrs. If you do not wish to expose your access token to everyone in a message, use the ```reinit``` command instead.
- ```reinit```: Reinitialize the bot. Do this if you wish to use it for a different organization in this room or if you need to update your token.

### Be aware that:

- Anyone who has the admin's access token can perform any API operations on your organization's Control Hub. Don't paste it in the chat carelessly.

>If you have any questions, contact me at agrobys@cisco.com. 

### Do you want your own bot?

To run this code in your own environment, you need to:

1. Create your own bot at https://developer.webex.com/my-apps/new/bot. Make sure to save the bot access token.
2. Create an Integration at https://developer.webex.com/my-apps/new/integration to handle OAuth. Save the Client ID and Client Secret.
3. Have somewhere to run it. Mine runs on a Debian Linux VM, but anything with Python should work. Create a directory with the code.
4. Install `uv` if you haven't already: https://github.com/astral-sh/uv
5. Set up environment variables in a `.env` file (see `.env.example`):
   - `BOT_TOKEN`: Your bot's access token.
   - `OAUTH_CLIENT_ID`: Your integration's Client ID.
   - `OAUTH_CLIENT_SECRET`: Your integration's Client Secret.
   - `OAUTH_REDIRECT_URI`: The redirect URI for OAuth (default: http://127.0.0.1:9999/auth).
6. Run the bot using `uv`:
   ```bash
   uv run bot_ws.py
   ```
