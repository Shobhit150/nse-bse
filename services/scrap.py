import httpx
from bs4 import BeautifulSoup
import asyncio

async def scrap_page(url: str) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    return soup

asyncio.run(scrap_page("https://www.bseindia.com/markets/PublicIssues/BSEbidDetails_ofs.aspx?flag=NR&Scripcode=544282"))