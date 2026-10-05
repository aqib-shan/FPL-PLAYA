def create_player_schema(player_list : list[str]) -> dict:
    """
    Generate a ResponseSchema object based on a dynamic list of player names.
    This should ensure enforcement to the player names in the JSON response.

    Args:
        player_list (list[str]): List of player names.

    Returns:
        dict: Schema object for LLM.
    """
    # Construct the JSON schema properties
    properties = {player: {"type": "string"} for player in player_list}
    
    schema = {
        "type": "object",
        "properties": properties,
        "required": player_list
    }
    
    return schema


def create_team_creation_schema() -> dict:
    """Generate a team creation response schema."""
    return {
        "type": "object",
        "properties": {
            "team": {
                "type": "object",
                "properties": {
                    "captain": {"type": "string"},
                    "vice_captain": {"type": "string"},
                    "captain_reason": {"type": "string"},
                    "vice_captain_reason": {"type": "string"},
                    "total_cost": {"type": "number"},
                    "bank": {"type": "number"},
                    "expected_points": {"type": "number"},
                    "starting": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "position": {"type": "string"},
                                "price": {"type": "number"},
                                "team": {"type": "string"},
                                "reason": {"type": "string"}
                            },
                            "required": ["name", "position", "price", "team", "reason"]
                        }
                    },
                    "substitutes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "position": {"type": "string"},
                                "price": {"type": "number"},
                                "team": {"type": "string"},
                                "sub_order": {"type": "number"},
                                "reason": {"type": "string"}
                            },
                            "required": ["name", "position", "price", "team", "sub_order", "reason"]
                        }
                    }
                },
                "required": ["captain", "vice_captain", "captain_reason", "vice_captain_reason", "total_cost", "bank", "expected_points", "starting", "substitutes"]
            }
        },
        "required": ["team"]
    }


def create_weekly_update_schema() -> dict:
    """Generate a weekly update response schema."""
    return {
        "type": "object",
        "properties": {
            "team": {
                "type": "object",
                "properties": {
                    "chip": {"type": "string"},
                    "chip_reason": {"type": "string"},
                    "transfers": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "player_in": {"type": "string"},
                                "player_in_price": {"type": "number"},
                                "player_out": {"type": "string"},
                                "player_out_price": {"type": "number"},
                                "reason": {"type": "string"}
                            },
                            "required": ["player_in", "player_in_price", "player_out", "player_out_price", "reason"]
                        }
                    },
                    "captain": {"type": "string"},
                    "vice_captain": {"type": "string"},
                    "captain_reason": {"type": "string"},
                    "vice_captain_reason": {"type": "string"},
                    "total_cost": {"type": "number"},
                    "bank": {"type": "number"},
                    "expected_points": {"type": "number"},
                    "starting": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "position": {"type": "string"},
                                "price": {"type": "number"},
                                "team": {"type": "string"},
                                "reason": {"type": "string"}
                            },
                            "required": ["name", "position", "price", "team", "reason"]
                        }
                    },
                    "substitutes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "position": {"type": "string"},
                                "price": {"type": "number"},
                                "team": {"type": "string"},
                                "sub_order": {"type": "number"},
                                "reason": {"type": "string"}
                            },
                            "required": ["name", "position", "price", "team", "sub_order", "reason"]
                        }
                    }
                },
                "required": ["chip", "chip_reason", "transfers", "captain", "vice_captain", 
                            "captain_reason", "vice_captain_reason", "total_cost", "bank", 
                            "expected_points", "starting", "substitutes"]
            }
        },
        "required": ["team"]
    }