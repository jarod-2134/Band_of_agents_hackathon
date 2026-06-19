import asyncio
from agents.team import PlannerAgent, EngineerAgent, SpawnAgentInput, DelegateTaskInput
from database import init_db
from main import registry

async def run_mock_test():
    print("=== INITIALIZING MOCK TEST (0 TOKENS BURNED) ===")
    
    # 1. Setup DB
    await init_db()
    
    # 2. Instantiate Planner
    org = "test_org"
    planner = PlannerAgent("MockPlanner", org)
    registry.register(org, planner)
    
    # 3. Extract Planner Tools
    planner_tools = {t[0].__name__: t[1] for t in planner.get_tools() if isinstance(t, tuple)}
    
    # 4. Mock the Planner deciding to spawn an Engineer
    print("\n--- Mock Planner: Spawning Engineer ---")
    spawn_func = planner_tools["SpawnAgentInput"]
    result = await spawn_func(SpawnAgentInput(role="engineer", name="MockEngineer"))
    print("Result:", result)
    
    # Extract Engineer ID from registry
    agents = registry.get_all_agents(org)
    engineer_id = [a.id for a in agents if a.role == "engineer"][0]
    
    # 5. Mock the Planner delegating a task
    print("\n--- Mock Planner: Delegating Task ---")
    delegate_func = planner_tools["DelegateTaskInput"]
    result = await delegate_func(DelegateTaskInput(agent_id=engineer_id, task="Build a login page"))
    print("Result:", result)
    
    # 6. Extract Engineer Tools
    engineer = registry.get_agent(org, engineer_id)
    engineer_tools = {t[0].__name__: t[1] for t in engineer.get_tools() if isinstance(t, tuple)}
    
    # 7. Mock the Engineer updating its status
    print("\n--- Mock Engineer: Updating Status ---")
    update_status_func = engineer_tools["UpdateOwnStatusInput"]
    # We need the actual input class
    from agents.team import UpdateOwnStatusInput
    result = await update_status_func(UpdateOwnStatusInput(status="Executing: Build a login page"))
    print("Result:", result)
    print("Registry Status:", registry.get_status(engineer_id))
    
    print("\n=== MOCK TEST COMPLETED ===")

if __name__ == "__main__":
    asyncio.run(run_mock_test())
