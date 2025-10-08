"""Text embedding utilities using TF-IDF."""
from collections import Counter
import numpy as np
from typing import List, Dict
import re
from math import log

class TFIDFVectorizer:
    """Simple TF-IDF vectorizer for text embeddings."""
    
    def __init__(self):
        self.vocab = {}  # word -> index mapping
        self.idf = {}   # word -> IDF score
        self.documents: List[str] = []
        
    def _preprocess(self, text: str) -> List[str]:
        """Clean and tokenize text."""
        # Convert to lowercase and remove special characters
        text = text.lower()
        text = re.sub(r'[^\w\s]', '', text)
        
        # Split into tokens
        return text.split()
    
    def fit(self, texts: List[str]):
        """Compute vocabulary and IDF scores."""
        self.documents = texts
        
        # Build vocabulary
        word_doc_count = Counter()
        for text in texts:
            # Count each word only once per document
            words = set(self._preprocess(text))
            for word in words:
                word_doc_count[word] += 1
        
        # Create vocabulary mapping
        self.vocab = {word: idx for idx, word in enumerate(word_doc_count.keys())}
        
        # Compute IDF scores
        num_docs = len(texts)
        self.idf = {
            word: log(num_docs / (count + 1)) + 1  # Add 1 for smoothing
            for word, count in word_doc_count.items()
        }
    
    def transform(self, text: str) -> List[float]:
        """Convert text to TF-IDF vector."""
        # Count word frequencies (TF)
        words = self._preprocess(text)
        word_counts = Counter(words)
        
        # Create vector
        vector = np.zeros(len(self.vocab))
        
        # Compute TF-IDF scores
        for word, count in word_counts.items():
            if word in self.vocab:
                idx = self.vocab[word]
                tf = count / len(words)  # Normalize by document length
                vector[idx] = tf * self.idf.get(word, 0)
        
        # Normalize vector
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
            
        return vector.tolist()

# Global vectorizer instance
_vectorizer = None

def compute_tf_idf_embedding(text: str) -> List[float]:
    """Compute TF-IDF embedding for text.
    
    Args:
        text: Text to compute embedding for
        
    Returns:
        List of floats representing the TF-IDF embedding
    """
    global _vectorizer
    
    if _vectorizer is None:
        _vectorizer = TFIDFVectorizer()
        # Initialize with single document
        _vectorizer.fit([text])
    
    return _vectorizer.transform(text)