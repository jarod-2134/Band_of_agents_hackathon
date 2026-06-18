import asyncio
import json
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from loguru import logger
import uvicorn
import bcrypt

from agents.registry import AgentRegistry
from agents.corporate import HeadAgent
from app.services.semantic_index import semantic_indexer
from app.core.logger import setup_app_logging
from app.core.middleware import LifecycleSecurityMiddleware
from app.core.exceptions import PlatformException, platform_exception_handler, validation_exception_handler
from database import init_db

from app.routers.auth import router as auth_router
from app.routers.issues import router as issues_router
from app.routers.org import router as orgs_router
from app.routers.members import router as members_router
from app.routers.traces import router as traces_router
from app.routers.repos import router as repos_router
from app.routers.pull_requests import router as pull_requests_router
from app.routers.agents import router as agents_router
from app.routers.sprints import router as sprints_router
from app.routers.analytics import router as analytics_router
from app.routers.websockets import router as websockets_router
from app.routers.search import router as search_router

if not hasattr(bcrypt, "__about__"):
    class DummyAbout:
        __version__ = getattr(bcrypt, "__version__", "4.0.0")
    bcrypt.__about__ = DummyAbout()

REPOS_DIR = os.path.join(os.path.dirname(__file__), "repos")
os.makedirs(REPOS_DIR, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_app_logging()

    logger.info("Starting application setup...")

    # Initialize database
    semantic_indexer.load_model()
    logger.info("Semantic indexing model loaded.")
    await init_db()
    logger.info("Database initialized successfully.")
    yield

app = FastAPI(
    lifespan=lifespan,
    openapi_components={
        "securitySchemes": {
            "APIKeyHeader": {
                "type": "apiKey",
                "in": "header",
                "name": "X-User-Id"
            }
        }
    },
    security=[{"APIKeyHeader": []}]
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(LifecycleSecurityMiddleware)
app.add_exception_handler(PlatformException, platform_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

app.include_router(auth_router)
app.include_router(issues_router)
app.include_router(orgs_router)
app.include_router(members_router)
app.include_router(traces_router)
app.include_router(repos_router)
app.include_router(pull_requests_router)
app.include_router(agents_router)
app.include_router(sprints_router)
app.include_router(analytics_router)
app.include_router(websockets_router)
app.include_router(search_router)

registry = AgentRegistry()

class ConnectionManager:
    def __init__(self):
        # Maps repo_id -> list[WebSocket]
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, repo_id: str, websocket: WebSocket):
        await websocket.accept()
        if repo_id not in self.active_connections:
            self.active_connections[repo_id] = []
        self.active_connections[repo_id].append(websocket)
        # Send initial graph on connect
        await self.send_graph_update(repo_id)

    def disconnect(self, repo_id: str, websocket: WebSocket):
        if repo_id in self.active_connections:
            try:
                self.active_connections[repo_id].remove(websocket)
            except ValueError:
                pass

    async def broadcast(self, repo_id: str, message: str):
        if repo_id not in self.active_connections:
            return
        for connection in self.active_connections[repo_id]:
            try:
                await connection.send_text(message)
            except:
                pass

    async def send_graph_update(self, repo_id: str):
        graph_data = registry.get_graph(repo_id)
        await self.broadcast(repo_id, json.dumps({
            "type": "graph_update",
            "payload": graph_data
        }))

manager = ConnectionManager()

# Hook up the registry to broadcast when the graph changes
def on_graph_update(repo_id: str):
    # We must run the async broadcast in the event loop
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(manager.send_graph_update(repo_id))
    except RuntimeError:
        logger.error(f"Error occurred while sending graph update for repo {repo_id}.")

registry.on_graph_update = on_graph_update

async def handle_agent_log(repo_id: str, agent_id: str, agent_role: str, message: str, log_type: str):
    await manager.broadcast(repo_id, json.dumps({
        "type": "log",
        "agentRole": agent_role,
        "logType": log_type,
        "payload": message
    }))
    # also highlight active node
    await manager.broadcast(repo_id, json.dumps({
        "type": "active_node",
        "payload": agent_id
    }))
    # briefly pause to let user see the highlight
    await asyncio.sleep(0.5)

@app.websocket("/ws/{org_slug}/{repo_id}")
async def websocket_endpoint(websocket: WebSocket, org_slug: str, repo_id: str):
    await manager.connect(repo_id, websocket)
    
    try:
        while True:
            data = await websocket.receive_text()
            logger.info(f"Received message from {repo_id} (org: {org_slug}): {data}")
            
            try:
                payload = json.loads(data)
                if payload.get("type") == "start_manager":
                    instructions = payload.get("instructions", "")
                    api_keys = payload.get("apiKeys", {})
                    
                    # Initialize the Corporate Structure on demand
                    ceo = HeadAgent("AI CEO", org_slug=repo_id, instructions=instructions, api_keys=api_keys)
                    ceo.set_log_callback(handle_agent_log)
                    registry.register(repo_id, ceo)
                    asyncio.create_task(ceo.run())
                    
                    await manager.broadcast(repo_id, json.dumps({
                        "type": "log",
                        "payload": f"Corporate simulation started with instructions: {instructions}",
                        "logType": "info"
                    }))
                    
                    # Trigger the CEO
                    await ceo.inbox.put({"message": "start", "instructions": instructions})
            except json.JSONDecodeError:
                pass
            
    except WebSocketDisconnect:
        manager.disconnect(repo_id, websocket)
        # Clean up registry for this repo
        registry.clear_org(repo_id)

def build_file_tree(dir_path: str, rel_path: str = ""):
    tree = []
    try:
        entries = sorted(os.listdir(dir_path))
    except FileNotFoundError:
        return []
        
    for entry in entries:
        if entry in [".git", "node_modules", "venv", "__pycache__", ".venv"]:
            continue
            
        full_path = os.path.join(dir_path, entry)
        current_rel = os.path.join(rel_path, entry).replace("\\", "/")
        is_dir = os.path.isdir(full_path)
        
        node = {
            "name": entry,
            "isDir": is_dir,
            "path": current_rel,
            "status": "unmodified"
        }
        
        if is_dir:
            node["children"] = build_file_tree(full_path, current_rel)
            
        tree.append(node)
        
    return tree

def build_file_tree_from_git(repo_path: str, tree, rel_path: str = ""):
    import pygit2
    result = []
    repo = pygit2.Repository(repo_path)
    for entry in tree:
        is_dir = entry.type == pygit2.GIT_OBJECT_TREE
        full_path = os.path.join(rel_path, entry.name).replace("\\", "/")
        node = {
            "name": entry.name,
            "isDir": is_dir,
            "path": full_path,
            "status": "unmodified"
        }
        if is_dir:
            try:
                sub_tree = repo.get(entry.id)
                node["children"] = build_file_tree_from_git(repo_path, sub_tree, full_path)
            except Exception:
                node["children"] = []
        result.append(node)
    return result

@app.get("/api/repos/{repo_id}/files")
async def get_repo_files(repo_id: str):
    repo_path = os.path.join(REPOS_DIR, repo_id)
    if not os.path.exists(repo_path):
        os.makedirs(repo_path, exist_ok=True)
        # Create a dummy README for new repos
        with open(os.path.join(repo_path, "README.md"), "w") as f:
            f.write(f"# Repository: {repo_id}\n\nInitialize your codebase here.")
            
    try:
        import pygit2
        repo = pygit2.Repository(repo_path)
        if repo.is_empty:
            return {"files": []}
        head = repo.head
        commit = repo.get(head.target)
        file_tree = build_file_tree_from_git(repo_path, commit.tree)
        return {"files": file_tree}
    except Exception as e:
        logger.error(f"Failed to read git tree: {e}")
        tree = build_file_tree(repo_path)
        return {"files": tree}

@app.get("/api/repos/{repo_id}/file/{filepath:path}")
async def get_repo_file(repo_id: str, filepath: str):
    repo_path = os.path.join(REPOS_DIR, repo_id)
    
    try:
        import pygit2
        repo = pygit2.Repository(repo_path)
        if not repo.is_empty:
            head = repo.head
            commit = repo.get(head.target)
            current = commit.tree
            parts = filepath.replace("\\", "/").strip("/").split("/")
            for part in parts:
                if not part: continue
                if type(current) is not pygit2.Tree:
                    raise KeyError
                entry = current[part]
                current = repo.get(entry.id)
            if type(current) is pygit2.Blob:
                return {"content": current.data.decode("utf-8")}
    except Exception:
        pass
        
    target_path = os.path.abspath(os.path.join(repo_path, filepath))
    
    if not target_path.startswith(os.path.abspath(repo_path)):
        raise HTTPException(status_code=403, detail="Path traversal prevented")
        
    if not os.path.exists(target_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    try:
        with open(target_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"content": content}
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Cannot read binary file")

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)