import asyncio
import uuid
from .base import BaseAgent
from .actions import AgentRole, AgentAction
from .registry import registry

def generate_id():
    return str(uuid.uuid4())[:8]

class HeadAgent(BaseAgent):
    def __init__(self, name: str):
        super().__init__(id=f"ceo-{generate_id()}", role=AgentRole.CEO, name=name)
        self.teams_created = False

    async def process_message(self, message: dict):
        msg = message.get("message")
        if msg == "start":
            await self.log("Analyzing overall corporate objective...", "thought")
            await asyncio.sleep(2)
            await self.create_team("Frontend Team")
            await asyncio.sleep(1)
            await self.create_team("Backend Team")
        elif "status" in msg:
            await self.log(f"Received status report from {message['from_name']}: {msg['status']}", "thought")

    async def create_team(self, team_name: str):
        await self.log(f"Action: Creating {team_name}", "action")
        manager = TeamManager(f"Manager ({team_name})", self.id)
        manager.set_log_callback(self.log_callback)
        registry.register(manager)
        asyncio.create_task(manager.run())
        
        # Tell manager to start hiring
        await self.send_message(manager, {"cmd": "hire_team"})

class TeamManager(BaseAgent):
    def __init__(self, name: str, parent_id: str):
        super().__init__(id=f"mgr-{generate_id()}", role=AgentRole.MANAGER, name=name, parent_id=parent_id)
        
    async def process_message(self, message: dict):
        msg = message.get("message")
        if msg.get("cmd") == "hire_team":
            await self.log(f"Planning team structure for {self.name}...", "thought")
            await asyncio.sleep(1.5)
            await self.hire_specialist(AgentRole.ENGINEER, f"Sr. Engineer ({self.name})")
            await asyncio.sleep(1)
            await self.hire_specialist(AgentRole.REVIEWER, f"Lead Reviewer ({self.name})")
            
            # Report back to CEO
            ceo = registry.get_agent(self.parent_id)
            if ceo:
                await self.send_message(ceo, {"status": f"{self.name} is fully staffed and ready."})
                
        elif msg.get("cmd") == "task_done":
            await self.log(f"Specialist {message['from_name']} completed task.", "thought")

    async def hire_specialist(self, role: AgentRole, name: str):
        await self.log(f"Action: Hiring {role.value} - {name}", "action")
        if role == AgentRole.ENGINEER:
            specialist = EngineerAgent(name, self.id)
        elif role == AgentRole.REVIEWER:
            specialist = ReviewerAgent(name, self.id)
        else:
            return
            
        specialist.set_log_callback(self.log_callback)
        registry.register(specialist)
        asyncio.create_task(specialist.run())
        
        # Give them some mock work
        await self.send_message(specialist, {"cmd": "do_work"})

class EngineerAgent(BaseAgent):
    def __init__(self, name: str, parent_id: str):
        super().__init__(id=f"eng-{generate_id()}", role=AgentRole.ENGINEER, name=name, parent_id=parent_id)

    async def process_message(self, message: dict):
        msg = message.get("message")
        if msg.get("cmd") == "do_work":
            await self.log("Analyzing requirements and reading files...", "thought")
            await asyncio.sleep(2)
            await self.log("Action: Writing code to implement feature.", "action")
            await asyncio.sleep(1.5)
            manager = registry.get_agent(self.parent_id)
            if manager:
                await self.send_message(manager, {"cmd": "task_done"})

class ReviewerAgent(BaseAgent):
    def __init__(self, name: str, parent_id: str):
        super().__init__(id=f"rev-{generate_id()}", role=AgentRole.REVIEWER, name=name, parent_id=parent_id)

    async def process_message(self, message: dict):
        msg = message.get("message")
        if msg.get("cmd") == "do_work":
            await self.log("Waiting for pull requests to review...", "thought")
            await asyncio.sleep(3)
            await self.log("Action: Linting code and running static analysis.", "action")
            await asyncio.sleep(1)
            await self.log("Action: Approving Pull Request.", "action")
            manager = registry.get_agent(self.parent_id)
            if manager:
                await self.send_message(manager, {"cmd": "task_done"})
