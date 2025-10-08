import httpx, json, time, hashlib
from typing import Dict, Any, Optional, List
from pathlib import Path
from ...config import settings


class FriendlyClient:
    """
    Friendli (serverless) OpenAI-compatible client with:
      - disk cache (hash of markdown+schema+model)
      - retry with exponential backoff honoring Retry-After (handles 429)
      - embeddings and chat completion support
    """
    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        max_retries: int = 4,
        initial_backoff_sec: float = 2.0,
    ):
        self.api_key = settings.FRIENDLI_API_KEY
        self.base_url = str(settings.FRIENDLI_API_BASE).rstrip("/")
        self.model = settings.FRIENDLI_MODEL
        if not self.api_key:
            raise RuntimeError("FRIENDLI_API_KEY not set")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        self.max_retries = max_retries
        self.initial_backoff_sec = initial_backoff_sec
        self.cache_dir = cache_dir or (Path(__file__).resolve().parents[3] / "data" / "cache" / "friendli")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_key(self, markdown: str, schema: Dict[str, Any]) -> Path:
        h = hashlib.sha256()
        h.update(self.model.encode("utf-8"))
        h.update(b"\n--schema--\n")
        h.update(json.dumps(schema, sort_keys=True).encode("utf-8"))
        h.update(b"\n--markdown--\n")
        h.update(markdown.encode("utf-8"))
        return self.cache_dir / f"{h.hexdigest()}.json"

    def _try_read_cache(self, key_path: Path) -> Optional[Dict[str, Any]]:
        if key_path.exists():
            try:
                return json.loads(key_path.read_text(encoding="utf-8"))
            except Exception:
                return None
        return None

    def _write_cache(self, key_path: Path, data: Dict[str, Any]) -> None:
        try:
            key_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def _shrink_markdown(self, md: str, max_chars: int = 20000) -> str:
        """
        Optional: trim very large inputs to reduce tokens and avoid rate pressure.
        You can tweak/remove this if you want full context.
        """
        if len(md) <= max_chars:
            return md
        head = md[: int(max_chars * 0.6)]
        tail = md[-int(max_chars * 0.4):]
        return head + "\n\n[...trimmed...]\n\n" + tail

    async def chat_json(self, markdown: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        cache_path = self._cache_key(markdown, schema)

        # 1) serve from cache if available
        cached = self._try_read_cache(cache_path)
        if cached is not None:
            return cached

        # 2) (optional) shrink input to ease rate limits
        markdown = self._shrink_markdown(markdown)

        payload = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 1000,  # keep answers small for demo
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": "Extract JSON matching the provided schema. Output valid JSON only."},
                {"role": "user", "content": f"SCHEMA:\n{json.dumps(schema, ensure_ascii=False)}\n\nDOCUMENT MARKDOWN:\n{markdown}"},
            ],
        }

        url = f"{self.base_url}/chat/completions"
        backoff = self.initial_backoff_sec

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=120) as client:
                    resp = await client.post(url, headers=self.headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    parsed = json.loads(data["choices"][0]["message"]["content"])
                    # write cache
                    self._write_cache(cache_path, parsed)
                    return parsed

                # Handle 429 with Retry-After
                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After")
                    sleep_sec = float(retry_after) if retry_after and retry_after.isdigit() else backoff
                    time.sleep(sleep_sec)
                    backoff *= 2
                    continue

                # Other client/server errors: raise with body
                resp.raise_for_status()

            except httpx.HTTPStatusError as e:
                # non-429 error with body
                body = e.response.text if e.response is not None else ""
                raise RuntimeError(f"Friendli HTTP {e.response.status_code if e.response else '??'} :: {body}") from e
            except Exception as e:
                if attempt < self.max_retries:
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                raise RuntimeError(f"Friendli call failed after retries: {e!r}")

    async def get_embeddings(self, text: str) -> List[float]:
        """Get embeddings from Friendli AI."""
        url = f"{self.base_url}/v1/embeddings"  # The correct embeddings endpoint
        
        # Truncate text if too long (typical limit is around 8k tokens)
        if len(text) > 24000:  # Approx 8k tokens
            text = text[:24000]
        
        # Split text into smaller chunks if needed (max 500 tokens per request)
        max_chunk_size = 1500  # ~500 tokens
        chunks = [text[i:i + max_chunk_size] for i in range(0, len(text), max_chunk_size)]
        
        # Retry logic for embeddings
        backoff = self.initial_backoff_sec
        all_embeddings = []
        
        for chunk in chunks:
            for attempt in range(self.max_retries + 1):
                try:
                    async with httpx.AsyncClient(timeout=60) as client:
                        response = await client.post(
                            url,
                            headers=self.headers,
                            json={
                                "input": chunk,
                                "model": "text-embedding-ada-002",  # The standard model name
                                "encoding_format": "float"
                            }
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            if "data" in data and len(data["data"]) > 0:
                                all_embeddings.extend([float(x) for x in data["data"][0]["embedding"]])
                                break  # Success, move to next chunk
                            raise RuntimeError("No embeddings in response")
                            
                        # Handle rate limits
                        if response.status_code == 429:
                            retry_after = response.headers.get("Retry-After")
                            sleep_sec = float(retry_after) if retry_after and retry_after.isdigit() else backoff
                            time.sleep(sleep_sec)
                            backoff *= 2
                            continue
                            
                        # If we get a 404, try the alternate endpoint
                        if response.status_code == 404 and attempt == 0:
                            url = f"{self.base_url}/v1/inference/embeddings"
                            continue
                            
                        response.raise_for_status()
                        
                except Exception as e:
                    if attempt < self.max_retries:
                        time.sleep(backoff)
                        backoff *= 2
                        continue
                    raise RuntimeError(f"Embeddings failed after retries: {str(e)}")
        
        # Average the embeddings if we had to split the text
        if len(chunks) > 1:
            embedding_size = len(all_embeddings) // len(chunks)
            averaged_embeddings = []
            for i in range(0, embedding_size):
                values = [all_embeddings[j] for j in range(i, len(all_embeddings), embedding_size)]
                averaged_embeddings.append(sum(values) / len(values))
            return averaged_embeddings
        
        return all_embeddings
            
    async def chat(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Send a chat completion request to Friendli AI."""
        url = f"{self.base_url}/v1/chat/completions"  # The standard chat endpoint
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2000,
            "top_p": 0.9,
            "frequency_penalty": 0,
            "presence_penalty": 0
        }
        
        backoff = self.initial_backoff_sec
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=120) as client:
                    response = await client.post(
                        url,
                        headers=self.headers,
                        json=payload
                    )
                    
                    if response.status_code == 200:
                        return response.json()
                        
                    # Handle rate limits
                    if response.status_code == 429:
                        retry_after = response.headers.get("Retry-After")
                        sleep_sec = float(retry_after) if retry_after and retry_after.isdigit() else backoff
                        time.sleep(sleep_sec)
                        backoff *= 2
                        continue
                        
                    # If we get a 404, try the alternate endpoint
                    if response.status_code == 404 and attempt == 0:
                        url = f"{self.base_url}/v1/inference/chat"
                        continue
                        
                    response.raise_for_status()
                    
            except Exception as e:
                if attempt < self.max_retries:
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                raise RuntimeError(f"Chat completion failed after retries: {str(e)}")
            
        raise RuntimeError("Chat completion failed: Max retries exceeded")
