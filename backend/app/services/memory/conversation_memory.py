"""Memory service for storing conversation context."""
from typing import List, Dict, Any
import json
from datetime import datetime
from pathlib import Path
import pickle

class ConversationMemory:
    """Service for storing and retrieving conversation history."""
    
    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.conversations: Dict[str, List[Dict[str, Any]]] = {}
        self.load_conversations()
    
    def load_conversations(self):
        """Load conversations from disk."""
        try:
            if self.storage_path.exists():
                with open(self.storage_path, 'rb') as f:
                    self.conversations = pickle.load(f)
        except Exception as e:
            print(f"Error loading conversations: {e}")
    
    def save_conversations(self):
        """Save conversations to disk."""
        try:
            self.storage_path.parent.mkdir(exist_ok=True)
            with open(self.storage_path, 'wb') as f:
                pickle.dump(self.conversations, f)
        except Exception as e:
            print(f"Error saving conversations: {e}")
    
    def add_message(self, doc_id: str, message: Dict[str, Any]):
        """Add a message to the conversation history."""
        if doc_id not in self.conversations:
            self.conversations[doc_id] = []
        
        message["timestamp"] = str(datetime.now())
        self.conversations[doc_id].append(message)
        self.save_conversations()
    
    def get_conversation(self, doc_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent conversation history for a document."""
        if doc_id not in self.conversations:
            return []
        
        return self.conversations[doc_id][-limit:]
    
    def clear_conversation(self, doc_id: str):
        """Clear conversation history for a document."""
        if doc_id in self.conversations:
            del self.conversations[doc_id]
            self.save_conversations()
    
    def clear_all(self):
        """Clear all conversation histories."""
        self.conversations.clear()
        self.save_conversations()

    def get_context_summary(self, doc_id: str) -> str:
        """Get a summary of the conversation context."""
        messages = self.get_conversation(doc_id)
        if not messages:
            return ""
        
        context = []
        for msg in messages:
            role = "User" if msg.get("role") == "user" else "Assistant"
            context.append(f"{role}: {msg.get('content', '')}")
        
        return "\n".join(context)