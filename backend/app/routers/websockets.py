import json
import asyncio
from typing import Dict, Set, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from pydantic import BaseModel, ValidationError
from loguru import logger

router = APIRouter(tags=["Real-time Event Fabric"])

# =============================================================================
# IN-MEMORY CONNECTION ORCHESTRATOR
# =============================================================================
class ConnectionManager:
    def __init__(self):
        # Maps a specific organization slug to its active client connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Maps a specific WebSocket connection to the repository IDs they are watching
        self.client_subscriptions: Dict[WebSocket, Set[str]] = {}

    async def connect(self, org_slug: str, websocket: WebSocket):
        await websocket.accept()
        if org_slug not in self.active_connections:
            self.active_connections[org_slug] = set()
        self.active_connections[org_slug].add(websocket)
        self.client_subscriptions[websocket] = set()
        logger.info(f"🔌 WebSocket connection established for org: {org_slug}")

    def disconnect(self, org_slug: str, websocket: WebSocket):
        if org_slug in self.active_connections:
            self.active_connections[org_slug].discard(websocket)
            if not self.active_connections[org_slug]:
                del self.active_connections[org_slug]
        if websocket in self.client_subscriptions:
            del self.client_subscriptions[websocket]
        logger.info(f"❌ WebSocket connection severed for org: {org_slug}")

    def subscribe_client_to_repo(self, websocket: WebSocket, repo_id: str):
        if websocket in self.client_subscriptions:
            self.client_subscriptions[websocket].add(str(repo_id))
            logger.debug(f"Client registered interest in repo channel: {repo_id}")

    def unsubscribe_client_from_repo(self, websocket: WebSocket, repo_id: str):
        if websocket in self.client_subscriptions:
            self.client_subscriptions[websocket].discard(str(repo_id))
            logger.debug(f"Client removed from repo channel: {repo_id}")

    async def broadcast_to_org(self, org_slug: str, event_type: str, payload: dict):
        """Broadcasts non-repo-specific events to everyone in the organization."""
        if org_slug not in self.active_connections:
            return
            
        message = {"event": event_type, "data": payload}
        disconnected_clients = set()
        
        for connection in self.active_connections[org_slug]:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected_clients.add(connection)
                
        for dead_client in disconnected_clients:
            self.disconnect(org_slug, dead_client)

    async def broadcast_to_repo_subscribers(self, org_slug: str, repo_id: str, event_type: str, payload: dict):
        """Broadcasts repository updates only to clients who explicitly subscribed to that repo ID."""
        if org_slug not in self.active_connections:
            return

        message = {"event": event_type, "data": payload}
        disconnected_clients = set()
        target_repo_str = str(repo_id)

        for connection in self.active_connections[org_slug]:
            # Deliver the event if the client is subscribed to this repository
            subscriptions = self.client_subscriptions.get(connection, set())
            if target_repo_str in subscriptions:
                try:
                    await connection.send_json(message)
                except Exception:
                    disconnected_clients.add(connection)

        for dead_client in disconnected_clients:
            self.disconnect(org_slug, dead_client)


manager = ConnectionManager()


# =============================================================================
# INBOUND ACTION VALIDATION SCHEMAS
# =============================================================================
class InboundWSMessage(BaseModel):
    action: str  # 'subscribe_repo', 'unsubscribe_repo', or 'ping'
    repo_id: Optional[str] = None


# =============================================================================
# CORE WEBSOCKET ROUTE ENTRYPOINT
# =============================================================================
@router.websocket("/ws/{org_slug}")
async def websocket_event_stream(websocket: WebSocket, org_slug: str):
    """
    Exposes a unified stateful WebSocket endpoint for handling real-time,
    bidirectional pipeline communications with active web browsers.
    """
    await manager.connect(org_slug, websocket)
    try:
        while True:
            # Expect incoming messages from clients
            data = await websocket.receive_text()
            
            try:
                raw_json = json.loads(data)
                msg = InboundWSMessage.parse_obj(raw_json)
                
                # Process incoming system instructions
                if msg.action == "subscribe_repo":
                    if msg.repo_id:
                        manager.subscribe_client_to_repo(websocket, msg.repo_id)
                        await websocket.send_json({"status": "subscribed", "repo_id": msg.repo_id})
                        
                elif msg.action == "unsubscribe_repo":
                    if msg.repo_id:
                        manager.unsubscribe_client_from_repo(websocket, msg.repo_id)
                        await websocket.send_json({"status": "unsubscribed", "repo_id": msg.repo_id})
                        
                elif msg.action == "ping":
                    await websocket.send_json({"status": "pong"})
                    
                else:
                    await websocket.send_json({"error": f"Unknown inbound system protocol action: {msg.action}"})
                    
            except (json.JSONDecodeError, ValidationError) as err:
                logger.warning(f"Malformed payload dropped over WebSocket connection channel: {err}")
                await websocket.send_json({"error": "Invalid action execution syntax format payload structure."})

    except WebSocketDisconnect:
        manager.disconnect(org_slug, websocket)
    except Exception as general_err:
        logger.error(f"Unexpected connection failure framework collision exception: {general_err}")
        manager.disconnect(org_slug, websocket)


