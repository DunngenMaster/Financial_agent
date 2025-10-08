"""Memory service using Pathway for conversation storage."""
from typing import List, Dict, Any
from datetime import datetime
import pathway as pw
from app.models.embeddings import compute_tf_idf_embedding

class PathwayMemoryService:
    """Service for storing conversation history in Pathway."""
    
    def __init__(self):
        self.conversation_table = pw.Table.empty(
            schema={
                "doc_id": str,
                "role": str,
                "content": str,
                "timestamp": str,
                "embedding": List[float],
                "metadata": Dict[str, Any]
            },
            primary_key=["doc_id", "timestamp"]
        )
    
    def add_message(self, doc_id: str, message: Dict[str, Any]):
        """Add a message to the conversation history."""
        entry = {
            "doc_id": doc_id,
            "role": message["role"],
            "content": message["content"],
            "timestamp": str(datetime.now()),
            "embedding": compute_tf_idf_embedding(message["content"]),
            "metadata": message.get("metadata", {})
        }
        
        # Insert into Pathway table
        self.conversation_table = self.conversation_table.concat(
            pw.Table.from_pydict(entry)
        )
    
    def get_relevant_context(self, doc_id: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get relevant conversation history based on semantic similarity."""
        query_embedding = compute_tf_idf_embedding(query)
        
        # Filter by document and compute similarity
        relevant = (
            self.conversation_table
            .filter(pw.this.doc_id == doc_id)
            .select(
                pw.this.role,
                pw.this.content,
                pw.this.metadata,
                similarity=pw.vector_similarity(
                    pw.this.embedding,
                    query_embedding
                )
            )
            .sort(pw.this.similarity, reverse=True)
            .limit(limit)
        )
        
        return [
            {
                "role": row["role"],
                "content": row["content"],
                "metadata": row["metadata"],
                "relevance": row["similarity"]
            }
            for row in relevant
        ]
    
    def clear_conversation(self, doc_id: str):
        """Clear conversation history for a document."""
        self.conversation_table = self.conversation_table.filter(
            pw.this.doc_id != doc_id
        )
    
    def clear_all(self):
        """Clear all conversation histories."""
        self.conversation_table = pw.Table.empty(
            schema=self.conversation_table.schema,
            primary_key=self.conversation_table.primary_key
        )