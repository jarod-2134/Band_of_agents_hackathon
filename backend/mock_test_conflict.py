import asyncio
import os

from sqlalchemy import text
from agents.team import PlannerAgent, SpawnAgentInput
from database import init_db, AsyncSessionLocal
from app.routers.repos import create_repository, RepoCreatePayload
from app.services.semantic_index import semantic_indexer
from main import registry

async def run_conflict_test():
    print("=== STARTING HARDCORE MERGE CONFLICT MOCK TEST ===")
    
    semantic_indexer.load_model()
    await init_db()
    org_slug = "default"
    repo_name = "conflict_test_repo_v2"
    
    print(f"\n--- 1. Creating Fresh Repository '{repo_name}' ---")
    async with AsyncSessionLocal() as db:
        try:
            res = await create_repository(org_slug, RepoCreatePayload(name=repo_name), db)
            print("Repo Created:", res)
            repo_fs_path = res["path"]
        except Exception as e:
            print("Repo creation skipped or failed:", e)
            result = await db.execute(text("SELECT fs_path FROM repos WHERE name=:n AND org_slug=:o"), {"n":repo_name, "o":org_slug})
            row = result.mappings().first()
            if row:
                repo_fs_path = row["fs_path"]
            else:
                print("Failed to recover repo path.")
                return

    # Set up physical paths
    repos_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "repos"))
    workspace_dir = os.path.join(repos_dir, repo_fs_path)
    
    print("\n--- 2. Spawning Planner Agent ---")
    planner = PlannerAgent("Conflict_Planner", org_slug)
    registry.register(org_slug, planner)
    planner_tools = {t[0].__name__: t[1] for t in planner.get_tools() if isinstance(t, tuple)}
    
    print("\n--- 3. Planner Dynamically Spawns Squad ---")
    spawn_func = planner_tools["SpawnAgentInput"]
    await spawn_func(SpawnAgentInput(role="engineer", name="Eng_Alice"))
    await spawn_func(SpawnAgentInput(role="engineer", name="Eng_Bob"))
    await spawn_func(SpawnAgentInput(role="reviewer", name="Rev_Charlie"))
    
    agents = registry.get_all_agents(org_slug)
    alice = next(a for a in agents if a.name == "Eng_Alice")
    bob = next(a for a in agents if a.name == "Eng_Bob")
    charlie = next(a for a in agents if a.name == "Rev_Charlie")
    
    from agents.harness import (
        write_file, git_commit, git_checkout_branch, git_merge,
        get_merge_conflicts, resolve_merge_conflict, read_file,
        WriteFileInput, GitCommitInput, GitCheckoutBranchInput, GitMergeInput,
        GetMergeConflictsInput, ResolveMergeConflictInput, ReadFileInput
    )
    
    file_target = os.path.join(workspace_dir, "config.txt")
    
    original_cwd = os.getcwd()
    os.chdir(workspace_dir)
    
    try:
        print("\n--- 4. Base Setup: Create file on main ---")
        await write_file(WriteFileInput(file_path=file_target, content="version=base\n"))
        await git_commit(GitCommitInput(message="Initial base config"))
        
        print("\n--- 5. Engineer Alice (Branch A) ---")
        await git_checkout_branch(GitCheckoutBranchInput(branch_name="feat-a", create_new=True))
        await write_file(WriteFileInput(file_path=file_target, content="version=alice\n"))
        res_a = await git_commit(GitCommitInput(message="Alice's changes"))
        print(f"Alice committed: {res_a}")
        
        print("\n--- 6. Engineer Bob (Branch B) ---")
        await git_checkout_branch(GitCheckoutBranchInput(branch_name="main", create_new=False))
        await git_checkout_branch(GitCheckoutBranchInput(branch_name="feat-b", create_new=True))
        await write_file(WriteFileInput(file_path=file_target, content="version=bob\n"))
        res_b = await git_commit(GitCommitInput(message="Bob's changes"))
        print(f"Bob committed: {res_b}")
        
        print("\n--- 7. Alice Merges Branch A into Main ---")
        await git_checkout_branch(GitCheckoutBranchInput(branch_name="main", create_new=False))
        res_merge_a = await git_merge(GitMergeInput(source_branch="feat-a"))
        print(f"Alice Merge Result: {res_merge_a}")
        
        print("\n--- 8. Bob Tries to Merge Branch B into Main (CONFLICT!) ---")
        res_merge_b = await git_merge(GitMergeInput(source_branch="feat-b"))
        print(f"Bob Merge Result: {res_merge_b}")
        
        print("\n--- 9. Reviewer Charlie steps in ---")
        conflict_res = await get_merge_conflicts(GetMergeConflictsInput())
        print(f"Conflicts detected: {conflict_res}")
        
        # Charlie reads the file to see the markers
        file_content = await read_file(ReadFileInput(file_path=file_target))
        print(f"\nCharlie reads conflicted file:\n{file_content}")
        
        # Charlie resolves it
        print("\n--- 10. Reviewer Charlie Resolves Conflict ---")
        conflict_block = file_content.strip() # The whole file is the conflict block in this case
        resolution = "version=merged-alice-and-bob\n"
        
        res_resolve = await resolve_merge_conflict(ResolveMergeConflictInput(
            file_path=file_target,
            conflict_block=file_content, # match exact content
            resolution=resolution
        ))
        print(f"Charlie Resolution Result: {res_resolve}")
        
        print("\n--- 11. Reviewer Charlie Finalizes Merge ---")
        res_final = await git_commit(GitCommitInput(message="Merge conflict resolved by Reviewer Charlie"))
        print(f"Final commit: {res_final}")
        
        final_file = await read_file(ReadFileInput(file_path=file_target))
        print(f"\nFinal unified config.txt:\n{final_file}")

    finally:
        os.chdir(original_cwd)
        
    print("\n=== HARDCORE MERGE CONFLICT MOCK TEST COMPLETED ===")

if __name__ == "__main__":
    asyncio.run(run_conflict_test())
