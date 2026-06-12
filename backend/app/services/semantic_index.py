import numpy as np
from sentence_transformers import SentenceTransformer
from loguru import logger

class SemanticIndexingService:
    def __init__(self):
        self.model = None
    
    def load_model(self, model_name='sentence-transformers/msmarco-distilbert-base-v4'):
        self.model = SentenceTransformer(model_name)
        logger.info(f"Loaded semantic indexing model: {model_name}")
    
    def encode_text(self, text):
        if self.model is None:
            raise ValueError("Model not loaded. Please call load_model() first.")
        embedding = self.model.encode(text, convert_to_numpy=True)

        return f"[{','.join(map(str, embedding))}]"
    
semantic_indexer = SemanticIndexingService()