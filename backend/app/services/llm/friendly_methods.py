    async def get_embeddings(self, text: str) -> List[float]:
        """Get embeddings from Friendli AI."""
        url = f"{self.base_url}/embeddings"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=self.headers,
                json={
                    "model": "text-embedding-ada-002",  # Use OpenAI-compatible model
                    "input": text
                }
            )
            
            if response.status_code != 200:
                raise RuntimeError(f"Embeddings failed with status {response.status_code}: {response.text}")
            
            return response.json()["data"][0]["embedding"]
            
    async def chat(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Send a chat completion request to Friendli AI."""
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=self.headers,
                json=payload
            )
            
            if response.status_code != 200:
                raise RuntimeError(f"Chat completion failed with status {response.status_code}: {response.text}")
            
            return response.json()