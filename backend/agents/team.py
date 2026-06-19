import asyncio
import uuid
from typing import List

from band.runtime.custom_tools import CustomToolDef
from pydantic import BaseModel, Field

from agents.base import BaseAgent
from agents.actions import AgentRole, AgentAction
from agents.harness import (
    TOOL_SEMANTIC_SEARCH, TOOL_GET_FILE_AST, TOOL_READ_FILE, TOOL_WRITE_FILE,
    TOOL_LIST_DIRECTORY, TOOL_GIT_STATUS, TOOL_GIT_DIFF, TOOL_GIT_COMMIT,
    TOOL_GIT_CHECKOUT, TOOL_GIT_MERGE,
    TOOL_CREATE_TASK, TOOL_UPDATE_TASK_STATUS, TOOL_GET_PROJECT_STATUS, TOOL_SUMMARIZE_REPO,
    TOOL_REPLACE_FILE_CONTENT, TOOL_RUN_TERMINAL_COMMAND, TOOL_SCAFFOLD_TEMPLATE,
    TOOL_GET_MERGE_CONFLICTS, TOOL_RESOLVE_MERGE_CONFLICT, TOOL_LEAVE_REVIEW_COMMENT, TOOL_ANALYZE_CODE_QUALITY,
    TOOL_GENERATE_UNIT_TEST, TOOL_RUN_COVERAGE_REPORT, TOOL_CREATE_BUG_REPORT
)

def generate_id():
    return str(uuid.uuid4())[:8]

# ==========================================
# PLANNER SPECIFIC TOOLS
# ==========================================
class SpawnAgentInput(BaseModel):
    """Spins up a new agent to delegate work to. Returns the agent_id."""
    role: str = Field(description="The role of the agent: engineer, reviewer, or tester.")
    name: str = Field(description="A descriptive name for the new agent.")

class DelegateTaskInput(BaseModel):
    """Sends a task to a spawned agent using their agent_id."""
    agent_id: str = Field(description="The ID of the agent to delegate to.")
    task: str = Field(description="The task instruction.")

class BroadcastMessageInput(BaseModel):
    """Sends a message to all active spawned agents simultaneously."""
    message: str = Field(description="The message to broadcast.")

class CheckAgentStatusInput(BaseModel):
    """Retrieves the current semantic status of a specific agent."""
    agent_id: str = Field(description="The ID of the agent.")

class ListActiveAgentsInput(BaseModel):
    """Retrieves a list of all active agents and their statuses."""
    pass

class WaitForMilestoneInput(BaseModel):
    """Pauses the planner until specific agents reach a COMPLETED or IDLE state."""
    agent_ids: List[str] = Field(description="List of agent IDs to wait for.")
    timeout_seconds: int = Field(default=60, description="Max time to wait.")

class FinalizeProjectInput(BaseModel):
    """Merges the current feature branch into main and closes the project milestone."""
    source_branch: str = Field(description="The feature branch to merge.")
    message: str = Field(description="The final merge/commit message.")

class UpdateOwnStatusInput(BaseModel):
    """Updates the planner's own status in the registry so the dashboard can display it."""
    status: str = Field(description="The new status string (e.g. 'Planning Phase 1').")

# We will define the functions inside PlannerAgent so they have access to self,
# or we can pass context. For Band tools, they can be methods.

