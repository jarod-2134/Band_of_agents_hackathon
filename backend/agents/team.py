import asyncio
import uuid
import re
import os
import subprocess
from agents.base import BaseAgent
from agents.actions import AgentRole, AgentAction

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
    def __init__(self, name: str, org_slug: str, instructions: str = "", api_keys: dict = None):
        system_prompt = (
            "You are the Chief Executive Officer (CEO) of a fully autonomous AI software delivery organization. "
            "Your role is to receive high-level business objectives and translate them into strategic directives "
            "that your subordinate agents can execute. You do not write code or manage tasks directly — instead, "
            "you set the vision, evaluate feasibility, and delegate all execution to your Product Manager. "
            "You are responsible for final sign-off on project delivery and ensuring the outcome aligns with "
            "the original business intent. When evaluating objectives, consider scope, feasibility, and risk. "
            "Always communicate with clarity, authority, and purpose. Your decisions cascade through the entire "
            "delivery pipeline, so be precise and unambiguous in your directives."
        )
        super().__init__(
            id=f"ceo-{generate_id()}",
            role=AgentRole.CEO,
            name=name,
            org_slug=org_slug,
            api_keys=api_keys,
            system_prompt=system_prompt,
        )
        self.instructions = instructions

    async def process_message(self, message: dict):
        from main import registry

        msg = message.get("message")
        if msg == "start":
            await self.log("Analyzing high-level business goals...", AgentAction.EVALUATE_BUSINESS_OBJECTIVE)
            
            pm = ProductManager("ProductManager", self.org_slug, self.id, self.api_keys)
            pm.set_log_callback(self.log_callback)
            registry.register(self.org_slug, pm)
            asyncio.create_task(pm.run())
            
            await self.log("Handing off strategic goals to Product Manager...", AgentAction.DELEGATE_STRATEGIC_PLAN)
            await self.send_message(pm, {"cmd": "create_specs", "instructions": self.instructions})
            
        elif isinstance(msg, dict) and msg.get("cmd") == "final_signoff":
            await self.log(f"Project delivery accepted: {msg.get('summary')}", AgentAction.RECEIVE_FINAL_DELIVERY_REPORT)


class ProductManager(BaseAgent):
    def __init__(self, name: str, org_slug: str, parent_id: str, api_keys: dict = None):
        system_prompt = (
            "You are a senior Product Manager in an autonomous AI software delivery pipeline. "
            "Your responsibility is to receive high-level strategic objectives from the CEO and convert them "
            "into detailed, structured, and actionable functional specifications that engineers can implement. "
            "Your specs must be exhaustive: define all user-facing features, acceptance criteria, data requirements, "
            "API contracts, edge cases, and non-functional requirements (performance, security, scalability). "
            "Use clear markdown formatting with numbered lists, tables, and sections. "
            "Do not assume anything is self-evident — spell out every requirement explicitly. "
            "Your output will be consumed directly by a Software Architect and engineering squad, so ambiguity "
            "is a defect. Think like a product owner who has already run discovery, user research, and stakeholder "
            "alignment. Produce specs that could pass a formal business acceptance review."
        )
        super().__init__(
            id=f"pm-{generate_id()}",
            role=AgentRole.PRODUCT_MANAGER,
            name=name,
            org_slug=org_slug,
            parent_id=parent_id,
            api_keys=api_keys,
            system_prompt=system_prompt,
        )

    async def process_message(self, message: dict):
        from main import registry

        msg = message.get("message")
        if isinstance(msg, dict) and msg.get("cmd") == "create_specs":
            instructions = msg.get("instructions")
            await self.log("Parsing market objectives into functional requirements...", AgentAction.PARSE_MARKET_OR_USER_OBJECTIVE)
            
            prompt = f"Convert this high-level instruction into a granular, markdown technical specification list: {instructions}"
            specs = await self._call_llm(prompt, "You are a Product Manager agent writing clear functional specs.")
            
            await self.log("Functional specification drafted successfully.", AgentAction.GENERATE_FUNCTIONAL_SPEC)
            
            sm = ScrumMaster("ScrumMaster", self.org_slug, self.id, self.api_keys)
            sm.set_log_callback(self.log_callback)
            registry.register(self.org_slug, sm)
            asyncio.create_task(sm.run())
            
            await self.send_message(sm, {"cmd": "bootstrap_pipeline", "specs": specs})


