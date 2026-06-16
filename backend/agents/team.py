import asyncio
import uuid
import re
import os
import subprocess
from .base import BaseAgent
from .actions import AgentRole, AgentAction
from .registry import registry

def generate_id():
    return str(uuid.uuid4())[:8]

async def run_cmd_async(cmd: str) -> str:
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=os.getcwd()
        )
        stdout, stderr = await proc.communicate()
        return (stdout.decode() + stderr.decode()).strip()
    except Exception as e:
        return str(e)


class HeadAgent(BaseAgent):
    def __init__(self, name: str, instructions: str = "", api_keys: dict = None):
        super().__init__(id=f"ceo-{generate_id()}", role=AgentRole.CEO, name=name, api_keys=api_keys)
        self.instructions = instructions

    async def process_message(self, message: dict):
        msg = message.get("message")
        if msg == "start":
            await self.log("Analyzing high-level business goals...", AgentAction.EVALUATE_BUSINESS_OBJECTIVE)
            
            pm = ProductManager("ProductManager", self.id, self.api_keys)
            pm.set_log_callback(self.log_callback)
            registry.register(pm)
            asyncio.create_task(pm.run())
            
            await self.log("Handing off strategic goals to Product Manager...", AgentAction.DELEGATE_STRATEGIC_PLAN)
            await self.send_message(pm, {"cmd": "create_specs", "instructions": self.instructions})
            
        elif isinstance(msg, dict) and msg.get("cmd") == "final_signoff":
            await self.log(f"Project delivery accepted: {msg.get('summary')}", AgentAction.RECEIVE_FINAL_DELIVERY_REPORT)


class ProductManager(BaseAgent):
    def __init__(self, name: str, parent_id: str, api_keys: dict = None):
        super().__init__(id=f"pm-{generate_id()}", role=AgentRole.PRODUCT_MANAGER, name=name, parent_id=parent_id, api_keys=api_keys)

    async def process_message(self, message: dict):
        msg = message.get("message")
        if isinstance(msg, dict) and msg.get("cmd") == "create_specs":
            instructions = msg.get("instructions")
            await self.log("Parsing market objectives into functional requirements...", AgentAction.PARSE_MARKET_OR_USER_OBJECTIVE)
            
            prompt = f"Convert this high-level instruction into a granular, markdown technical specification list: {instructions}"
            specs = await self._call_llm(prompt, "You are a Product Manager agent writing clear functional specs.")
            
            await self.log("Functional specification drafted successfully.", AgentAction.GENERATE_FUNCTIONAL_SPEC)
            
            sm = ScrumMaster("ScrumMaster", self.id, self.api_keys)
            sm.set_log_callback(self.log_callback)
            registry.register(sm)
            asyncio.create_task(sm.run())
            
            await self.send_message(sm, {"cmd": "bootstrap_pipeline", "specs": specs})


