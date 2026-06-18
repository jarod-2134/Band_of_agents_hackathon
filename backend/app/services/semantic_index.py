import numpy as np
from sentence_transformers import SentenceTransformer
from loguru import logger
from sqlalchemy import delete
from database import AsyncSessionLocal
from models import CodeNode, Commit, EntityNode, EntityEdge
from tree_sitter import Language, Parser
import tree_sitter_python
import tree_sitter_javascript
import tree_sitter_go
import tree_sitter_typescript

class SemanticIndexingService:
    def __init__(self):
        self.model = None
        self.parsers = {}
        try:
            self.parsers['python'] = Parser(Language(tree_sitter_python.language()))
            self.parsers['javascript'] = Parser(Language(tree_sitter_javascript.language()))
            self.parsers['go'] = Parser(Language(tree_sitter_go.language()))
            self.parsers['typescript'] = Parser(Language(tree_sitter_typescript.language_typescript()))
            self.parsers['tsx'] = Parser(Language(tree_sitter_typescript.language_tsx()))
        except Exception as e:
            logger.error(f"Failed to load tree-sitter languages: {e}")
    
    def load_model(self, model_name='sentence-transformers/msmarco-distilbert-base-v4'):
        self.model = SentenceTransformer(model_name)
        logger.info(f"Loaded semantic indexing model: {model_name}")
    
    def encode_text(self, text):
        if self.model is None:
            raise ValueError("Model not loaded. Please call load_model() first.")
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def get_parser(self, filepath: str):
        ext = filepath.split('.')[-1].lower() if '.' in filepath else ''
        mapping = {
            'py': 'python',
            'js': 'javascript',
            'jsx': 'javascript',
            'ts': 'typescript',
            'tsx': 'tsx',
            'go': 'go'
        }
        lang = mapping.get(ext)
        return self.parsers.get(lang)

    def extract_ast_nodes(self, filepath: str, content: str):
        parser = self.get_parser(filepath)
        if not parser:
            return []
        
        try:
            tree = parser.parse(content.encode('utf8'))
        except Exception as e:
            logger.warning(f"Failed to parse {filepath}: {e}")
            return []
            
        nodes = []
        
        def walk(node):
            node_type = node.type.lower()
            name = None
            
            # Simple heuristic for common languages
            if 'class' in node_type or 'interface' in node_type or 'struct' in node_type:
                for child in node.children:
                    if child.type == 'identifier' or child.type == 'type_identifier':
                        name = content.encode('utf8')[child.start_byte:child.end_byte].decode('utf8')
                        break
                if name:
                    nodes.append({"type": "class", "name": name})
                    
            elif 'function' in node_type or 'method' in node_type:
                for child in node.children:
                    if child.type == 'identifier' or child.type == 'property_identifier':
                        name = content.encode('utf8')[child.start_byte:child.end_byte].decode('utf8')
                        break
                if name:
                    nodes.append({"type": "function", "name": name})
            
            elif 'import' in node_type or 'include' in node_type:
                for child in node.children:
                    if child.type in ('string', 'identifier', 'dotted_name'):
                        name = content.encode('utf8')[child.start_byte:child.end_byte].decode('utf8').strip("'\"")
                        break
                if name:
                    nodes.append({"type": "import", "name": name})
            
            for child in node.children:
                walk(child)
                
        walk(tree.root_node)
        return nodes
    
    async def index_file_change(self, repo_id: str, branch: str, filepath: str, content: str):
        try:
            embedding_str = self.encode_text(content)
            ast_entities = self.extract_ast_nodes(filepath, content)
            
            async with AsyncSessionLocal() as session:
                # 1. Clean old vector code nodes
                await session.execute(
                    delete(CodeNode).where(CodeNode.repo_id == repo_id).where(CodeNode.file_path == filepath)
                )
                node = CodeNode(repo_id=repo_id, file_path=filepath, content=content, embedding=embedding_str)
                session.add(node)
                
                # 2. Clean old graph nodes
                await session.execute(
                    delete(EntityNode).where(EntityNode.repo_id == repo_id).where(EntityNode.file_path == filepath)
                )
                
                # Create root file node
                file_node = EntityNode(repo_id=repo_id, file_path=filepath, node_type="file", name=filepath.split('/')[-1])
                session.add(file_node)
                await session.flush() # get id
                
                # Add AST entities
                for ent in ast_entities:
                    child_node = EntityNode(repo_id=repo_id, file_path=filepath, node_type=ent["type"], name=ent["name"])
                    session.add(child_node)
                    await session.flush()
                    
                    edge_type = "DEFINES"
                    if ent["type"] == "import":
                        edge_type = "IMPORTS"
                        
                    edge = EntityEdge(repo_id=repo_id, source_id=file_node.id, target_id=child_node.id, relation_type=edge_type)
                    session.add(edge)
                
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to index file {filepath}: {e}")

    async def delete_repository_embeddings(self, repo_id: str):
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(delete(CodeNode).where(CodeNode.repo_id == repo_id))
                await session.execute(delete(Commit).where(Commit.repo_id == repo_id))
                await session.execute(delete(EntityEdge).where(EntityEdge.repo_id == repo_id))
                await session.execute(delete(EntityNode).where(EntityNode.repo_id == repo_id))
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to delete embeddings for repo {repo_id}: {e}")

semantic_indexer = SemanticIndexingService()