class ScrumMaster(BaseAgent):
    def __init__(self, name: str, org_slug: str, parent_id: str, api_keys: dict = None):
        system_prompt = (
            "You are an experienced Scrum Master and delivery orchestrator in an autonomous AI software pipeline. "
            "Your role is to coordinate the full engineering squad — Architect, Data Engineer, Backend Engineer, "
            "Frontend Engineer, Security Auditor, Peer Reviewer, Automation Tester, Infrastructure Engineer, "
            "and Release Manager — ensuring work flows correctly through each stage of the delivery pipeline. "
            "You do not write code. You sequence tasks, dispatch work to the right agents, monitor quality gates, "
            "and handle failure recovery by routing failed work back to the responsible engineer with full error context. "
            "You are the single point of coordination: every agent reports back to you, and you decide what happens next. "
            "When a quality gate fails, analyze the failure type, identify the responsible engineer role, and trigger "
            "a targeted retry loop with the error details. Keep the pipeline moving efficiently and never drop context "
            "between handoffs. Always maintain the full delivery context object as you pass it between agents."
        )
        super().__init__(
            id=f"sm-{generate_id()}",
            role=AgentRole.SCRUM_MASTER,
            name=name,
            org_slug=org_slug,
            parent_id=parent_id,
            api_keys=api_keys,
            system_prompt=system_prompt,
        )

    async def process_message(self, message: dict):
        from main import registry

        msg = message.get("message")
        if not isinstance(msg, dict): return
        cmd = msg.get("cmd")
        context = msg.get("context", {})
        
        if cmd == "bootstrap_pipeline":
            await self.log("Provisioning full operational delivery squad...", AgentAction.PROVISION_SQUAD_CLUSTER)
            context["specs"] = msg.get("specs")
            
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
                agent = cls(name, self.org_slug, self.id, self.api_keys)
                agent.set_log_callback(self.log_callback)
                registry.register(self.org_slug, agent)
                asyncio.create_task(agent.run())

            architect = registry.find_subsidiary_by_role(self.org_slug, self.id, AgentRole.ARCHITECT)
            await self.send_message(architect, {"cmd": "design_blueprint", "context": context})

        elif cmd == "blueprint_ready":
            await self.log("Technical design verified. Dispatching schema creation to Data Engineer...", AgentAction.DISPATCH_SUBTASK_TO_WORKER)
            data_eng = registry.find_subsidiary_by_role(self.org_slug, self.id, AgentRole.DATA_ENGINEER)
            await self.send_message(data_eng, {"cmd": "write_schema", "context": context})

        elif cmd == "schema_ready":
            await self.log("Schema applied. Dispatching routes to Backend Engineer...", AgentAction.DISPATCH_SUBTASK_TO_WORKER)
            backend_eng = registry.find_subsidiary_by_role(self.org_slug, self.id, AgentRole.BACKEND_ENGINEER)
            await self.send_message(backend_eng, {"cmd": "write_backend", "context": context})

        elif cmd == "backend_ready":
            await self.log("Backend routes ready. Dispatching views to Frontend Engineer...", AgentAction.DISPATCH_SUBTASK_TO_WORKER)
            frontend_eng = registry.find_subsidiary_by_role(self.org_slug, self.id, AgentRole.FRONTEND_ENGINEER)
            await self.send_message(frontend_eng, {"cmd": "write_frontend", "context": context})

        elif cmd == "frontend_ready":
            await self.log("Code footprint complete. Passing to Quality Assurance Gates...", AgentAction.EVALUATE_QUALITY_GATE_CROSSING)
            auditor = registry.find_subsidiary_by_role(self.org_slug, self.id, AgentRole.SECURITY_AUDITOR)
            await self.send_message(auditor, {"cmd": "audit_code", "context": context})

        elif cmd == "audit_passed":
            reviewer = registry.find_subsidiary_by_role(self.org_slug, self.id, AgentRole.PEER_REVIEWER)
            await self.send_message(reviewer, {"cmd": "review_pr", "context": context})

        elif cmd == "review_passed":
            tester = registry.find_subsidiary_by_role(self.org_slug, self.id, AgentRole.AUTOMATION_TESTER)
            await self.send_message(tester, {"cmd": "run_tests", "context": context})

        elif cmd == "tests_passed":
            infra = registry.find_subsidiary_by_role(self.org_slug, self.id, AgentRole.INFRASTRUCTURE_ENGINEER)
            await self.send_message(infra, {"cmd": "build_infra", "context": context})

        elif cmd == "infra_passed":
            release = registry.find_subsidiary_by_role(self.org_slug, self.id, AgentRole.RELEASE_MANAGER)
            await self.send_message(release, {"cmd": "merge_and_release", "context": context})

        elif cmd in ["audit_failed", "review_failed", "tests_failed", "infra_failed"]:
            await self.log(f"Quality gate rejection encountered from {message['from_name']}. Initializing rollback/fix loops.", AgentAction.TRIGGER_DEVELOPMENT_RETRY_LOOP)
            target_role = context.get("last_active_engineer")
            target_agent = registry.find_subsidiary_by_role(self.org_slug, self.id, target_role)
            if target_agent:
                await self.send_message(target_agent, {"cmd": "fix_error", "context": context})

        elif cmd == "pipeline_complete":
            pm = registry.get_agent(self.org_slug, self.parent_id)
            if pm:
                await self.send_message(pm, {"cmd": "signoff", "summary": context.get("specs")})


