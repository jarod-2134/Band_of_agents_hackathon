import asyncio
import os
from typing import Callable, Optional
import litellm
from loguru import logger

from band import Agent
from band.adapters import GoogleADKAdapter # Swapped from AnthropicAdapter
from band.core.types import AdapterFeatures, Capability, Emit
from band.runtime.types import ContactEventConfig, ContactEventStrategy
from band.platform.event import ContactRequestReceivedEvent

from agents.actions import AgentRole
from database import AsyncSessionLocal
from models import AgentActionLog

# Secure cross-agent allowed list 
TRUSTED_TEAM_HANDLES = {f"@{role.value}-agent" for role in AgentRole}

class BaseAgent:
    def __init__(self, id: str, role: str, name: str, org_slug: str, parent_id: Optional[str] = None, api_keys: dict = None, system_prompt: str = ""):
        self.id = id
        self.role = role
        self.name = name
        self.org_slug = org_slug
        self.parent_id = parent_id
        self.api_keys = api_keys or {}
        self.inbox = asyncio.Queue()
        self.running = False
        self.log_callback = None
        
        self.band_id = self.api_keys.get("agent_id")
        self.band_key = self.api_keys.get("bandai")
        self.band_agent: Optional[Agent] = None
        self.system_prompt = system_prompt
        self._init_band_context()

    def _init_band_context(self):
        if not self.band_key:
            return

        features = AdapterFeatures(
            capabilities={Capability.CONTACTS},
            emit={Emit.EXECUTION}
        )
        
        # Updated to GoogleAdapter to match the gemini-2.5-flash native schemas
        self.adapter = GoogleADKAdapter(
            model="gemini-2.5-flash",
            custom_section=self.system_prompt,
            features=features
        )
        
        self.band_agent = Agent.create(
            adapter=self.adapter,
            agent_id=self.band_id,
            api_key=self.band_key,
            ws_url=os.getenv("BAND_WS_URL"),
            rest_url=os.getenv("BAND_REST_URL"),
            contact_config=ContactEventConfig(
                strategy=ContactEventStrategy.CALLBACK,
                on_event=self._handle_band_contact_handshake,
                broadcast_changes=True
            )

        )

    async def _handle_band_contact_handshake(self, event: ContactRequestReceivedEvent, tools) -> None:
        handle = event.payload.from_handle
        if handle in TRUSTED_TEAM_HANDLES or handle.startswith("@org-admin"):
            await tools.respond_contact_request("approve", request_id=event.payload.id)
        else:
            await tools.respond_contact_request("reject", request_id=event.payload.id)

    def set_log_callback(self, callback: Callable):
        self.log_callback = callback

    async def log(self, message: str, action: str = 'thought'):
        logger.info(f"[{self.name}] ({action}): {message}")
        
        if self.log_callback:
            try:
                await self.log_callback(self.org_slug, self.id, self.role, message, action)
            except Exception:
                pass
            
        try:
            async with AsyncSessionLocal() as session:
                log_entry = AgentActionLog(
                    agent_id=self.id,
                    action_type=action,
                    content=message
                )
                session.add(log_entry)
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to commit log telemetry: {e}")

    async def send_message(self, target_agent, message: dict):
        await target_agent.inbox.put({
            "from_id": self.id,
            "from_name": self.name,
            "message": message
        })

    async def _call_llm(self, prompt: str, system_prompt: str = "") -> str:
        kwargs = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1
        }
        
        # litellm requires the gemini/ prefix to target the Google API
        model = "gemini/gemini-2.5-flash"

        if self.band_key:
            kwargs["api_key"] = self.band_key
            kwargs["api_base"] = "https://app.band.ai/v1"
            # If routing through Band proxy instead of litellm directly, drop the prefix
            model = "gemini-2.5-flash" 
        elif self.api_keys.get("gemini"):
            kwargs["api_key"] = self.api_keys["gemini"]
        elif os.getenv("GEMINI_API_KEY"):
            kwargs["api_key"] = os.getenv("GEMINI_API_KEY")

        try:
            response = await litellm.acompletion(model=model, **kwargs)
            return response.choices[0].message.content or ""
        except Exception as e:
            await self.log(f"LLM Context Processing Error: {e}", "error")
            return ""

    async def process_message(self, message: dict):
        raise NotImplementedError

    async def run(self):
        self.running = True
        if self.band_agent:
            asyncio.create_task(self.band_agent.run())
            
        while self.running:
            try:
                msg = await asyncio.wait_for(self.inbox.get(), timeout=3.0)
                await self.process_message(msg)
                self.inbox.task_done()
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                logger.error(f"Inbox loop exception: {e}")