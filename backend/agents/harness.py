import asyncio
import os
import subprocess
from typing import Optional
from loguru import logger
from pydantic import BaseModel, Field

from sqlalchemy import select, update
from database import AsyncSessionLocal
from models import CodeNode, EntityNode, TaskNode, ReviewComment, BugReport
from band.runtime.custom_tools import CustomToolDef

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from app.services.semantic_index import semantic_indexer

async def run_cmd_async(cmd: str, timeout: int = 60) -> str:
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=os.getcwd()
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return f"Error: Command timed out after {timeout} seconds."
        return (stdout.decode() + stderr.decode()).strip()
    except Exception as e:
        return str(e)

# ==========================================
# GRAPH & VECTOR DB TOOLS (Optimized)
# ==========================================

class SemanticSearchInput(BaseModel):
    """Searches the repository for code snippets that semantically match the query."""
    query: str = Field(description="The semantic search query.")
    repo_id: str = Field(description="The repository ID.")
    limit: int = Field(default=3, description="Max number of snippets to return.")

async def semantic_search(args: SemanticSearchInput) -> str:
    try:
        embedding = semantic_indexer.encode_text(args.query)
        async with AsyncSessionLocal() as session:
            stmt = (
                select(CodeNode.file_path, CodeNode.content)
                .where(CodeNode.repo_id == args.repo_id)
                .order_by(CodeNode.embedding.l2_distance(embedding))
                .limit(args.limit)
            )
            results = await session.execute(stmt)
            snippets = results.all()
            if not snippets:
                return "No semantic matches found."
            
            formatted = []
            for path, content in snippets:
                truncated = content[:500] + "..." if len(content) > 500 else content
                formatted.append(f"--- File: {path} ---\n{truncated}")
            return "\n".join(formatted)
    except Exception as e:
        return f"Failed to semantic search: {e}"

class GetFileAstInput(BaseModel):
    """Returns a token-optimized outline of classes, functions, and imports in a file."""
    file_path: str = Field(description="The path to the file.")
    repo_id: str = Field(description="The repository ID.")

async def get_file_ast(args: GetFileAstInput) -> str:
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(EntityNode).where(
                EntityNode.repo_id == args.repo_id,
                EntityNode.file_path == args.file_path
            )
            result = await session.execute(stmt)
            nodes = result.scalars().all()
            
            if not nodes:
                return f"No AST nodes indexed for {args.file_path}."
                
            summary = [f"AST for {args.file_path}:"]
            for node in nodes:
                if node.node_type != "file":
                    summary.append(f"- [{node.node_type}] {node.name}")
            return "\n".join(summary)
    except Exception as e:
        return f"Failed to get AST: {e}"

# ==========================================
# ADVANCED ENGINEERING TOOLS
# ==========================================

class ReplaceFileContentInput(BaseModel):
    """Replaces a specific chunk of text in a file. Highly token optimized!"""
    file_path: str
    target_content: str = Field(default="", description="The exact text to be replaced. Or leave blank and use start/end lines.")
    replacement_content: str = Field(description="The new text to insert.")
    start_line: int = Field(default=None, description="Optional starting line number (1-indexed) to replace.")
    end_line: int = Field(default=None, description="Optional ending line number (1-indexed) to replace.")

