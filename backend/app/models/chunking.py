"""Text chunking utilities for document processing."""
import uuid
from typing import List, Dict

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[Dict]:
    """Split text into overlapping chunks.
    
    Args:
        text: The text to split into chunks
        chunk_size: Target size of each chunk in characters
        overlap: Number of characters to overlap between chunks
        
    Returns:
        List of dicts with chunk ID and text
    """
    # Remove extra whitespace
    text = ' '.join(text.split())
    
    if not text:
        return []
        
    # Split into sentences (basic splitting)
    sentences = text.split('.')
    sentences = [s.strip() + '.' for s in sentences if s.strip()]
    
    chunks = []
    current_chunk = []
    current_size = 0
    
    for sentence in sentences:
        sentence_size = len(sentence)
        
        # If adding this sentence would exceed chunk size, save current chunk
        if current_size + sentence_size > chunk_size and current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunks.append({
                "id": str(uuid.uuid4()),
                "text": chunk_text,
                "size": len(chunk_text)
            })
            
            # Start new chunk with overlap
            overlap_size = 0
            overlap_chunk = []
            
            # Add sentences from end of previous chunk until we meet overlap size
            for prev_sentence in reversed(current_chunk):
                if overlap_size + len(prev_sentence) > overlap:
                    break
                overlap_chunk.insert(0, prev_sentence)
                overlap_size += len(prev_sentence)
            
            current_chunk = overlap_chunk
            current_size = overlap_size
            
        current_chunk.append(sentence)
        current_size += sentence_size
    
    # Add final chunk if there's anything left
    if current_chunk:
        chunk_text = ' '.join(current_chunk)
        chunks.append({
            "id": str(uuid.uuid4()),
            "text": chunk_text,
            "size": len(chunk_text)
        })
    
    return chunks