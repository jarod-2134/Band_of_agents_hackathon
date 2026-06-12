import asyncio
from typing import Callable, Optional

class BaseAgent:
    def __init__(self, id: str, role: str, name: str, parent_id: Optional[str] = None):
        self.id = id
        self.role = role
        self.name = name
        self.parent_id = parent_id
        self.inbox = asyncio.Queue()
        self.running = False
        self.log_callback = None

    def set_log_callback(self, callback: Callable):
        self.log_callback = callback

    async def log(self, message: str, type: str = 'thought'):
        if self.log_callback:
            await self.log_callback(self.id, self.role, message, type)
            
    async def send_message(self, target_agent, message: dict):
        await target_agent.inbox.put({
            "from_id": self.id,
            "from_name": self.name,
            "message": message
        })

    async def process_message(self, message: dict):
        raise NotImplementedError

    async def run(self):
        self.running = True
        await self.log(f"{self.name} ({self.role}) has joined the workforce.", "info")
        while self.running:
            try:
                msg = await asyncio.wait_for(self.inbox.get(), timeout=3.0)
                await self.process_message(msg)
                self.inbox.task_done()
            except asyncio.TimeoutError:
                await self.idle_thought()
            except Exception as e:
                await self.log(f"Error processing message: {e}", "error")

    async def idle_thought(self):
        # Override to occasionally do something when idle
        pass