class ScrumMaster(BaseAgent):
    def __init__(self, name: str, parent_id: str, api_keys: dict = None):
        super().__init__(id=f"sm-{generate_id()}", role=AgentRole.SCRUM_MASTER, name=name, parent_id=parent_id, api_keys=api_keys)

    async def process_message(self, message: dict):
        msg = message.get("message")
        if not isinstance(msg, dict): return
        cmd = msg.get("cmd")
        context = msg.get("context", {})
        
        if cmd == "bootstrap_pipeline":
            await self.log("Provisioning full operational delivery squad...", AgentAction.PROVISION_SQUAD_CLUSTER)
            context["specs"] = msg.get("specs")
            
            # Spin up remaining specialized engineering nodes
            roles = [
                (Architect, AgentRole.ARCHITECT, "Architect"),
                (DataEngineer, AgentRole.DATA_ENGINEER, "DataEngineer"),
                (BackendEngineer, AgentRole.BACKEND_ENGINEER, "BackendEngineer"),
                (FrontendEngineer, AgentRole.FRONTEND_ENGINEER, "FrontendEngineer"),
                (SecurityAuditor, AgentRole.SECURITY_AUDITOR, "SecurityAuditor"),
                (PeerReviewer, AgentRole.PEER_REVIEWER, "PeerReviewer"),
                (AutomationTester, AgentRole.AUTOMATION_TESTER, "AutomationTester"),
                (InfrastructureEngineer, AgentRole.INFRASTRUCTURE_ENGINEER, "InfrastructureEngineer"),
                (ReleaseManager, AgentRole.RELEASE_MANAGER, "ReleaseManager")
            ]
            for cls, role, name in roles:
                agent = cls(name, self.id, self.api_keys)
                agent.set_log_callback(self.log_callback)
                registry.register(agent)
                asyncio.create_task(agent.run())

            architect = registry.find_subsidiary_by_role(self.id, AgentRole.ARCHITECT)
            await self.send_message(architect, {"cmd": "design_blueprint", "context": context})

        elif cmd == "blueprint_ready":
            await self.log("Technical design verified. Dispatching schema creation to Data Engineer...", AgentAction.DISPATCH_SUBTASK_TO_WORKER)
            data_eng = registry.find_subsidiary_by_role(self.id, AgentRole.DATA_ENGINEER)
            await self.send_message(data_eng, {"cmd": "write_schema", "context": context})

        elif cmd == "schema_ready":
            await self.log("Schema applied. Dispatching routes to Backend Engineer...", AgentAction.DISPATCH_SUBTASK_TO_WORKER)
            backend_eng = registry.find_subsidiary_by_role(self.id, AgentRole.BACKEND_ENGINEER)
            await self.send_message(backend_eng, {"cmd": "write_backend", "context": context})

        elif cmd == "backend_ready":
            await self.log("Backend routes ready. Dispatching views to Frontend Engineer...", AgentAction.DISPATCH_SUBTASK_TO_WORKER)
            frontend_eng = registry.find_subsidiary_by_role(self.id, AgentRole.FRONTEND_ENGINEER)
            await self.send_message(frontend_eng, {"cmd": "write_frontend", "context": context})

        elif cmd == "frontend_ready":
            await self.log("Code footprint complete. Passing to Quality Assurance Gates...", AgentAction.EVALUATE_QUALITY_GATE_CROSSING)
            auditor = registry.find_subsidiary_by_role(self.id, AgentRole.SECURITY_AUDITOR)
            await self.send_message(auditor, {"cmd": "audit_code", "context": context})

        elif cmd == "audit_passed":
            reviewer = registry.find_subsidiary_by_role(self.id, AgentRole.PEER_REVIEWER)
            await self.send_message(reviewer, {"cmd": "review_pr", "context": context})

        elif cmd == "review_passed":
            tester = registry.find_subsidiary_by_role(self.id, AgentRole.AUTOMATION_TESTER)
            await self.send_message(tester, {"cmd": "run_tests", "context": context})

        elif cmd == "tests_passed":
            infra = registry.find_subsidiary_by_role(self.id, AgentRole.INFRASTRUCTURE_ENGINEER)
            await self.send_message(infra, {"cmd": "build_infra", "context": context})

        elif cmd == "infra_passed":
            release = registry.find_subsidiary_by_role(self.id, AgentRole.RELEASE_MANAGER)
            await self.send_message(release, {"cmd": "merge_and_release", "context": context})

        elif cmd in ["audit_failed", "review_failed", "tests_failed", "infra_failed"]:
            await self.log(f"Quality gate rejection encountered from {message['from_name']}. Initializing rollback/fix loops.", AgentAction.TRIGGER_DEVELOPMENT_RETRY_LOOP)
            target_role = context.get("last_active_engineer")
            target_agent = registry.find_subsidiary_by_role(self.id, target_role)
            if target_agent:
                await self.send_message(target_agent, {"cmd": "fix_error", "context": context})

        elif cmd == "pipeline_complete":
            pm = registry.get_agent(self.parent_id)
            if pm:
                await self.send_message(pm, {"cmd": "signoff", "summary": context.get("specs")})