# =============================================================================
# BROADCAST BRIDGE EMITTERS (Hook these into your database & message loops)
# =============================================================================
class RealTimeEventFabricBridge:
    """
    Provides a standardized API surface for system worker services to push events 
    directly to connected browsers, matching your required specs exactly.
    """
    
    # Git Specific Subsystem Channels
    @staticmethod
    async def emit_git_commit_created(org_slug: str, repo_id: str, sha: str, branch: str, author: str, message: str):
        payload = {"sha": sha, "branch": branch, "author": author, "message": message, "repo_id": repo_id}
        await manager.broadcast_to_repo_subscribers(org_slug, repo_id, "git.commit.created", payload)

    @staticmethod
    async def emit_git_branch_created(org_slug: str, repo_id: str, name: str, linked_issue_id: Optional[int] = None):
        payload = {"name": name, "linked_issue": linked_issue_id, "repo_id": repo_id}
        await manager.broadcast_to_repo_subscribers(org_slug, repo_id, "git.branch.created", payload)

    # Pull Request Specific Channels
    @staticmethod
    async def emit_pr_created(org_slug: str, repo_id: str, pr_id: int, title: str, head_branch: str):
        payload = {"pr_id": pr_id, "title": title, "head_branch": head_branch, "repo_id": repo_id}
        await manager.broadcast_to_repo_subscribers(org_slug, repo_id, "pr.created", payload)

    @staticmethod
    async def emit_pr_status_changed(org_slug: str, repo_id: str, pr_id: int, status: str):
        payload = {"pr_id": pr_id, "status": status, "repo_id": repo_id}
        await manager.broadcast_to_repo_subscribers(org_slug, repo_id, "pr.status_changed", payload)

    @staticmethod
    async def emit_pr_comment_added(org_slug: str, repo_id: str, pr_id: int, comment_id: int, file_path: Optional[str] = None, line_number: Optional[int] = None):
        payload = {"pr_id": pr_id, "comment_id": comment_id, "file_path": file_path, "line_number": line_number}
        await manager.broadcast_to_repo_subscribers(org_slug, repo_id, "pr.comment_added", payload)

    # Issue Tracker Core Subsystems
    @staticmethod
    async def emit_issue_created(org_slug: str, issue_id: int, title: str, status: str):
        payload = {"issue_id": issue_id, "title": title, "status": status}
        await manager.broadcast_to_org(org_slug, "issue.created", payload)

    @staticmethod
    async def emit_issue_status_changed(org_slug: str, issue_id: int, old_status: str, new_status: str):
        payload = {"issue_id": issue_id, "old_status": old_status, "new_status": new_status}
        await manager.broadcast_to_org(org_slug, "issue.status_changed", payload)

    @staticmethod
    async def emit_issue_assigned(org_slug: str, issue_id: int, agent_id: int):
        payload = {"issue_id": issue_id, "agent_id": agent_id}
        await manager.broadcast_to_org(org_slug, "issue.assigned", payload)

    # Kanban & Sprint Boards UI Mutations
    @staticmethod
    async def emit_sprint_card_moved(org_slug: str, item_id: int, issue_id: int, column_status: str, position: int):
        payload = {"item_id": item_id, "issue_id": issue_id, "column_status": column_status, "position": position}
        await manager.broadcast_to_org(org_slug, "sprint.card_moved", payload)

    # Intelligent Agent Status Monitors
    @staticmethod
    async def emit_agent_status_changed(org_slug: str, agent_id: int, role: str, status: str):
        payload = {"agent_id": agent_id, "role": role, "status": status}
        await manager.broadcast_to_org(org_slug, "agent.status_changed", payload)

    @staticmethod
    async def emit_agent_tool_called(org_slug: str, agent_id: int, tool: str, duration_ms: int):
        payload = {"agent_id": agent_id, "tool": tool, "duration_ms": duration_ms}
        await manager.broadcast_to_org(org_slug, "agent.tool_called", payload)

    # Vector Semantic Parsing Pipeline Systems
    @staticmethod
    async def emit_semantic_index_complete(org_slug: str, repo_id: str, sha: str, chunks_indexed: int):
        payload = {"sha": sha, "chunks_indexed": chunks_indexed}
        await manager.broadcast_to_repo_subscribers(org_slug, repo_id, "semantic.index_complete", payload)