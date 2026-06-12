import numpy as np
from sentence_transformers import SentenceTransformer

class SemanticIndexingService:
    def __init__(self):
        self.model = None
    
    def load_model(self, model_name='microsoft/codebert-base'):
        self.model = SentenceTransformer(model_name)
        print(f"Model '{model_name}' loaded successfully.")
    
    def encode_text(self, text):
        if self.model is None:
            raise ValueError("Model not loaded. Please call load_model() first.")
        embedding = self.model.encode(text, convert_to_numpy=True)

        return f"[{','.join(map(str, embedding))}]"
    
semantic_indexer = SemanticIndexingService()