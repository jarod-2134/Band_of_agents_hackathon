import asyncio
import os
import sys

from sqlalchemy import text
from agents.team import PlannerAgent, SpawnAgentInput
from agents.harness import WriteFileInput, GitCommitInput, AnalyzeCodeQualityInput, GenerateUnitTestInput
from database import init_db, AsyncSessionLocal
from app.routers.repos import create_repository, RepoCreatePayload
from app.services.semantic_index import semantic_indexer
from main import registry

async def run_e2e_test():
    print("=== STARTING END-TO-END MOCK TEST ===")
    
    semantic_indexer.load_model()
    await init_db()
    org_slug = "default"
    repo_name = "e2e_test_repo"
    
    print(f"\n--- 1. Creating Fresh Repository '{repo_name}' ---")
    async with AsyncSessionLocal() as db:
        try:
            res = await create_repository(org_slug, RepoCreatePayload(name=repo_name), db)
            print("Repo Created:", res)
            repo_fs_path = res["path"]
        except Exception as e:
            print("Repo creation skipped or failed (might already exist):", e)
            result = await db.execute(text("SELECT fs_path FROM repos WHERE name=:n AND org_slug=:o"), {"n":repo_name, "o":org_slug})
            row = result.mappings().first()
            if row:
                repo_fs_path = row["fs_path"]
            else:
                print("Failed to recover repo path.")
                return

    # Set up physical paths
    repos_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "repos"))
    workspace_dir = os.path.join(repos_dir, repo_fs_path)
    
    print("\n--- 2. Spawning Planner Agent ---")
    planner = PlannerAgent("E2E_Planner", org_slug)
    registry.register(org_slug, planner)
    planner_tools = {t[0].__name__: t[1] for t in planner.get_tools() if isinstance(t, tuple)}
    
    print("\n--- 3. Planner Dynamically Spawns Squad ---")
    spawn_func = planner_tools["SpawnAgentInput"]
    await spawn_func(SpawnAgentInput(role="engineer", name="E2E_Engineer"))
    await spawn_func(SpawnAgentInput(role="reviewer", name="E2E_Reviewer"))
    await spawn_func(SpawnAgentInput(role="tester", name="E2E_Tester"))
    
    agents = registry.get_all_agents(org_slug)
    engineer = next(a for a in agents if a.role == "engineer")
    reviewer = next(a for a in agents if a.role == "reviewer")
    tester = next(a for a in agents if a.role == "tester")
    
    print(f"Spawned: {engineer.name} ({engineer.id}), {reviewer.name} ({reviewer.id}), {tester.name} ({tester.id})")
    
    print("\n--- 4. Engineer Creates hello_world.txt ---")
    eng_tools = {t[0].__name__: t[1] for t in engineer.get_tools() if isinstance(t, tuple)}
    
    from agents.harness import write_file, git_commit, analyze_code_quality, generate_unit_test
    
    file_target = os.path.join(workspace_dir, "hello_world.txt")
    res = await write_file(WriteFileInput(file_path=file_target, content="Hello World! E2E Test successful.\n"))
    print("Write result:", res)
    
    print("\n--- 5. Engineer Commits to Repository ---")
    original_cwd = os.getcwd()
    os.chdir(workspace_dir)
    try:
        res = await git_commit(GitCommitInput(message="feat: Add hello world test file"))
        print("Commit result:", res)
    finally:
        os.chdir(original_cwd)
        
    print("\n--- 6. Reviewer Analyzes Code ---")
    os.chdir(workspace_dir)
    try:
        res = await analyze_code_quality(AnalyzeCodeQualityInput(file_path="hello_world.txt"))
        print("Analysis result:", res)
    finally:
        os.chdir(original_cwd)
        
    print("\n--- 7. Tester Generates Dummy Unit Test ---")
    test_target = os.path.join(workspace_dir, "test_hello_world.py")
    res = await generate_unit_test(GenerateUnitTestInput(source_file_path="hello_world.txt", test_file_path=test_target))
    print("Generate Test result:", res)
    
    print("\n=== E2E MOCK TEST COMPLETED ===")

if __name__ == "__main__":
    asyncio.run(run_e2e_test())