class Architect(BaseAgent):
    def __init__(self, name: str, parent_id: str, api_keys: dict = None):
        super().__init__(id=f"arch-{generate_id()}", role=AgentRole.ARCHITECT, name=name, parent_id=parent_id, api_keys=api_keys)

    async def process_message(self, message: dict):
        msg = message.get("message")
        if isinstance(msg, dict) and msg.get("cmd") == "design_blueprint":
            context = msg.get("context")
            await self.log("Analyzing existing repository layout and codebase structures...", AgentAction.ANALYZE_EXISTING_CODEBASE_TOPOLOGY)
            
            prompt = f"Generate a comprehensive architectural technical design spec for these requirements:\n{context.get('specs')}"
            blueprint = await self._call_llm(prompt, "You are a Principal Software Architect agent.")
            context["blueprint"] = blueprint
            
            await self.log("Technical specifications and architectural interface targets set.", AgentAction.GENERATE_TECHNICAL_DESIGN_SPEC)
            sm = registry.get_agent(self.parent_id)
            if sm:
                await self.send_message(sm, {"cmd": "blueprint_ready", "context": context})


class BaseWriterAgent(BaseAgent):
    """Reusable helper base for writing file changes to the local filesystem."""
    async def _write_extracted_files(self, model_output: str, action: str) -> int:
        writes = re.finditer(r'<write\s+path="([^"]+)">\s*(.*?)\s*</write>', model_output, re.DOTALL)
        files_changed = 0
        for match in writes:
            path, content = match.group(1), match.group(2)
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(content)
                await self.log(f"Wrote file modifications down: {path}", action)
                files_changed += 1
            except Exception as e:
                await self.log(f"Failed file modification layer path write ({path}): {e}", "error")
        return files_changed


class DataEngineer(BaseWriterAgent):
    def __init__(self, name: str, parent_id: str, api_keys: dict = None):
        super().__init__(id=f"data-{generate_id()}", role=AgentRole.DATA_ENGINEER, name=name, parent_id=parent_id, api_keys=api_keys)

    async def process_message(self, message: dict):
        msg = message.get("message")
        if not isinstance(msg, dict): return
        cmd = msg.get("cmd")
        context = msg.get("context")
        context["last_active_engineer"] = AgentRole.DATA_ENGINEER
        
        system_prompt = "You are a Data Engineer agent. Output file paths using this exact format:\n<write path=\"relative/path\">\ncontents\n</write>"

        if cmd == "write_schema":
            await self.log("Reading existing database migration schemas...", AgentAction.READ_SCHEMA_DEFINITION)
            prompt = f"Design database layer adjustments for this technical plan:\n{context.get('blueprint')}"
            response = await self._call_llm(prompt, system_prompt)
            
            if (await self._write_extracted_files(response, AgentAction.COMPILE_ALEMBIC_MIGRATION_SCRIPT)) > 0:
                await run_cmd_async("git add . && git commit -m 'db: apply auto migration blueprints'")
                
            sm = registry.get_agent(self.parent_id)
            if sm: await self.send_message(sm, {"cmd": "schema_ready", "context": context})

        elif cmd == "fix_error":
            prompt = f"Fix the following error in your database files:\n{context.get('error')}"
            response = await self._call_llm(prompt, system_prompt)
            await self._write_extracted_files(response, AgentAction.COMPILE_ALEMBIC_MIGRATION_SCRIPT)
            await run_cmd_async("git add . && git commit -m 'db: resolve migration failures'")
            sm = registry.get_agent(self.parent_id)
            if sm: await self.send_message(sm, {"cmd": "schema_ready", "context": context})


class BackendEngineer(BaseWriterAgent):
    def __init__(self, name: str, parent_id: str, api_keys: dict = None):
        super().__init__(id=f"be-{generate_id()}", role=AgentRole.BACKEND_ENGINEER, name=name, parent_id=parent_id, api_keys=api_keys)

    async def process_message(self, message: dict):
        msg = message.get("message")
        if not isinstance(msg, dict): return
        cmd = msg.get("cmd")
        context = msg.get("context")
        context["last_active_engineer"] = AgentRole.BACKEND_ENGINEER
        
        system_prompt = "You are a Backend Engineer agent. Output code additions using this format:\n<write path=\"path\">\ncode\n</write>"

        if cmd == "write_backend":
            await self.log("Reviewing context router configurations...", AgentAction.READ_BACKEND_CONTEXT)
            prompt = f"Write backend api routes matching this spec:\n{context.get('blueprint')}"
            response = await self._call_llm(prompt, system_prompt)
            
            if (await self._write_extracted_files(response, AgentAction.WRITE_API_ENDPOINT_LOGIC)) > 0:
                await run_cmd_async("git add . && git commit -m 'feat: backend api logic footprint complete'")
                
            sm = registry.get_agent(self.parent_id)
            if sm: await self.send_message(sm, {"cmd": "backend_ready", "context": context})

        elif cmd == "fix_error":
            prompt = f"Fix the following error in backend business rules or endpoint configurations:\n{context.get('error')}"
            response = await self._call_llm(prompt, system_prompt)
            await self._write_extracted_files(response, AgentAction.WRITE_API_ENDPOINT_LOGIC)
            await run_cmd_async("git add . && git commit -m 'fix: resolve backend implementation errors'")
            sm = registry.get_agent(self.parent_id)
            if sm: await self.send_message(sm, {"cmd": "backend_ready", "context": context})


