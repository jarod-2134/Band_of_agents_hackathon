import asyncio
import json
import asyncpg
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

from agents.registry import registry
from agents.corporate import HeadAgent
from services.semantic_index import semantic_indexer

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the semantic model at startup
    semantic_indexer.load_model()
    yield
    # Perform any necessary cleanup here (if needed)

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        # Send initial graph on connect
        await self.send_graph_update()

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass

    async def send_graph_update(self):
        graph_data = registry.get_graph()
        await self.broadcast(json.dumps({
            "type": "graph_update",
            "payload": graph_data
        }))

manager = ConnectionManager()

# Hook up the registry to broadcast when the graph changes
def on_graph_update():
    # We must run the async broadcast in the event loop
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(manager.send_graph_update())
    except RuntimeError:
        pass

registry.on_graph_update = on_graph_update

async def handle_agent_log(agent_id: str, agent_role: str, message: str, log_type: str):
    await manager.broadcast(json.dumps({
        "type": "log",
        "agentRole": agent_role,
        "logType": log_type,
        "payload": message
    }))
    # also highlight active node
    await manager.broadcast(json.dumps({
        "type": "active_node",
        "payload": agent_id
    }))
    # briefly pause to let user see the highlight
    await asyncio.sleep(0.5)

@app.websocket("/ws/{repo_id}")
async def websocket_endpoint(websocket: WebSocket, repo_id: str):
    await manager.connect(websocket)
    
    # Initialize the Corporate Structure
    ceo = HeadAgent("AI CEO")
    ceo.set_log_callback(handle_agent_log)
    registry.register(ceo)
    asyncio.create_task(ceo.run())
    
    try:
        await manager.broadcast(json.dumps({
            "type": "log",
            "payload": f"Corporate simulation started for {repo_id}",
            "logType": "info"
        }))
        
        # Trigger the CEO
        await ceo.inbox.put({"message": "start"})
        
        while True:
            data = await websocket.receive_text()
            print(f"Received from {repo_id}: {data}")
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        # Clean up registry only if no other connections remain
        if len(manager.active_connections) == 0:
            registry.agents.clear()
            if ceo.running:
                ceo.running = False

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
