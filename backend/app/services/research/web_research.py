"""Web research service for enhancing responses with internet data."""
import aiohttp
import asyncio
from typing import List, Dict, Any
from bs4 import BeautifulSoup
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class WebResearchService:
    """Service for performing web research on topics."""
    
    def __init__(self):
        self.session = None
        self.search_url = "https://api.bing.microsoft.com/v7.0/search"
        self.headers = {
            "Ocp-Apim-Subscription-Key": "YOUR_BING_API_KEY"  # Replace with your key
        }
    
    async def setup(self):
        """Initialize aiohttp session."""
        if not self.session:
            self.session = aiohttp.ClientSession()
    
    async def close(self):
        """Close aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def search_topic(self, query: str, max_results: int = 3) -> List[Dict[str, str]]:
        """Search for information about a topic."""
        await self.setup()
        
        try:
            async with self.session.get(
                self.search_url,
                headers=self.headers,
                params={"q": query, "count": max_results}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return [
                        {
                            "title": result["name"],
                            "url": result["url"],
                            "snippet": result["snippet"]
                        }
                        for result in data.get("webPages", {}).get("value", [])
                    ]
                else:
                    logger.error(f"Search failed: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"Search error: {str(e)}")
            return []

    async def fetch_content(self, url: str) -> str:
        """Fetch and extract main content from a URL."""
        await self.setup()
        
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Remove script and style elements
                    for script in soup(["script", "style"]):
                        script.decompose()
                    
                    # Get text content
                    text = soup.get_text()
                    
                    # Clean up whitespace
                    lines = (line.strip() for line in text.splitlines())
                    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                    text = ' '.join(chunk for chunk in chunks if chunk)
                    
                    return text
                else:
                    logger.error(f"Failed to fetch {url}: {response.status}")
                    return ""
        except Exception as e:
            logger.error(f"Error fetching {url}: {str(e)}")
            return ""

    async def research_topic(self, topic: str) -> Dict[str, Any]:
        """Perform comprehensive research on a topic."""
        # Search for relevant results
        results = await self.search_topic(topic)
        
        research_data = {
            "query": topic,
            "timestamp": str(datetime.now()),
            "sources": [],
            "summary": ""
        }
        
        # Fetch content from each result
        for result in results:
            content = await self.fetch_content(result["url"])
            if content:
                research_data["sources"].append({
                    "title": result["title"],
                    "url": result["url"],
                    "content": content[:1000]  # Limit content length
                })
        
        return research_data