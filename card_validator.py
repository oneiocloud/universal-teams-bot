import json
import urllib.request
from jsonschema import validate, ValidationError

_schema_cache = None

def _load_schema():
    global _schema_cache
    if _schema_cache is None:
        with urllib.request.urlopen("https://adaptivecards.io/schemas/adaptive-card.json") as response:
            _schema_cache = json.load(response)
    return _schema_cache

def validate_card(card_json: dict) -> bool:
    schema = _load_schema()
    try:
        validate(instance=card_json, schema=schema)
        return True
    except ValidationError as e:
        raise ValueError(f"Invalid Adaptive Card: {e.message}") from e