async def replace_file_content(args: ReplaceFileContentInput) -> str:
    try:
        with open(args.file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        if args.start_line is not None and args.end_line is not None:
            s_idx = max(0, args.start_line - 1)
            e_idx = min(len(lines), args.end_line)
            before = lines[:s_idx]
            after = lines[e_idx:]
            # Ensure replacement_content ends with a newline if we are replacing full lines
            rep = args.replacement_content
            if rep and not rep.endswith("\n"):
                rep += "\n"
            final_content = "".join(before) + rep + "".join(after)
            with open(args.file_path, 'w', encoding='utf-8') as f:
                f.write(final_content)
            return f"Successfully replaced lines {args.start_line}-{args.end_line} in {args.file_path}."
        else:
            content = "".join(lines)
            if args.target_content not in content:
                # Fallback to loose search
                if args.target_content.strip() in content:
                    return "Error: target_content found, but whitespaces did not exactly match. Try using start_line and end_line instead."
                return "Error: target_content exactly as provided was not found in the file."
            new_content = content.replace(args.target_content, args.replacement_content, 1)
            with open(args.file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return f"Successfully replaced target content in {args.file_path}."
    except Exception as e:
        return f"Failed to replace file content: {e}"

class RunTerminalCommandInput(BaseModel):
    """Executes a terminal command locally (e.g., compile, lint). Security restrictions apply."""
    command: str = Field(description="The command to execute (e.g., 'npm run build').")
    working_directory: str = Field(default=".", description="The directory to run the command in.")

async def run_terminal_command(args: RunTerminalCommandInput) -> str:
    # Security checks
    if "npm install" in args.command and (" -g" in args.command or "global" in args.command):
        return "Error: Global 'npm install -g' is strictly forbidden by policy. Install locally."
    
    try:
        proc = await asyncio.create_subprocess_shell(
            args.command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=args.working_directory
        )
        stdout, stderr = await proc.communicate()
        out = stdout.decode() + "\n" + stderr.decode()
        # Truncate to prevent token explosion
        if len(out) > 2000:
            out = out[:1000] + "\n...[TRUNCATED]...\n" + out[-1000:]
        return out.strip() or "Command completed successfully with no output."
    except Exception as e:
        return f"Command execution failed: {e}"

class ScaffoldTemplateInput(BaseModel):
    """Generates boilerplate code from predefined templates."""
    template_name: str = Field(description="Name of the template (e.g., 'python_fastapi', 'react_component').")
    destination_path: str = Field(description="Where to save the scaffolded file.")

async def scaffold_template(args: ScaffoldTemplateInput) -> str:
    template_path = os.path.join(os.path.dirname(__file__), "..", "templates", f"{args.template_name}.txt")
    if not os.path.exists(template_path):
        return f"Error: Template {args.template_name} not found."
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
        os.makedirs(os.path.dirname(os.path.abspath(args.destination_path)), exist_ok=True)
        with open(args.destination_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully scaffolded {args.template_name} to {args.destination_path}."
    except Exception as e:
        return f"Scaffolding failed: {e}"

# ==========================================
# ADVANCED REVIEWER TOOLS
# ==========================================

class GetMergeConflictsInput(BaseModel):
    """Checks the repository for files with active merge conflicts."""
    pass

async def get_merge_conflicts(args: GetMergeConflictsInput) -> str:
    out = await run_cmd_async("git diff --name-only --diff-filter=U")
    if not out.strip():
        return "No merge conflicts found."
    return f"Conflicted files:\n{out}"

class ResolveMergeConflictInput(BaseModel):
    """Replaces a specific conflict block in a file and stages it."""
    file_path: str = Field(description="The conflicted file.")
    conflict_block: str = Field(description="The exact text of the conflict block (including <<<<<<< and >>>>>>> markers).")
    resolution: str = Field(description="The final code to replace the conflict block with.")

async def resolve_merge_conflict(args: ResolveMergeConflictInput) -> str:
    # First, replace the text using the existing logic
    replace_args = ReplaceFileContentInput(
        file_path=args.file_path,
        target_content=args.conflict_block,
        replacement_content=args.resolution
    )
    replace_res = await replace_file_content(replace_args)
    if "Error" in replace_res or "Failed" in replace_res:
        return replace_res
    
    # Stage the file to mark it resolved
    await run_cmd_async(f"git add {args.file_path}")
    return f"Conflict in {args.file_path} resolved and staged successfully."

class LeaveReviewCommentInput(BaseModel):
    """Leaves a concise code review comment on a specific file, saving it to the database."""
    repo_id: str
    file_path: str
    comment: str = Field(description="Short, highly optimized feedback.")
    line_number: int = Field(default=None, description="Optional line number.")

async def leave_review_comment(args: LeaveReviewCommentInput) -> str:
    try:
        async with AsyncSessionLocal() as session:
            comment = ReviewComment(
                repo_id=args.repo_id,
                file_path=args.file_path,
                line_number=args.line_number,
                comment=args.comment
            )
            session.add(comment)
            await session.commit()
            return f"Review comment saved for {args.file_path}."
    except Exception as e:
        return f"Failed to save comment: {e}"

class AnalyzeCodeQualityInput(BaseModel):
    """Runs static analysis (flake8 for python, eslint for js) on a specific file."""
    file_path: str

async def analyze_code_quality(args: AnalyzeCodeQualityInput) -> str:
    if args.file_path.endswith('.py'):
        out = await run_cmd_async(f"flake8 {args.file_path}")
        return out.strip() or "No flake8 issues found."
    elif args.file_path.endswith('.js') or args.file_path.endswith('.tsx') or args.file_path.endswith('.ts'):
        out = await run_cmd_async(f"npx eslint {args.file_path}")
        return out.strip() or "No eslint issues found."
    return "Unsupported file type for automated analysis."

# ==========================================
# ADVANCED TESTER TOOLS
# ==========================================

class GenerateUnitTestInput(BaseModel):
    """Scaffolds a basic boilerplate unit test file for a target source file."""
    source_file_path: str = Field(description="The source file to test (e.g., 'src/calc.py').")
    test_file_path: str = Field(description="The destination test file (e.g., 'tests/test_calc.py').")

async def generate_unit_test(args: GenerateUnitTestInput) -> str:
    try:
        os.makedirs(os.path.dirname(os.path.abspath(args.test_file_path)), exist_ok=True)
        # Simple boilerplate based on extension
        if args.source_file_path.endswith(".py"):
            content = f"import unittest\n# import {os.path.basename(args.source_file_path).replace('.py', '')}\n\nclass Test{os.path.basename(args.source_file_path).replace('.py', '').capitalize()}(unittest.TestCase):\n    def test_example(self):\n        self.assertEqual(1, 1)\n\nif __name__ == '__main__':\n    unittest.main()\n"
        elif args.source_file_path.endswith((".js", ".ts", ".tsx")):
            content = f"// import module from '../{args.source_file_path}';\n\ndescribe('{os.path.basename(args.source_file_path)}', () => {{\n    it('should pass a basic test', () => {{\n        expect(1).toBe(1);\n    }});\n}});\n"
        else:
            content = f"// Boilerplate test for {args.source_file_path}\n"
            
        with open(args.test_file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Scaffolded boilerplate test at {args.test_file_path}."
    except Exception as e:
        return f"Failed to generate test: {e}"

class RunCoverageReportInput(BaseModel):
    """Runs tests with a coverage flag to report test coverage percentage."""
    command: str = Field(description="The command to run (e.g., 'pytest --cov=app' or 'npm run test:cov').")

async def run_coverage_report(args: RunCoverageReportInput) -> str:
    out = await run_cmd_async(args.command)
    # Simple truncation to prevent token bloat
    if len(out) > 1500:
        lines = out.split("\n")
        out = "\n".join(lines[:20] + ["...[TRUNCATED]..."] + lines[-20:])
    return f"Coverage Report:\n{out}"

class CreateBugReportInput(BaseModel):
    """Logs a formal bug report to the database for the React Dashboard."""
    repo_id: str
    summary: str = Field(description="A brief description of the bug.")
    failing_test_name: str = Field(description="Name of the test that failed.")
    stack_trace: str = Field(description="The raw error stack trace.")

async def create_bug_report(args: CreateBugReportInput) -> str:
    try:
        async with AsyncSessionLocal() as session:
            bug = BugReport(
                repo_id=args.repo_id,
                summary=args.summary,
                failing_test_name=args.failing_test_name,
                stack_trace=args.stack_trace
            )
            session.add(bug)
            await session.commit()
            return f"Bug logged to database: {args.summary}"
    except Exception as e:
        return f"Failed to log bug: {e}"

# ==========================================
# GENERAL FILE OPS TOOLS
# ==========================================

class ReadFileInput(BaseModel):
    """Reads the exact content of a file. Paginates to 200 lines if start/end line not specified."""
    file_path: str
    start_line: int = Field(default=None, description="Optional starting line number (1-indexed).")
    end_line: int = Field(default=None, description="Optional ending line number (1-indexed).")

async def read_file(args: ReadFileInput) -> str:
    try:
        if not os.path.exists(args.file_path):
            return f"File not found: {args.file_path}"
        with open(args.file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        s_idx = max(0, args.start_line - 1) if args.start_line is not None else 0
        e_idx = min(len(lines), args.end_line) if args.end_line is not None else len(lines)
        
        # Paginate if start/end not specified and file is long
        if args.start_line is None and args.end_line is None and len(lines) > 200:
            e_idx = 200
            truncated = True
        else:
            truncated = False

        content = "".join(lines[s_idx:e_idx])
        if truncated:
            content += f"\n\n...[TRUNCATED. File has {len(lines)} lines. Use start_line and end_line to read further.]"
        return content
    except Exception as e:
        return f"Error reading file: {e}"

class WriteFileInput(BaseModel):
    """Writes content to a file, creating directories if needed."""
    file_path: str
    content: str

async def write_file(args: WriteFileInput) -> str:
    try:
        os.makedirs(os.path.dirname(os.path.abspath(args.file_path)), exist_ok=True)
        with open(args.file_path, 'w', encoding='utf-8') as f:
            f.write(args.content)
        return f"Successfully wrote to {args.file_path}."
    except Exception as e:
        return f"Error writing file: {e}"

class ListDirectoryInput(BaseModel):
    """Lists contents of a local directory."""
    path: str

async def list_directory(args: ListDirectoryInput) -> str:
    try:
        if not os.path.exists(args.path):
            return f"Directory not found: {args.path}"
        ignored = {".git", "node_modules", "venv", "__pycache__", "dist", "build", ".next"}
        items = [f for f in os.listdir(args.path) if f not in ignored]
        return "\n".join(items)
    except Exception as e:
        return f"Error listing directory: {e}"

# ==========================================
# GIT OPS TOOLS
# ==========================================

class GitStatusInput(BaseModel):
    """Returns the current git status (modified, untracked files)."""
    pass

async def git_status(args: GitStatusInput) -> str:
    return await run_cmd_async("git status -s")

class GitDiffInput(BaseModel):
    """Returns the git diff for uncommitted changes. Specify file_path for a specific file, or leave empty for all."""
    file_path: str = Field(default="", description="Optional path to specific file.")

async def git_diff(args: GitDiffInput) -> str:
    if not args.file_path:
        cmd = "git diff --stat"
    else:
        cmd = f"git diff {args.file_path}".strip()
    out = await run_cmd_async(cmd)
    
    if not args.file_path:
        out = "=== DIFF STAT (Use file_path to see full diff) ===\n" + out
        
    lines = out.split('\n')
    if len(lines) > 2000:
        return "\n".join(lines[:2000]) + "\n...[TRUNCATED: Diff too large. Use file_path to view specific files.]"
    return out

class GitCommitInput(BaseModel):
    """Stages all changes and commits them with the given message."""
    message: str

async def git_commit(args: GitCommitInput) -> str:
    await run_cmd_async("git add .")
    return await run_cmd_async(f"git commit -m \"{args.message}\"")

class GitCheckoutBranchInput(BaseModel):
    """Checks out a git branch. Set create_new to true to create it first."""
    branch_name: str
    create_new: bool = False

async def git_checkout_branch(args: GitCheckoutBranchInput) -> str:
    flag = "-b" if args.create_new else ""
    return await run_cmd_async(f"git checkout {flag} {args.branch_name}")

class GitMergeInput(BaseModel):
    """Merges a source branch into the current branch."""
    source_branch: str

async def git_merge(args: GitMergeInput) -> str:
    return await run_cmd_async(f"git merge {args.source_branch}")

# ==========================================
# PLANNER / PROJECT MANAGEMENT TOOLS
# ==========================================

class CreateTaskInput(BaseModel):
    """Creates a new sub-task for the project."""
    repo_id: str
    title: str
    description: str
    assignee_id: str = Field(default="", description="Agent ID to assign this task to (optional).")

async def create_task(args: CreateTaskInput) -> str:
    try:
        band_room_id = None
        try:
            from main import registry
            for org_slug, agents in registry._org_agents.items():
                for agent in agents.values():
                    if getattr(agent, 'role', None) == 'planner' and getattr(agent, 'band_room_id', None):
                        band_room_id = agent.band_room_id
                        break
                if band_room_id:
                    break
        except Exception:
            pass

        async with AsyncSessionLocal() as session:
            task = TaskNode(
                repo_id=args.repo_id,
                title=args.title,
                description=args.description,
                assignee_id=args.assignee_id,
                band_room_id=band_room_id,
                status="PENDING"
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)
            return f"Created task #{task.id}: {task.title}"
    except Exception as e:
        return f"Failed to create task: {e}"

class UpdateTaskStatusInput(BaseModel):
    """Updates the status of an existing task."""
    task_id: int
    status: str = Field(description="Must be PENDING, IN_PROGRESS, BLOCKED, or COMPLETED.")

async def update_task_status(args: UpdateTaskStatusInput) -> str:
    try:
        async with AsyncSessionLocal() as session:
            stmt = update(TaskNode).where(TaskNode.id == args.task_id).values(status=args.status)
            result = await session.execute(stmt)
            await session.commit()
            if result.rowcount == 0:
                return f"Task #{args.task_id} not found."
            return f"Updated task #{args.task_id} status to {args.status}."
    except Exception as e:
        return f"Failed to update task: {e}"

class GetProjectStatusInput(BaseModel):
    """Retrieves all tasks and their current statuses for the project."""
    repo_id: str
    status_filter: str = Field(default="ACTIVE", description="Optional status filter. 'ACTIVE' excludes COMPLETED tasks.")

async def get_project_status(args: GetProjectStatusInput) -> str:
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(TaskNode).where(TaskNode.repo_id == args.repo_id)
            if args.status_filter:
                if args.status_filter.upper() == "ACTIVE":
                    stmt = stmt.where(TaskNode.status != "COMPLETED")
                else:
                    stmt = stmt.where(TaskNode.status == args.status_filter)
                    
            result = await session.execute(stmt)
            tasks = result.scalars().all()
            if not tasks:
                return f"No tasks found matching filter: {args.status_filter}."
            lines = [f"Project Status (repo: {args.repo_id}, filter: {args.status_filter}):"]
            for t in tasks:
                assignee = f" -> assigned to {t.assignee_id}" if t.assignee_id else ""
                lines.append(f"- [#{t.id}] [{t.status}] {t.title}{assignee}")
            return "\n".join(lines)
    except Exception as e:
        return f"Failed to get project status: {e}"

class SummarizeRepoArchitectureInput(BaseModel):
    """Provides a high-level summary of the repository architecture."""
    repo_id: str

async def summarize_repo_architecture(args: SummarizeRepoArchitectureInput) -> str:
    try:
        async with AsyncSessionLocal() as session:
            # We fetch all file paths to give a tree structure
            stmt = select(EntityNode.file_path).where(
                EntityNode.repo_id == args.repo_id,
                EntityNode.node_type == "file"
            ).distinct()
            result = await session.execute(stmt)
            files = result.scalars().all()
            if not files:
                return "No architecture indexed."
            
            # Simple summary of root folders/files
            folders = set()
            for f in files:
                parts = f.split('/')
                if len(parts) > 1:
                    folders.add(parts[0])
            
            return f"Total files: {len(files)}. Root directories/modules: {', '.join(folders)}"
    except Exception as e:
        return f"Failed to summarize architecture: {e}"


# ==========================================
# TOOL DEFINITION EXPORTS
# ==========================================

TOOL_SEMANTIC_SEARCH: CustomToolDef = (SemanticSearchInput, semantic_search)
TOOL_GET_FILE_AST: CustomToolDef = (GetFileAstInput, get_file_ast)
TOOL_READ_FILE: CustomToolDef = (ReadFileInput, read_file)
TOOL_WRITE_FILE: CustomToolDef = (WriteFileInput, write_file)
TOOL_LIST_DIRECTORY: CustomToolDef = (ListDirectoryInput, list_directory)

TOOL_REPLACE_FILE_CONTENT: CustomToolDef = (ReplaceFileContentInput, replace_file_content)
TOOL_RUN_TERMINAL_COMMAND: CustomToolDef = (RunTerminalCommandInput, run_terminal_command)
TOOL_SCAFFOLD_TEMPLATE: CustomToolDef = (ScaffoldTemplateInput, scaffold_template)

TOOL_GET_MERGE_CONFLICTS: CustomToolDef = (GetMergeConflictsInput, get_merge_conflicts)
TOOL_RESOLVE_MERGE_CONFLICT: CustomToolDef = (ResolveMergeConflictInput, resolve_merge_conflict)
TOOL_LEAVE_REVIEW_COMMENT: CustomToolDef = (LeaveReviewCommentInput, leave_review_comment)
TOOL_ANALYZE_CODE_QUALITY: CustomToolDef = (AnalyzeCodeQualityInput, analyze_code_quality)

TOOL_GENERATE_UNIT_TEST: CustomToolDef = (GenerateUnitTestInput, generate_unit_test)
TOOL_RUN_COVERAGE_REPORT: CustomToolDef = (RunCoverageReportInput, run_coverage_report)
TOOL_CREATE_BUG_REPORT: CustomToolDef = (CreateBugReportInput, create_bug_report)

TOOL_CREATE_TASK: CustomToolDef = (CreateTaskInput, create_task)
TOOL_UPDATE_TASK_STATUS: CustomToolDef = (UpdateTaskStatusInput, update_task_status)
TOOL_GET_PROJECT_STATUS: CustomToolDef = (GetProjectStatusInput, get_project_status)
TOOL_SUMMARIZE_REPO: CustomToolDef = (SummarizeRepoArchitectureInput, summarize_repo_architecture)

TOOL_GIT_STATUS: CustomToolDef = (GitStatusInput, git_status)
TOOL_GIT_DIFF: CustomToolDef = (GitDiffInput, git_diff)
TOOL_GIT_COMMIT: CustomToolDef = (GitCommitInput, git_commit)
TOOL_GIT_CHECKOUT: CustomToolDef = (GitCheckoutBranchInput, git_checkout_branch)
TOOL_GIT_MERGE: CustomToolDef = (GitMergeInput, git_merge)
