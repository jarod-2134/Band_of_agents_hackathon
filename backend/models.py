from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from pgvector.sqlalchemy import Vector
from datetime import datetime
from database import Base

class CodeNode(Base):
    """Stores code files, their metadata, and their vector embeddings."""
    __tablename__ = "code_nodes"

    id = Column(Integer, primary_key=True, index=True)
    repo_id = Column(String, index=True)
    file_path = Column(String, index=True, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(768))  # Assuming 768 dims for distilbert
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AgentActionLog(Base):
    """Stores the history of agent actions for vector search and context."""
    __tablename__ = "agent_action_logs"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(String, index=True)
    action_type = Column(String)
    content = Column(Text)
    embedding = Column(Vector(768))
    timestamp = Column(DateTime, default=datetime.utcnow)

class GitHubCommit(Base):
    """Stores github commits to give agents context of history via vectors."""
    __tablename__ = "github_commits"

    id = Column(Integer, primary_key=True, index=True)
    repo_id = Column(String, index=True)
    commit_hash = Column(String, unique=True, index=True)
    message = Column(Text)
    diff = Column(Text)
    embedding = Column(Vector(768))
    timestamp = Column(DateTime, default=datetime.utcnow)

class EntityNode(Base):
    __tablename__ = "entity_nodes"
    id = Column(Integer, primary_key=True, index=True)
    repo_id = Column(String, index=True, nullable=False)
    file_path = Column(String, index=True)
    node_type = Column(String, index=True) 
    name = Column(String, index=True)

class EntityEdge(Base):
    __tablename__ = "entity_edges"
    id = Column(Integer, primary_key=True, index=True)
    repo_id = Column(String, index=True, nullable=False)
    source_id = Column(Integer, index=True)
    target_id = Column(Integer, index=True)
    relation_type = Column(String, index=True)
