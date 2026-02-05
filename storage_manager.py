#!/usr/bin/env python3
"""StorageManager - Handles local storage for bot data with migration support.

This module provides a centralized storage interface that:
1. Stores bot configuration and room data in nested JSON format
2. Migrates from old flat format to new nested format transparently
3. Provides data accessors that maintain compatibility with existing code
"""

import json
from pathlib import Path


class StorageManager:
    """Manages bot local storage with format migration support."""

    def __init__(self, fileLocation: Path):
        """Initialize storage manager."""
        self._fileLocation = fileLocation
        self._data = {}
        with open(fileLocation) as f:
            try:
                self._data = json.load(f)
            except json.JSONDecodeError:
                self._data = {}

        # Migration: Ensure rooms is a dictionary
        rooms = self._data.get("rooms")
        if rooms is None:
            self._data["rooms"] = {}
        elif isinstance(rooms, list):
            # Migrate list to dict
            rooms_dict = {}
            for room in rooms:
                rid = room.get("room_id")
                if rid:
                    rooms_dict[rid] = room
            self._data["rooms"] = rooms_dict

    def save(self) -> None:
        """Save data to JSON file."""
        with open(self._fileLocation, "w") as f:
            json.dump(self._data, f, indent=4)

    def get_rooms(self) -> list:
        """Get all rooms.

        Returns:
            List of room dictionaries
        """
        return list(self._data.get("rooms", {}).values())

    def add_room(self, room_id: str, room_name, room_admin_email=None, room_admin_id=None) -> dict:
        """Add a new room to storage."""
        if "rooms" not in self._data:
            self._data["rooms"] = {}

        room = {
            "room_id": room_id,
            "room_name": room_name,
            "room_admin": {
                "email": room_admin_email,
                "id": room_admin_id
            },
            "room_authorized_users": [],
            "managed_org": {}
        }
        self._data["rooms"][room_id] = room
        return room

    def remove_room(self, room_id: str) -> bool:
        """Remove a room from storage."""
        rooms = self._data.get("rooms", {})
        if room_id in rooms:
            del rooms[room_id]
            return True
        return False

    def get_room(self, room_id: str) -> dict | None:
        return self._data.get("rooms", {}).get(room_id)