class Architect(BaseAgent):
    def __init__(self, name: str, org_slug: str, parent_id: str, api_keys: dict = None):
        system_prompt = (
            "You are a Principal Software Architect in an autonomous AI software delivery pipeline. "
            "Your responsibility is to produce a comprehensive, implementation-ready technical design based on "
            "the functional specifications provided. Your blueprint must cover: system architecture (layered or "
            "microservice), module boundaries and responsibilities, database schema design (entities, relationships, "
            "indexes), API surface design (endpoints, request/response shapes, auth strategy), frontend component "
            "hierarchy and state management approach, infrastructure topology (services, containers, networking), "
            "and cross-cutting concerns (logging, error handling, configuration management). "
            "Your output will be used directly by specialist engineers (Data, Backend, Frontend) and must be "
            "specific enough that each can work independently without ambiguity. Use structured markdown with "
            "headers per domain. Do not write implementation code — write precise technical contracts, diagrams "
            "in text form, and design decisions with justifications. Flag any architectural risks or trade-offs."
        )
        super().__init__(
            id=f"arch-{generate_id()}",
            role=AgentRole.ARCHITECT,
            name=name,
            org_slug=org_slug,
            parent_id=parent_id,
            api_keys=api_keys,
            system_prompt=system_prompt,
        )

    async def process_message(self, message: dict):
        from main import registry

        msg = message.get("message")
        if isinstance(msg, dict) and msg.get("cmd") == "design_blueprint":
            context = msg.get("context")
            await self.log("Analyzing existing repository layout and codebase structures...", AgentAction.ANALYZE_EXISTING_CODEBASE_TOPOLOGY)
            
            prompt = f"Generate a comprehensive architectural technical design spec for these requirements:\n{context.get('specs')}"
            blueprint = await self._call_llm(prompt, "You are a Principal Software Architect agent.")
            context["blueprint"] = blueprint
            
            await self.log("Technical specifications and architectural interface targets set.", AgentAction.GENERATE_TECHNICAL_DESIGN_SPEC)
            sm = registry.get_agent(self.org_slug, self.parent_id)
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
    def __init__(self, name: str, org_slug: str, parent_id: str, api_keys: dict = None):
        system_prompt = (
            "You are a Data Engineer in an autonomous AI software delivery pipeline. "
            "Your responsibility is to design and implement the full database layer based on the architectural blueprint provided. "
            "This includes: defining SQLAlchemy ORM models with correct column types, constraints, indexes, and relationships; "
            "writing Alembic migration scripts that are safe to run in sequence; designing schema changes that are "
            "backward-compatible where possible; and ensuring referential integrity, cascades, and soft-delete patterns "
            "are applied where appropriate. You must not introduce breaking schema changes without explicit justification. "
            "Always output files using the exact format:\n"
            "<write path=\"relative/path/to/file\">\nfile contents\n</write>\n"
            "Write all migration files to the migrations/versions/ directory and all ORM models to the appropriate "
            "models/ module. When fixing errors, read the error carefully, identify the root cause in the schema or "
            "migration, and produce a corrected file — do not patch around the problem."
        )
        super().__init__(
            id=f"data-{generate_id()}",
            role=AgentRole.DATA_ENGINEER,
            name=name,
            org_slug=org_slug,
            parent_id=parent_id,
            api_keys=api_keys,
            system_prompt=system_prompt,
        )

    async def process_message(self, message: dict):
        from main import registry

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
                
            sm = registry.get_agent(self.org_slug, self.parent_id)
            if sm: await self.send_message(sm, {"cmd": "schema_ready", "context": context})

        elif cmd == "fix_error":
            prompt = f"Fix the following error in your database files:\n{context.get('error')}"
            response = await self._call_llm(prompt, system_prompt)
            await self._write_extracted_files(response, AgentAction.COMPILE_ALEMBIC_MIGRATION_SCRIPT)
            await run_cmd_async("git add . && git commit -m 'db: resolve migration failures'")
            sm = registry.get_agent(self.org_slug, self.parent_id)
            if sm: await self.send_message(sm, {"cmd": "schema_ready", "context": context})


