import orjson


def serialize(obj: object) -> str:
    """Serialize an object to a JSON string."""
    return orjson.dumps(obj).decode("utf-8")


def deserialize(obj: str) -> object:
    """Deserialize a JSON string to an object."""
    return orjson.loads(obj)
