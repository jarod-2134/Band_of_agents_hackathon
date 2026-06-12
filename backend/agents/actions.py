from enum import Enum

class AgentRole(str, Enum):
    CEO = "ceo"
    MANAGER = "manager"
    ENGINEER = "engineer"
    REVIEWER = "reviewer"
    TESTER = "tester"

class AgentAction(str, Enum):
    # CEO Actions
    CREATE_TEAM = "create_team"
    DELEGATE_TASK = "delegate_task"
    
    # Manager Actions
    HIRE_SPECIALIST = "hire_specialist"
    ASSIGN_WORK = "assign_work"
    REPORT_TO_CEO = "report_to_ceo"
    
    # Engineer Actions
    READ_FILE = "read_file"
    WRITE_CODE = "write_code"
    SEARCH_CODE = "search_code"
    
    # Reviewer Actions
    LINT_CODE = "lint_code"
    APPROVE_PR = "approve_pr"
    
    # Tester Actions
    RUN_TESTS = "run_tests"