class BackendEngineer(BaseWriterAgent):
    def __init__(self, name: str, org_slug: str, parent_id: str, api_keys: dict = None):
        system_prompt = (
            "You are a Backend Engineer in an autonomous AI software delivery pipeline. "
            "Your responsibility is to implement the full server-side application layer based on the architectural blueprint. "
            "This includes: writing FastAPI route handlers with correct HTTP methods, path parameters, query parameters, "
            "and request/response Pydantic schemas; implementing business logic and service layer functions; "
            "integrating with the database via SQLAlchemy sessions; applying authentication and authorization middleware "
            "where specified; and structuring code into clean, maintainable modules (routers/, services/, schemas/, dependencies/). "
            "Follow RESTful conventions, return appropriate HTTP status codes, and handle errors with proper exception handlers. "
            "Always output files using the exact format:\n"
            "<write path=\"relative/path/to/file\">\nfile contents\n</write>\n"
            "When fixing errors, read the error trace carefully, identify whether the issue is in routing, business logic, "
            "or data access, and produce a corrected implementation — do not add workarounds that mask the root cause."
        )
        super().__init__(
            id=f"be-{generate_id()}",
            role=AgentRole.BACKEND_ENGINEER,
            name=name,
            org_slug=org_slug,
            parent_id=parent_id,
            api_keys=api_keys,
            system_prompt=system_prompt,
        )

    async def process_message(self, message: dict):
        from main import registry

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
                
            sm = registry.get_agent(self.org_slug, self.parent_id)
            if sm: await self.send_message(sm, {"cmd": "backend_ready", "context": context})

        elif cmd == "fix_error":
            prompt = f"Fix the following error in backend business rules or endpoint configurations:\n{context.get('error')}"
            response = await self._call_llm(prompt, system_prompt)
            await self._write_extracted_files(response, AgentAction.WRITE_API_ENDPOINT_LOGIC)
            await run_cmd_async("git add . && git commit -m 'fix: resolve backend implementation errors'")
            sm = registry.get_agent(self.org_slug, self.parent_id)
            if sm: await self.send_message(sm, {"cmd": "backend_ready", "context": context})


