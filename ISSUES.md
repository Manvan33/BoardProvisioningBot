# Backlog

## Feature: Support Device Model Selection
**Status**: Pending
**Description**: The bot currently does not allow users to select a device model when provisioning. There is commented-out code in `bot.py` suggesting this feature was intended.
**Tasks**:
- Update `make_code_card` to include model selection.
- Update `handle_card` in `bot.py` to read the model.
- Pass model to `admin.get_activation_code`.

## Feature: Handle Bot Removal from Room
**Status**: Pending
**Description**: When the bot is removed from a room, it should clean up the `room_to_org` and `room_to_admin` mappings.
**Tasks**:
- Implement `handle_removed` in `bot.py`.
- Ensure webhook for `memberships` `deleted` event is working.

## Bug: Fix Helper Module and Card Initialization
**Status**: Pending
**Description**: `helper.py` is missing `create_admin` and `make_init_card`. Also, `make_code_card` requires arguments but is called without them in `bot.py` `__init__`.
**Tasks**:
- Implement `make_init_card` in `helper.py`.
- Implement `create_admin` in `helper.py`.
- Refactor `bot.py` to generate `code_card` dynamically with `workspaces` data.

## Bug: Webhook Filter Issue
**Status**: Pending
**Description**: README mentions an error with `personId` in webhooks.
**Tasks**:
- Verify and fix webhook creation in `webhooks.py`.
