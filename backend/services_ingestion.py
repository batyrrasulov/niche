import httpx
from bs4 import BeautifulSoup


async def fetch_url_text(url: str) -> str:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(url)
        resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for script in soup(["script", "style"]):
        script.extract()
    return " ".join(soup.get_text(separator=" ").split())