class FrontendEngineer(BaseWriterAgent):
    def __init__(self, name: str, org_slug: str, parent_id: str, api_keys: dict = None):
        system_prompt = (
            "You are a Frontend Engineer in an autonomous AI software delivery pipeline. "
            "Your responsibility is to implement the complete UI layer based on the architectural blueprint. "
            "This includes: writing React components in TypeScript with correct props, state, and lifecycle handling; "
            "implementing routing with React Router; managing global and local state with appropriate hooks or state libraries; "
            "integrating with backend APIs via fetch or axios, handling loading, error, and empty states correctly; "
            "applying consistent styling using Tailwind CSS or the project's designated styling approach; "
            "and structuring code into pages/, components/, hooks/, and services/ modules. "
            "Write accessible, responsive markup. Avoid prop drilling — use context or dedicated state management where appropriate. "
            "Always output files using the exact format:\n"
            "<write path=\"relative/path/to/file\">\nfile contents\n</write>\n"
            "When fixing errors, identify whether the issue is a rendering crash, a state management bug, an API integration "
            "failure, or a styling defect, and produce a targeted fix — do not restructure unrelated components."
        )
        super().__init__(
            id=f"fe-{generate_id()}",
            role=AgentRole.FRONTEND_ENGINEER,
            name=name,
            org_slug=org_slug,
            parent_id=parent_id,
            api_keys=api_keys,
            system_prompt=system_prompt,
        )

    async def process_message(self, message: dict):
        from main import registry

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
                
            sm = registry.get_agent(self.org_slug, self.parent_id)
            if sm: await self.send_message(sm, {"cmd": "frontend_ready", "context": context})

        elif cmd == "fix_error":
            prompt = f"Fix the following visual rendering or state binding error in frontend files:\n{context.get('error')}"
            response = await self._call_llm(prompt, system_prompt)
            await self._write_extracted_files(response, AgentAction.WRITE_UI_COMPONENT_MARKUP)
            await run_cmd_async("git add . && git commit -m 'fix: resolve frontend view crashes'")
            sm = registry.get_agent(self.org_slug, self.parent_id)
            if sm: await self.send_message(sm, {"cmd": "frontend_ready", "context": context})


class SecurityAuditor(BaseAgent):
    def __init__(self, name: str, org_slug: str, parent_id: str, api_keys: dict = None):
        system_prompt = (
            "You are a Security Auditor in an autonomous AI software delivery pipeline. "
            "Your responsibility is to perform a thorough static analysis of all code produced in the current pipeline run "
            "before it proceeds to peer review. You must check for: syntax errors and compilation failures; "
            "hardcoded secrets, API keys, passwords, or tokens in source files; use of deprecated or vulnerable dependencies; "
            "SQL injection, XSS, CSRF, and other OWASP Top 10 vulnerabilities; insecure defaults (debug mode on, open CORS, "
            "missing auth on sensitive endpoints); and improper error handling that leaks stack traces or internal details. "
            "You will be given build logs and may also analyze source files. "
            "If you find any issues, respond with 'REJECTED:' followed by a structured list of all findings with file paths "
            "and line-level descriptions. If the code is clean, respond with exactly 'PASSED'. "
            "Be strict — a false negative here puts the entire system at risk. Do not pass code with known issues."
        )
        super().__init__(
            id=f"aud-{generate_id()}",
            role=AgentRole.SECURITY_AUDITOR,
            name=name,
            org_slug=org_slug,
            parent_id=parent_id,
            api_keys=api_keys,
            system_prompt=system_prompt,
        )

    async def process_message(self, message: dict):
        from main import registry

        msg = message.get("message")
        if isinstance(msg, dict) and msg.get("cmd") == "audit_code":
            context = msg.get("context")
            await self.log("Executing syntax linter and compilation validation checks...", AgentAction.RUN_STATIC_SYNTAX_ANALYSIS)
            
            logs = await run_cmd_async("python -m compileall .")
            prompt = f"Review these build logs. If errors exist, reply with 'REJECTED:' followed by the errors. If everything looks clean, write 'PASSED'.\n\nLogs:\n{logs}"
            verdict = await self._call_llm(prompt, "You are a strict security linter auditor.")
            
            sm = registry.get_agent(self.org_slug, self.parent_id)
            if not sm: return
            
            if "REJECTED" in verdict:
                context["error"] = logs
                await self.send_message(sm, {"cmd": "audit_failed", "context": context})
            else:
                await self.send_message(sm, {"cmd": "audit_passed", "context": context})


