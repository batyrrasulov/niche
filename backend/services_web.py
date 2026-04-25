import httpx


async def search_web(query: str, limit: int = 3) -> list[dict]:
    params = {
        "q": query,
        "format": "json",
        "no_html": 1,
        "no_redirect": 1,
        "skip_disambig": 1,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get("https://api.duckduckgo.com/", params=params)
        response.raise_for_status()
    payload = response.json()

    results: list[dict] = []
    abstract = payload.get("AbstractText", "")
    abstract_url = payload.get("AbstractURL", "")
    heading = payload.get("Heading", "") or "DuckDuckGo abstract"
    if abstract:
        results.append({"title": heading, "url": abstract_url, "snippet": abstract})

    for topic in payload.get("RelatedTopics", []):
        if len(results) >= limit:
            break
        if isinstance(topic, dict) and topic.get("Text"):
            results.append(
                {
                    "title": topic.get("Text", "Related topic")[:120],
                    "url": topic.get("FirstURL", ""),
                    "snippet": topic.get("Text", ""),
                }
            )

    return results[:limit]
