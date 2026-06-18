from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Boolean
from pgvector.sqlalchemy import Vector
from datetime import datetime
from database import Base

class Repo(Base):
    """Stores repository metadata and semantic embeddings."""
    __tablename__ = "repos"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    org_slug = Column(String, index=True)
    fs_path = Column(String)
    default_branch = Column(String)
    visibility = Column(String)
    description = Column(Text)
    embedding = Column(Vector(768))

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email = Column(String)

class Branch(Base):
    __tablename__ = "branches"
    id = Column(Integer, primary_key=True, index=True)
    repo_id = Column(Integer, index=True)
    name = Column(String)
    head_sha = Column(String)
    status = Column(String)
    protected = Column(Boolean)
    created_by = Column(Integer)

class PullRequest(Base):
    __tablename__ = "prs"
    id = Column(Integer, primary_key=True, index=True)
    repo_id = Column(Integer, index=True)
    title = Column(String)
    description = Column(Text)
    embedding = Column(Vector(768))

class Sprint(Base):
    __tablename__ = "sprints"
    id = Column(Integer, primary_key=True, index=True)
    repo_id = Column(Integer, index=True)
    name = Column(String)
    goal = Column(Text)
    embedding = Column(Vector(768))

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

class Commit(Base):
    """Stores commits with vectorized embeddings for context."""
    __tablename__ = "commits"

    id = Column(Integer, primary_key=True, index=True)
    sha = Column(String, unique=True, index=True)
    org_slug = Column(String, index=True)
    repo_id = Column(Integer, index=True)
    message = Column(Text)
    author_name = Column(String)
    author_email = Column(String)
    branch = Column(String, index=True)
    parent_shas = Column(JSON)
    files_changed = Column(Integer)
    insertions = Column(Integer)
    deletions = Column(Integer)
    committed_at = Column(DateTime, default=datetime.utcnow)
    
    # Vectorized fields
    diff = Column(Text)
    embedding = Column(Vector(768))

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