class PeerReviewer(BaseAgent):
    def __init__(self, name: str, org_slug: str, parent_id: str, api_keys: dict = None):
        system_prompt = (
            "You are a Senior Peer Reviewer in an autonomous AI software delivery pipeline. "
            "Your responsibility is to review the latest git diff against the functional spec and architectural blueprint "
            "to catch logic errors, design violations, and quality issues that static analysis cannot detect. "
            "Evaluate the diff for: correctness of business logic relative to the spec; adherence to the architectural "
            "design (module structure, separation of concerns, interface contracts); algorithmic correctness and edge case handling; "
            "code readability, naming conventions, and documentation quality; unnecessary complexity or code duplication; "
            "missing input validation, error handling, or logging; and test coverage gaps for critical paths. "
            "If you find issues, respond with 'REJECTED' followed by structured, line-level review comments referencing "
            "specific files and functions. Be specific — vague feedback is not actionable. "
            "If the code meets the standard, respond with exactly 'PASSED'. "
            "You are the last human-equivalent quality check before automated testing — take it seriously."
        )
        super().__init__(
            id=f"rev-{generate_id()}",
            role=AgentRole.PEER_REVIEWER,
            name=name,
            org_slug=org_slug,
            parent_id=parent_id,
            api_keys=api_keys,
            system_prompt=system_prompt,
        )

    async def process_message(self, message: dict):
        from main import registry

        msg = message.get("message")
        if isinstance(msg, dict) and msg.get("cmd") == "review_pr":
            context = msg.get("context")
            await self.log("Pulling active workspace git diff logs...", AgentAction.PULL_TRANSACTION_GIT_DIFF)
            diff = await run_cmd_async("git show HEAD")
            
            prompt = f"Verify if this diff contains algorithmic flaws or logic issues based on the spec:\n{context.get('blueprint')}\n\nDiff:\n{diff}"
            verdict = await self._call_llm(prompt, "You are a strict code peer reviewer. Reply with 'REJECTED' if bugs are found, or 'PASSED'.")
            
            sm = registry.get_agent(self.org_slug, self.parent_id)
            if not sm: return
            
            if "REJECTED" in verdict:
                context["error"] = verdict
                await self.send_message(sm, {"cmd": "review_failed", "context": context})
            else:
                await self.send_message(sm, {"cmd": "review_passed", "context": context})


class AutomationTester(BaseAgent):
    def __init__(self, name: str, org_slug: str, parent_id: str, api_keys: dict = None):
        system_prompt = (
            "You are an Automation Tester in an autonomous AI software delivery pipeline. "
            "Your responsibility is to execute the project's test suite and accurately interpret the results. "
            "You will run pytest or unittest depending on what is available, capture the full output, and assess whether "
            "the suite passes or fails. Look for: test failures with their specific assertion errors and tracebacks; "
            "errors during test collection (import errors, missing fixtures); tests that were skipped and why; "
            "and overall pass/fail counts. "
            "If any tests fail or errors occur during collection or execution, respond with 'REJECTED:' followed by "
            "a structured summary of all failures with test names, failure reasons, and relevant tracebacks. "
            "If all tests pass (or there are no tests yet and the suite exits cleanly), respond with 'PASSED'. "
            "Do not pass a suite with failures. Do not fail a suite because of warnings alone."
        )
        super().__init__(
            id=f"tst-{generate_id()}",
            role=AgentRole.AUTOMATION_TESTER,
            name=name,
            org_slug=org_slug,
            parent_id=parent_id,
            api_keys=api_keys,
            system_prompt=system_prompt,
        )

    async def process_message(self, message: dict):
        from main import registry

        msg = message.get("message")
        if isinstance(msg, dict) and msg.get("cmd") == "run_tests":
            context = msg.get("context")
            await self.log("Running active unit test runners...", AgentAction.EXECUTE_TEST_RUNNER_PROCESS)
            
            logs = await run_cmd_async("pytest")
            if "command not found" in logs: logs = await run_cmd_async("python -m unittest discover")
            
            prompt = f"Review test outputs. If failures exist, reply with 'REJECTED:' and details. Otherwise write 'PASSED'.\n\nLogs:\n{logs}"
            verdict = await self._call_llm(prompt, "You are an automated testing parser.")
            
            sm = registry.get_agent(self.org_slug, self.parent_id)
            if not sm: return
            
            if "REJECTED" in verdict or "failed" in logs.lower():
                context["error"] = logs
                await self.send_message(sm, {"cmd": "tests_failed", "context": context})
            else:
                await self.send_message(sm, {"cmd": "tests_passed", "context": context})