class PlannerAgent(BaseAgent):
    def __init__(self, name: str, org_slug: str, api_keys: dict = None):
        system_prompt = (
            "You are the Planner Agent. Your job is to orchestrate the software delivery process. "
            "You will spawn Engineer, Reviewer, and Tester agents and delegate tasks to them. "
            "Wait for their responses and make decisions based on their success or failure."
        )
        super().__init__(
            id=f"plan-{generate_id()}",
            role=AgentRole.PLANNER,
            name=name,
            org_slug=org_slug,
            api_keys=api_keys,
            system_prompt=system_prompt,
        )

    def get_tools(self) -> List[CustomToolDef]:
        async def spawn_agent(args: SpawnAgentInput) -> str:
            from main import registry
            from database import AsyncSessionLocal
            from sqlalchemy import text
            
            cls_map = {
                "engineer": EngineerAgent,
                "reviewer": ReviewerAgent,
                "tester": TesterAgent
            }
            if args.role not in cls_map:
                return f"Error: Role {args.role} not found."
            
            # Sync new agent to the DB so the UI can track it
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    text("""
                        INSERT INTO agents (org_slug, name, model_spec, operational_status)
                        VALUES (:org_slug, :name, :model_spec, 'idle')
                        RETURNING id;
                    """),
                    {"org_slug": self.org_slug, "name": args.name, "model_spec": "gemini-2.5-flash"}
                )
                row = result.mappings().first()
                await session.commit()
                db_id = row["id"]
            
            agent = cls_map[args.role](args.name, self.org_slug, self.id, self.api_keys)
            agent.id = str(db_id)  # Override UUID with DB ID
            if self.log_callback:
                agent.set_log_callback(self.log_callback)
            registry.register(self.org_slug, agent)
            asyncio.create_task(agent.run())
            return f"Agent {args.name} spawned with ID: {agent.id}"

        async def delegate_task(args: DelegateTaskInput) -> str:
            from main import registry
            agent = registry.get_agent(self.org_slug, args.agent_id)
            if not agent:
                return f"Error: Agent {args.agent_id} not found."
            registry.update_status(args.agent_id, f"Executing task: {args.task[:30]}...")
            await self.send_message(agent, {"cmd": "execute_task", "task": args.task})
            return f"Task delegated to {args.agent_id}."
            
        async def broadcast_message(args: BroadcastMessageInput) -> str:
            from main import registry
            agents = registry.get_all_agents(self.org_slug)
            count = 0
            for agent in agents:
                if agent.id != self.id:
                    await self.send_message(agent, {"cmd": "broadcast", "message": args.message})
                    count += 1
            return f"Broadcast sent to {count} agents."

        async def check_agent_status(args: CheckAgentStatusInput) -> str:
            from main import registry
            status = registry.get_status(args.agent_id)
            return f"Agent {args.agent_id} status: {status}"

        async def list_active_agents(args: ListActiveAgentsInput) -> str:
            from main import registry
            agents = registry.get_all_agents(self.org_slug)
            lines = ["Active Agents:"]
            for a in agents:
                status = registry.get_status(a.id)
                lines.append(f"- [{a.role}] {a.name} (ID: {a.id}) | Status: {status}")
            return "\n".join(lines)

        async def wait_for_milestone(args: WaitForMilestoneInput) -> str:
            from main import registry
            import time
            start = time.time()
            while time.time() - start < args.timeout_seconds:
                all_ready = True
                for aid in args.agent_ids:
                    status = registry.get_status(aid)
                    # We assume IDLE means they finished their current work
                    if status != "IDLE":
                        all_ready = False
                        break
                if all_ready:
                    return f"All requested agents ({', '.join(args.agent_ids)}) have reached IDLE state."
                await asyncio.sleep(2)
            return f"Timeout reached while waiting for milestone."

        async def update_own_status(args: UpdateOwnStatusInput) -> str:
            from main import registry
            registry.update_status(self.id, args.status)
            return f"Planner status updated to: {args.status}"

        async def finalize_project(args: FinalizeProjectInput) -> str:
            from agents.harness import run_cmd_async
            out1 = await run_cmd_async("git checkout main")
            out2 = await run_cmd_async(f"git merge {args.source_branch} -m \"{args.message}\"")
            from main import registry
            registry.update_status(self.id, "PROJECT COMPLETE")
            return f"Project finalized and merged to main.\nCheckout log: {out1}\nMerge log: {out2}"
            
        return [
            (SpawnAgentInput, spawn_agent),
            (DelegateTaskInput, delegate_task),
            (BroadcastMessageInput, broadcast_message),
            (CheckAgentStatusInput, check_agent_status),
            (ListActiveAgentsInput, list_active_agents),
            (WaitForMilestoneInput, wait_for_milestone),
            (UpdateOwnStatusInput, update_own_status),
            (FinalizeProjectInput, finalize_project),
            TOOL_CREATE_TASK,
            TOOL_UPDATE_TASK_STATUS,
            TOOL_GET_PROJECT_STATUS,
            TOOL_SUMMARIZE_REPO
        ]

    async def process_message(self, message: dict):
        msg = message.get("message")
        if msg == "start" or (isinstance(msg, dict) and msg.get("cmd") == "start"):
            instructions = msg.get("instructions", "No initial instructions.")
            await self.log(f"Planner starting up. Objectives: {instructions}", AgentAction.SPIN_UP_AGENT)
            # To actually trigger the agent to think natively via Band, someone needs to send it a message 
            # via the Band Network. If we want it to react internally, we might need a custom bridge 
            # or rely entirely on users interacting with the Planner via the UI.
            
        elif isinstance(msg, dict) and msg.get("cmd") == "report":
            from_name = message.get("from_name")
            report = msg.get("report")
            await self.log(f"Received report from {from_name}: {report}", AgentAction.MONITOR_PROGRESS)

