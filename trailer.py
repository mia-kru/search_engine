import json

    def get_key(
            response_text: str,
            platform: str = "youtube",
            allowed_langs: tuple[str, ...] = ("de", "en"),
    ) -> str | None:
    try:
        data = json.loads(response_text)
        # print(data)
    except (ValueError, json.JSONDecodeError):
        data = {}

    trailers = [
        v for v in data.get("results", [])
        if isinstance(v, dict)
        and v.get("site", "").lower() == platform
        and v.get("type", "").lower() == "trailer"
        and v.get("iso_639_1", "").lower() in allowed_langs
    ]

    key = None
    if trailers and isinstance(trailers[0], dict):
        key = trailers[0].get("key")
    return key