import json
import os

STORAGE_PATH = "storage.json"

def save_ticket_context(ticket_id: str, conversation_reference: dict, activity_id: str):
    data = {}
    if os.path.exists(STORAGE_PATH):
        with open(STORAGE_PATH, "r") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {}
    data[ticket_id] = {
        "conversation_reference": conversation_reference.serialize(),
        "activity_id": activity_id
    }
    with open(STORAGE_PATH, "w") as f:
        json.dump(data, f, indent=4)

def get_ticket_context(ticket_id: str):
    if not os.path.exists(STORAGE_PATH):
        return None
    with open(STORAGE_PATH, "r") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return None
    return data.get(ticket_id)

def get_ticket_id_by_activity(activity_id: str):
    if not os.path.exists(STORAGE_PATH):
        return None
    with open(STORAGE_PATH, "r") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return None
    for ticket_id, context in data.items():
        if context.get("activity_id") == activity_id:
            return ticket_id
    return None
