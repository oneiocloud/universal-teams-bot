import json
import os
import logging

STORAGE_PATH = "storage.json"

def save_ticket_context(ticket_id: str, conversation_reference: dict, activity_id: str):
    ticket_id = str(ticket_id)
    data = {}
    try:
        if os.path.exists(STORAGE_PATH):
            with open(STORAGE_PATH, "r") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    logging.warning("storage file exists but could not be decoded. Starting fresh.")
                    data = {}

        serialized_ref = conversation_reference.serialize()
        data[ticket_id] = {
            "conversation_reference": serialized_ref,
            "activity_id": activity_id
        }

        with open(STORAGE_PATH, "w") as f:
            json.dump(data, f, indent=4)
        logging.info(f"Saved context for ticket_id={ticket_id}")
    except Exception as e:
        logging.error(f"Failed to save ticket context for ticket_id={ticket_id}: {e}")

def get_ticket_context(ticket_id: str):
    ticket_id = str(ticket_id)
    if not os.path.exists(STORAGE_PATH):
        logging.warning(f"storage file does not exist at: {os.path.abspath(STORAGE_PATH)}")
        return None
    try:
        with open(STORAGE_PATH, "r") as f:
            data = json.load(f)
        context = data.get(ticket_id)
        if context:
            logging.info(f"Retrieved context for ticket_id={ticket_id}: {context}")
        else:
            logging.warning(f"No context found for ticket_id={ticket_id}")
        return context
    except Exception as e:
        logging.error(f"Failed to load ticket context for ticket_id={ticket_id}: {e}")
        return None

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