class EngineerAgent(BaseAgent):
    def __init__(self, name: str, org_slug: str, parent_id: str, api_keys: dict = None):
        system_prompt = (
            "You are the Engineer Agent. Your job is to implement features or fix bugs. "
            "Use your tools to explore the codebase, edit files, and run git operations. "
            "When you are finished with a task, report back to your planner."
        )
        super().__init__(
            id=f"eng-{generate_id()}",
            role=AgentRole.ENGINEER,
            name=name,
            org_slug=org_slug,
            parent_id=parent_id,
            api_keys=api_keys,
            system_prompt=system_prompt,
        )

    def get_tools(self) -> List[CustomToolDef]:
        async def update_own_status(args: UpdateOwnStatusInput) -> str:
            from main import registry
            registry.update_status(self.id, args.status)
            return f"Engineer status updated to: {args.status}"

        class ReportTaskCompletionInput(BaseModel):
            """Reports that the assigned task is complete, updates DB, and sets agent to IDLE."""
            task_id: int = Field(description="The ID of the completed task.")
            summary: str = Field(description="A brief summary of what was done.")

        async def report_task_completion(args: ReportTaskCompletionInput) -> str:
            from agents.harness import update_task_status, UpdateTaskStatusInput
            from main import registry
            # Update the task status to COMPLETED in the database
            await update_task_status(UpdateTaskStatusInput(task_id=args.task_id, status="COMPLETED"))
            # Set the engineer's status to IDLE so the Planner's wait_for_milestone can proceed
            registry.update_status(self.id, "IDLE")
            # Optionally message the planner
            planner = registry.get_agent(self.org_slug, self.parent_id)
            if planner:
                await self.send_message(planner, {"cmd": "report", "from_name": self.name, "report": args.summary})
            return "Task completion reported successfully. Status is now IDLE."

        return [
            TOOL_LIST_DIRECTORY,
            TOOL_READ_FILE,
            TOOL_WRITE_FILE,
            TOOL_REPLACE_FILE_CONTENT,
            TOOL_RUN_TERMINAL_COMMAND,
            TOOL_SCAFFOLD_TEMPLATE,
            TOOL_GIT_STATUS,
            TOOL_GIT_DIFF,
            TOOL_GIT_COMMIT,
            TOOL_GIT_CHECKOUT,
            TOOL_SEMANTIC_SEARCH,
            TOOL_GET_FILE_AST,
            (UpdateOwnStatusInput, update_own_status),
            (ReportTaskCompletionInput, report_task_completion)
        ]

    async def process_message(self, message: dict):
        msg = message.get("message")
        if isinstance(msg, dict) and msg.get("cmd") == "execute_task":
            task = msg.get("task")
            from main import registry
            registry.update_status(self.id, f"Engineering: {task[:30]}...")
            await self.log(f"Received task: {task}", AgentAction.READ_CODEBASE)
            # The agent will process this via the Band network when receiving messages natively.
            # This internal queue is mainly for internal orchestration/telemetry now.

class ReviewerAgent(BaseAgent):
    def __init__(self, name: str, org_slug: str, parent_id: str, api_keys: dict = None):
        system_prompt = (
            "You are the Reviewer Agent. Your job is to verify git diffs, ensure there are no bugs, "
            "and resolve merge conflicts. Use your semantic search tools to gather wider context if needed."
        )
        super().__init__(
            id=f"rev-{generate_id()}",
            role=AgentRole.REVIEWER,
            name=name,
            org_slug=org_slug,
            parent_id=parent_id,
            api_keys=api_keys,
            system_prompt=system_prompt,
        )

    def get_tools(self) -> List[CustomToolDef]:
        async def update_own_status(args: UpdateOwnStatusInput) -> str:
            from main import registry
            registry.update_status(self.id, args.status)
            return f"Reviewer status updated to: {args.status}"

        class ApproveBranchInput(BaseModel):
            """Formally approves the code, sets status to IDLE, and notifies the Planner."""
            summary: str = Field(description="Summary of the approved changes.")

        async def approve_branch(args: ApproveBranchInput) -> str:
            from main import registry
            registry.update_status(self.id, "IDLE")
            planner = registry.get_agent(self.org_slug, self.parent_id)
            if planner:
                await self.send_message(planner, {"cmd": "report", "from_name": self.name, "report": f"APPROVED: {args.summary}"})
            return "Branch approved. Planner notified."

        class RequestChangesInput(BaseModel):
            """Rejects the code and reintroduces an engineer or notifies the planner to reassign."""
            reason: str = Field(description="Detailed reason for rejection.")
            engineer_id: str = Field(default="", description="Optional: specific engineer ID to reintroduce directly.")

        async def request_changes(args: RequestChangesInput) -> str:
            from main import registry
            registry.update_status(self.id, "IDLE")
            if args.engineer_id:
                eng = registry.get_agent(self.org_slug, args.engineer_id)
                if eng:
                    await self.send_message(eng, {"cmd": "execute_task", "task": f"Fix requested by Reviewer: {args.reason}"})
                    return f"Sent fix request directly to Engineer {args.engineer_id}."
            
            # Fallback to planner
            planner = registry.get_agent(self.org_slug, self.parent_id)
            if planner:
                await self.send_message(planner, {"cmd": "report", "from_name": self.name, "report": f"CHANGES REQUESTED: {args.reason}"})
            return "Changes requested. Planner notified."

        return [
            TOOL_GIT_DIFF,
            TOOL_GIT_STATUS,
            TOOL_GIT_MERGE,
            TOOL_READ_FILE,
            TOOL_WRITE_FILE,
            TOOL_REPLACE_FILE_CONTENT,
            TOOL_SEMANTIC_SEARCH,
            TOOL_GET_FILE_AST,
            TOOL_GET_MERGE_CONFLICTS,
            TOOL_RESOLVE_MERGE_CONFLICT,
            TOOL_LEAVE_REVIEW_COMMENT,
            TOOL_ANALYZE_CODE_QUALITY,
            (UpdateOwnStatusInput, update_own_status),
            (ApproveBranchInput, approve_branch),
            (RequestChangesInput, request_changes)
        ]

    async def process_message(self, message: dict):
        msg = message.get("message")
        if isinstance(msg, dict) and msg.get("cmd") == "execute_task":
            task = msg.get("task")
            from main import registry
            registry.update_status(self.id, f"Reviewing: {task[:30]}...")
            await self.log(f"Received review task: {task}", AgentAction.GATHER_CONTEXT)

