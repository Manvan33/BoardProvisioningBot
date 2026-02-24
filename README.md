# Webex Board Provisioning Bot

A Webex bot that allows authorized users to easily provision Webex Boards and other devices directly from a webex space.

Original idea: https://github.com/agrobys/BoardProvisioningBot

### Why use this bot?

- Do you manage a Control Hub instance and need to frequently add Webex devices? 
- Do you have a space of people who need to retrieve activation codes without needing full Control Hub admin access?
- Do you simply want a quick way to generate device activation codes from your phone or desktop via the Webex App?

If any of those are true, this bot can simplify your workflow.

### How to use the bot

1. **Add to a Space or Direct Message**: Add the bot to a Webex space or send it a direct message.
2. **Authorization**: The first time you interact with the bot, it will send an authorization link. As an organization admin, click the link to authorize the bot using Webex OAuth. This securely links the room to your organization.
3. **Provisioning**: Once authorized, simply mention the bot and say `hello` (e.g., `@BotName hello`). It will reply with a card where you can provide a new workspace name or select an existing one to generate an activation code!
4. **Room Context**: Remember to mention the bot when in a space, as it cannot read other messages. In direct messages, mentioning is not necessary.

### Available Commands

- `hello`: Get a card to provision a board and retrieve an activation code.
- `help`: Print all available commands.
- `add [@person or email]`: Add an authorized user to your organization. You can provide several at once separated by a space. Provided emails must be in your organization. By default, **only the user who authorized the bot** can perform operations using the bot.
- `remove [@person or email]`: Remove a user from your organization's authorized list.
- `info`: Get info about the organization linked to this room and the list of authorized users.
- `details [workspace name]`: Get details about a specific workspace (devices, status, IP). Use **ALL** to get details about all workspaces.
- `reinit` or `reinitialize`: Reinitialize the room. Use this if you want to change the organization linked to the room or re-authorize.

### Security and Scope

- **Authorization**: The bot uses OAuth to securely access your organization's Control Hub. The bot's actions are limited by the scopes granted during the OAuth flow.
- **Room Isolation**: Each Webex space where the bot is added manages its own authorization and list of allowed users.

### Hosting Your Own Bot

To run this code in your own environment, you need to set up a Webex Bot and an Integration for OAuth.

For detailed instructions on setting up your environment, configuring variables, and deploying the bot using Docker (recommended) or systemd, please refer to the [Deployment Guide](deployment/DEPLOYMENT.md).

> If you have any questions, you can contact me at ivanivan@cisco.com