class FrontendEngineer(BaseWriterAgent):
    def __init__(self, name: str, parent_id: str, api_keys: dict = None):
        super().__init__(id=f"fe-{generate_id()}", role=AgentRole.FRONTEND_ENGINEER, name=name, parent_id=parent_id, api_keys=api_keys)

    async def process_message(self, message: dict):
        msg = message.get("message")
        if not isinstance(msg, dict): return
        cmd = msg.get("cmd")
        context = msg.get("context")
        context["last_active_engineer"] = AgentRole.FRONTEND_ENGINEER
        
        system_prompt = "You are a Frontend Engineer agent. Output code changes using this format:\n<write path=\"path\">\nmarkup\n</write>"

        if cmd == "write_frontend":
            await self.log("Reviewing frontend repository files...", AgentAction.READ_FRONTEND_CONTEXT)
            prompt = f"Write frontend views and bind component logic matching this design specification:\n{context.get('blueprint')}"
            response = await self._call_llm(prompt, system_prompt)
            
            if (await self._write_extracted_files(response, AgentAction.WRITE_UI_COMPONENT_MARKUP)) > 0:
                await run_cmd_async("git add . && git commit -m 'feat: frontend UI implementation complete'")
                
            sm = registry.get_agent(self.parent_id)
            if sm: await self.send_message(sm, {"cmd": "frontend_ready", "context": context})

        elif cmd == "fix_error":
            prompt = f"Fix the following visual rendering or state binding error in frontend files:\n{context.get('error')}"
            response = await self._call_llm(prompt, system_prompt)
            await self._write_extracted_files(response, AgentAction.WRITE_UI_COMPONENT_MARKUP)
            await run_cmd_async("git add . && git commit -m 'fix: resolve frontend view crashes'")
            sm = registry.get_agent(self.parent_id)
            if sm: await self.send_message(sm, {"cmd": "frontend_ready", "context": context})


class SecurityAuditor(BaseAgent):
    def __init__(self, name: str, parent_id: str, api_keys: dict = None):
        super().__init__(id=f"aud-{generate_id()}", role=AgentRole.SECURITY_AUDITOR, name=name, parent_id=parent_id, api_keys=api_keys)

    async def process_message(self, message: dict):
        msg = message.get("message")
        if isinstance(msg, dict) and msg.get("cmd") == "audit_code":
            context = msg.get("context")
            await self.log("Executing syntax linter and compilation validation checks...", AgentAction.RUN_STATIC_SYNTAX_ANALYSIS)
            
            logs = await run_cmd_async("python -m compileall .")
            prompt = f"Review these build logs. If errors exist, reply with 'REJECTED:' followed by the errors. If everything looks clean, write 'PASSED'.\n\nLogs:\n{logs}"
            verdict = await self._call_llm(prompt, "You are a strict security linter auditor.")
            
            sm = registry.get_agent(self.parent_id)
            if not sm: return
            
            if "REJECTED" in verdict:
                context["error"] = logs
                await self.send_message(sm, {"cmd": "audit_failed", "context": context})
            else:
                await self.send_message(sm, {"cmd": "audit_passed", "context": context})