class TesterAgent(BaseAgent):
    def __init__(self, name: str, org_slug: str, parent_id: str, api_keys: dict = None):
        system_prompt = (
            "You are the Tester Agent. Your job is to run the automated test suite and report results."
        )
        super().__init__(
            id=f"tst-{generate_id()}",
            role=AgentRole.TESTER,
            name=name,
            org_slug=org_slug,
            parent_id=parent_id,
            api_keys=api_keys,
            system_prompt=system_prompt,
        )

    def get_tools(self) -> List[CustomToolDef]:
        async def update_own_status(args: UpdateOwnStatusInput) -> str:
            from main import registry
            registry.update_status(self.id, args.status)
            return f"Tester status updated to: {args.status}"

        class ReportTestResultsInput(BaseModel):
            """Reports the final QA results. Passes the milestone or fails and routes to Engineer."""
            passed: bool = Field(description="True if all tests pass and coverage is good, False otherwise.")
            summary: str = Field(description="Summary of the test run.")
            engineer_id: str = Field(default="", description="Optional: specific engineer ID to fix bugs.")

        async def report_test_results(args: ReportTestResultsInput) -> str:
            from main import registry
            registry.update_status(self.id, "IDLE")
            if not args.passed and args.engineer_id:
                eng = registry.get_agent(self.org_slug, args.engineer_id)
                if eng:
                    await self.send_message(eng, {"cmd": "execute_task", "task": f"Fix Failing Tests: {args.summary}"})
                    return f"Sent bug fix request directly to Engineer {args.engineer_id}."
            
            # Fallback to planner
            planner = registry.get_agent(self.org_slug, self.parent_id)
            if planner:
                prefix = "TESTS PASSED" if args.passed else "TESTS FAILED"
                await self.send_message(planner, {"cmd": "report", "from_name": self.name, "report": f"{prefix}: {args.summary}"})
            return f"Results reported. Passed: {args.passed}. Planner notified."

        class RunInhouseTestsInput(BaseModel):
            """Runs the automated test suite."""
            test_path: str = Field(default=".", description="Path to the tests directory.")

        async def run_inhouse_tests(args: RunInhouseTestsInput) -> str:
            from agents.harness import run_cmd_async
            out = await run_cmd_async(f"pytest {args.test_path}")
            if "command not found" in out:
                out = await run_cmd_async(f"python -m unittest discover {args.test_path}")
            return out
            
        return [
            (RunInhouseTestsInput, run_inhouse_tests),
            TOOL_RUN_TERMINAL_COMMAND,
            TOOL_GENERATE_UNIT_TEST,
            TOOL_RUN_COVERAGE_REPORT,
            TOOL_CREATE_BUG_REPORT,
            TOOL_READ_FILE,
            (UpdateOwnStatusInput, update_own_status),
            (ReportTestResultsInput, report_test_results)
        ]

    async def process_message(self, message: dict):
        msg = message.get("message")
        if isinstance(msg, dict) and msg.get("cmd") == "execute_task":
            task = msg.get("task")
            from main import registry
            registry.update_status(self.id, f"Testing: {task[:30]}...")
            await self.log(f"Received testing task: {task}", AgentAction.RUN_INHOUSE_TESTS)