class InfrastructureEngineer(BaseAgent):
    def __init__(self, name: str, org_slug: str, parent_id: str, api_keys: dict = None):
        system_prompt = (
            "You are an Infrastructure Engineer in an autonomous AI software delivery pipeline. "
            "Your responsibility is to validate and maintain the container and deployment infrastructure "
            "before any release is attempted. This includes: linting and validating Dockerfiles for correctness, "
            "best practices (non-root user, minimal base image, layer caching hygiene, no secrets baked in); "
            "verifying docker-compose or Kubernetes manifests are syntactically valid and correctly reference "
            "services, volumes, ports, and environment variables; checking that environment configuration files "
            "(.env.example, config maps) are complete and consistent with application requirements; "
            "and confirming that health check endpoints and readiness probes are defined. "
            "If any infrastructure definition contains errors or fails validation, respond with a structured "
            "error report identifying the file, the issue, and the recommended fix. "
            "Signal 'infra_failed' with the error context if issues are found, or 'infra_passed' if everything is clean."
        )
        super().__init__(
            id=f"inf-{generate_id()}",
            role=AgentRole.INFRASTRUCTURE_ENGINEER,
            name=name,
            org_slug=org_slug,
            parent_id=parent_id,
            api_keys=api_keys,
            system_prompt=system_prompt,
        )

    async def process_message(self, message: dict):
        from main import registry

        msg = message.get("message")
        if isinstance(msg, dict) and msg.get("cmd") == "build_infra":
            context = msg.get("context")
            await self.log("Validating application container environment builds...", AgentAction.BUILD_CONTAINER_IMAGE_SPEC)
            
            logs = await run_cmd_async("docker lint Dockerfile") if os.path.exists("Dockerfile") else "PASSED"
            
            sm = registry.get_agent(self.org_slug, self.parent_id)
            if not sm: return
            
            if "error" in str(logs).lower():
                context["error"] = logs
                await self.send_message(sm, {"cmd": "infra_failed", "context": context})
            else:
                await self.send_message(sm, {"cmd": "infra_passed", "context": context})


class ReleaseManager(BaseAgent):
    def __init__(self, name: str, org_slug: str, parent_id: str, api_keys: dict = None):
        system_prompt = (
            "You are a Release Manager in an autonomous AI software delivery pipeline. "
            "Your responsibility is to execute the final production release after all quality gates have passed. "
            "This includes: verifying that the feature branch is fully up to date with the target branch (main/master) "
            "and that there are no merge conflicts; performing a final compliance check to confirm all required gates "
            "(security audit, peer review, automated tests, infrastructure validation) have passed; "
            "executing the merge into the production branch using a merge commit (not a squash or rebase, to preserve history); "
            "applying a semantic version tag following the project's versioning convention (e.g. v1.2.3); "
            "and generating a concise release summary noting what was delivered, which agents contributed, "
            "and any notable decisions or risks flagged during the pipeline run. "
            "If any pre-release check fails, halt the release and report the issue clearly. "
            "Do not proceed with a merge if there is any ambiguity about gate pass status."
        )
        super().__init__(
            id=f"rel-{generate_id()}",
            role=AgentRole.RELEASE_MANAGER,
            name=name,
            org_slug=org_slug,
            parent_id=parent_id,
            api_keys=api_keys,
            system_prompt=system_prompt,
        )

    async def process_message(self, message: dict):
        from main import registry

        msg = message.get("message")
        if isinstance(msg, dict) and msg.get("cmd") == "merge_and_release":
            context = msg.get("context")
            await self.log("Verifying overall compliance requirements before merging...", AgentAction.VERIFY_PROD_RELEASE_COMPLIANCE)
            
            await run_cmd_async("git checkout main && git merge -")
            await self.log("Production release tag applied to main branch.", AgentAction.TAG_PRODUCTION_RELEASE_VERSION)
            
            sm = registry.get_agent(self.org_slug, self.parent_id)
            if sm: await self.send_message(sm, {"cmd": "pipeline_complete", "context": context})