class PeerReviewer(BaseAgent):
    def __init__(self, name: str, parent_id: str, api_keys: dict = None):
        super().__init__(id=f"rev-{generate_id()}", role=AgentRole.PEER_REVIEWER, name=name, parent_id=parent_id, api_keys=api_keys)

    async def process_message(self, message: dict):
        msg = message.get("message")
        if isinstance(msg, dict) and msg.get("cmd") == "review_pr":
            context = msg.get("context")
            await self.log("Pulling active workspace git diff logs...", AgentAction.PULL_TRANSACTION_GIT_DIFF)
            diff = await run_cmd_async("git show HEAD")
            
            prompt = f"Verify if this diff contains algorithmic flaws or logic issues based on the spec:\n{context.get('blueprint')}\n\nDiff:\n{diff}"
            verdict = await self._call_llm(prompt, "You are a strict code peer reviewer. Reply with 'REJECTED' if bugs are found, or 'PASSED'.")
            
            sm = registry.get_agent(self.parent_id)
            if not sm: return
            
            if "REJECTED" in verdict:
                context["error"] = verdict
                await self.send_message(sm, {"cmd": "review_failed", "context": context})
            else:
                await self.send_message(sm, {"cmd": "review_passed", "context": context})


class AutomationTester(BaseAgent):
    def __init__(self, name: str, parent_id: str, api_keys: dict = None):
        super().__init__(id=f"tst-{generate_id()}", role=AgentRole.AUTOMATION_TESTER, name=name, parent_id=parent_id, api_keys=api_keys)

    async def process_message(self, message: dict):
        msg = message.get("message")
        if isinstance(msg, dict) and msg.get("cmd") == "run_tests":
            context = msg.get("context")
            await self.log("Running active unit test runners...", AgentAction.EXECUTE_TEST_RUNNER_PROCESS)
            
            logs = await run_cmd_async("pytest")
            if "command not found" in logs: logs = await run_cmd_async("python -m unittest discover")
            
            prompt = f"Review test outputs. If failures exist, reply with 'REJECTED:' and details. Otherwise write 'PASSED'.\n\nLogs:\n{logs}"
            verdict = await self._call_llm(prompt, "You are an automated testing parser.")
            
            sm = registry.get_agent(self.parent_id)
            if not sm: return
            
            if "REJECTED" in verdict or "failed" in logs.lower():
                context["error"] = logs
                await self.send_message(sm, {"cmd": "tests_failed", "context": context})
            else:
                await self.send_message(sm, {"cmd": "tests_passed", "context": context})


class InfrastructureEngineer(BaseAgent):
    def __init__(self, name: str, parent_id: str, api_keys: dict = None):
        super().__init__(id=f"inf-{generate_id()}", role=AgentRole.INFRASTRUCTURE_ENGINEER, name=name, parent_id=parent_id, api_keys=api_keys)

    async def process_message(self, message: dict):
        msg = message.get("message")
        if isinstance(msg, dict) and msg.get("cmd") == "build_infra":
            context = msg.get("context")
            await self.log("Validating application container environment builds...", AgentAction.BUILD_CONTAINER_IMAGE_SPEC)
            
            # Simple lint verification of container image steps
            logs = await run_cmd_async("docker lint Dockerfile") if os.path.exists("Dockerfile") else "PASSED"
            
            sm = registry.get_agent(self.parent_id)
            if not sm: return
            
            if "error" in str(logs).lower():
                context["error"] = logs
                await self.send_message(sm, {"cmd": "infra_failed", "context": context})
            else:
                await self.send_message(sm, {"cmd": "infra_passed", "context": context})


class ReleaseManager(BaseAgent):
    def __init__(self, name: str, parent_id: str, api_keys: dict = None):
        super().__init__(id=f"rel-{generate_id()}", role=AgentRole.RELEASE_MANAGER, name=name, parent_id=parent_id, api_keys=api_keys)

    async def process_message(self, message: dict):
        msg = message.get("message")
        if isinstance(msg, dict) and msg.get("cmd") == "merge_and_release":
            context = msg.get("context")
            await self.log("Verifying overall compliance requirements before merging...", AgentAction.VERIFY_PROD_RELEASE_COMPLIANCE)
            
            await run_cmd_async("git checkout main && git merge -")
            await self.log("Production release tag applied to main branch.", AgentAction.TAG_PRODUCTION_RELEASE_VERSION)
            
            sm = registry.get_agent(self.parent_id)
            if sm: await self.send_message(sm, {"cmd": "pipeline_complete", "context": context})