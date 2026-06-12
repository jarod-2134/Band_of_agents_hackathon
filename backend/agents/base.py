import asyncio
from typing import Callable, Optional
import litellm

from database import AsyncSessionLocal
from models import AgentActionLog

class BaseAgent:
    def __init__(self, id: str, role: str, name: str, parent_id: Optional[str] = None, api_keys: dict = None):
        self.id = id
        self.role = role
        self.name = name
        self.parent_id = parent_id
        self.api_keys = api_keys or {}
        self.inbox = asyncio.Queue()
        self.running = False
        self.log_callback = None

    def set_log_callback(self, callback: Callable):
        self.log_callback = callback

    async def log(self, message: str, type: str = 'thought'):
        if self.log_callback:
            await self.log_callback(self.id, self.role, message, type)
            
        # Persist to vector database for operations history
        try:
            async with AsyncSessionLocal() as session:
                log_entry = AgentActionLog(
                    agent_id=self.id,
                    action_type=type,
                    content=message
                )
                session.add(log_entry)
                await session.commit()
        except Exception as e:
            print(f"Error saving log to DB: {e}")
            
    async def send_message(self, target_agent, message: dict):
        await target_agent.inbox.put({
            "from_id": self.id,
            "from_name": self.name,
            "message": message
        })

    async def _call_llm(self, prompt: str, system_prompt: str = "") -> str:
        # Determine model to use
        # If bandai key is present, use it as custom openai compatible endpoint
        kwargs = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }

        # Default model
        model = "gpt-4o"

        if self.api_keys.get("bandai"):
            kwargs["api_key"] = self.api_keys["bandai"]
            kwargs["api_base"] = "https://app.band.ai/v1"
            # litellm requires the model name to be passed exactly, maybe openai/ prefix for custom bases
            model = "openai/gpt-4o" 
        elif self.api_keys.get("openai"):
            kwargs["api_key"] = self.api_keys["openai"]
        elif self.api_keys.get("anthropic"):
            kwargs["api_key"] = self.api_keys["anthropic"]
            model = "claude-3-5-sonnet-20240620"
        else:
            await self.log("No API Key found! Proceeding might fail.", "error")

        try:
            await self.log(f"Calling LLM ({model})...", "thought")
            response = await litellm.acompletion(model=model, **kwargs)
            return response.choices[0].message.content
        except Exception as e:
            await self.log(f"LLM Error: {e}", "error")
            return ""

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
