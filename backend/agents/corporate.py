import asyncio
import uuid
import re
import subprocess
import os
from .base import BaseAgent
from .actions import AgentRole
from .registry import registry
from database import AsyncSessionLocal
from models import AgentActionLog, Commit

def generate_id():
    return str(uuid.uuid4())[:8]

def run_cmd(cmd, cwd=None):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd or os.getcwd())
        return result.stdout + result.stderr
    except Exception as e:
        return str(e)

def repo_dir_for(org_slug: str) -> str:
    """Resolve the on-disk repo directory for an org/repo id, creating it if missing."""
    base = os.path.join(os.path.dirname(os.path.dirname(__file__)), "repos", org_slug)
    os.makedirs(base, exist_ok=True)
    return base

def resolve_repo_path(org_slug: str, raw_path: str) -> str:
    """Anchor an LLM-emitted file path inside the repo dir and normalize it safely."""
    # Strip any leading slashes/separators so it can't escape the repo root.
    clean = raw_path.replace("\\", "/").lstrip("./").lstrip("/")
    return os.path.join(repo_dir_for(org_slug), clean)

class HeadAgent(BaseAgent):
    def __init__(self, name: str, org_slug: str, instructions: str = "", api_keys: dict = None):
        super().__init__(id=f"ceo-{generate_id()}", role=AgentRole.CEO, name=name, org_slug=org_slug, api_keys=api_keys)
        self.instructions = instructions

    async def process_message(self, message: dict):
        msg = message.get("message")
        if msg == "start":
            await self.log("Analyzing overall corporate objective via LLM...", "thought")
            prompt = f"Break down this objective into a single clear engineering task: {self.instructions}. Respond with ONLY the task description."
            task_description = await self._call_llm(prompt, "You are an AI CEO delegating tasks.")
            
            await self.log(f"Delegating task: {task_description[:50]}...", "action")
            
            manager = TeamManager(f"Manager", self.org_slug, self.id, self.api_keys)
            manager.set_log_callback(self.log_callback)
            registry.register(self.org_slug, manager)
            asyncio.create_task(manager.run())
            
            # Tell manager to execute the plan
            await self.send_message(manager, {"cmd": "execute_plan", "task": task_description})

        elif isinstance(msg, dict) and "status" in msg:
            await self.log(f"Received status report from {message['from_name']}: {msg['status']}", "thought")

class TeamManager(BaseAgent):
    def __init__(self, name: str, org_slug: str, parent_id: str, api_keys: dict = None):
        super().__init__(id=f"mgr-{generate_id()}", role=AgentRole.MANAGER, name=name, org_slug=org_slug, parent_id=parent_id, api_keys=api_keys)
        
    async def process_message(self, message: dict):
        msg = message.get("message")
        if isinstance(msg, dict) and msg.get("cmd") == "execute_plan":
            task = msg.get("task")
            await self.log(f"Planning team execution for task...", "thought")
            
            engineer = EngineerAgent("Engineer", self.org_slug, self.id, self.api_keys)
            reviewer = ReviewerAgent("Reviewer", self.org_slug, self.id, self.api_keys)
            
            engineer.set_log_callback(self.log_callback)
            reviewer.set_log_callback(self.log_callback)
            
            registry.register(self.org_slug, engineer)
            registry.register(self.org_slug, reviewer)
            
            asyncio.create_task(engineer.run())
            asyncio.create_task(reviewer.run())
            
            # Tell engineer to do the work
            await self.send_message(engineer, {"cmd": "do_work", "task": task})
            
        elif isinstance(msg, dict) and msg.get("cmd") == "engineer_done":
            await self.log(f"Engineer finished. Asking Reviewer to review.", "action")
            # Find reviewer
            for agent in registry.get_all_agents(self.org_slug):
                if agent.role == AgentRole.REVIEWER and getattr(agent, 'parent_id', None) == self.id:
                    await self.send_message(agent, {"cmd": "review_work"})
                    break
                    
        elif isinstance(msg, dict) and msg.get("cmd") == "reviewer_done":
            ceo = registry.get_agent(self.org_slug, self.parent_id)
            if ceo:
                await self.send_message(ceo, {"status": "Task completed and reviewed successfully!"})


class EngineerAgent(BaseAgent):
    def __init__(self, name: str, org_slug: str, parent_id: str, api_keys: dict = None):
        super().__init__(id=f"eng-{generate_id()}", role=AgentRole.ENGINEER, name=name, org_slug=org_slug, parent_id=parent_id, api_keys=api_keys)

    async def process_message(self, message: dict):
        msg = message.get("message")
        if isinstance(msg, dict) and msg.get("cmd") == "do_work":
            task = msg.get("task")
            await self.log(f"Writing code for: {task[:30]}...", "thought")
            
            system_prompt = (
                "You are an expert engineer. Your task is to write code. "
                "Output file modifications using this exact format:\n"
                "<write path=\"relative/path/to/file\">\nfile contents here\n</write>\n"
                "Do not use markdown blocks outside of the write tags for the code."
            )
            response = await self._call_llm(task, system_prompt)
            
            # Parse <write path="...">...</write>
            writes = re.finditer(r'<write\s+path="([^"]+)">\s*(.*?)\s*</write>', response, re.DOTALL)
            files_changed = 0
            repo_cwd = repo_dir_for(self.org_slug)
            for match in writes:
                raw_path = match.group(1)
                content = match.group(2)
                try:
                    abs_path = resolve_repo_path(self.org_slug, raw_path)
                    parent = os.path.dirname(abs_path)
                    if parent:
                        os.makedirs(parent, exist_ok=True)
                    with open(abs_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    await self.log(f"Created/Modified file: {raw_path}", "action")
                    files_changed += 1
                except Exception as e:
                    await self.log(f"Failed to write {raw_path}: {e}", "error")

            if files_changed > 0:
                await self.log("Committing changes to git...", "action")
                run_cmd("git add .", cwd=repo_cwd)
                run_cmd('git commit -m "Engineer: Completed task implementation"', cwd=repo_cwd)
            else:
                await self.log("No files were written based on the LLM output.", "error")

            manager = registry.get_agent(self.org_slug, self.parent_id)
            if manager:
                await self.send_message(manager, {"cmd": "engineer_done"})

class ReviewerAgent(BaseAgent):
    def __init__(self, name: str, org_slug: str, parent_id: str, api_keys: dict = None):
        super().__init__(id=f"rev-{generate_id()}", role=AgentRole.REVIEWER, name=name, org_slug=org_slug, parent_id=parent_id, api_keys=api_keys)

    async def process_message(self, message: dict):
        msg = message.get("message")
        if isinstance(msg, dict) and msg.get("cmd") == "review_work":
            await self.log("Pulling git diff to review changes...", "thought")

            repo_cwd = repo_dir_for(self.org_slug)
            diff = run_cmd("git show HEAD", cwd=repo_cwd) # last commit the engineer made
            
            if not diff or "fatal" in diff:
                await self.log("No git history found or not a git repo.", "error")
            else:
                await self.log("Reviewing diff...", "action")
                prompt = f"Review the following git diff and point out any glaring issues. Keep it brief.\n\n{diff}"
                review = await self._call_llm(prompt, "You are a strict code reviewer.")
                await self.log(f"Review Feedback: {review[:100]}...", "thought")
                
            manager = registry.get_agent(self.org_slug, self.parent_id)
            if manager:
                await self.send_message(manager, {"cmd": "reviewer_done"})
