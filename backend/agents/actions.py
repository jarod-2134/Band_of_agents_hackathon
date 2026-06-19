from enum import Enum

class AgentRole(str, Enum):
    PLANNER = "planner"
    ENGINEER = "engineer"
    REVIEWER = "reviewer"
    TESTER = "tester"

class AgentAction(str, Enum):
    # Planner
    SPIN_UP_AGENT = "planner.spin_up_agent"
    DELEGATE_TASK = "planner.delegate_task"
    MONITOR_PROGRESS = "planner.monitor_progress"
    HANDLE_FAILURE = "planner.handle_failure"

    # Engineer
    READ_CODEBASE = "engineer.read_codebase"
    WRITE_CODE = "engineer.write_code"
    RUN_GIT_OPS = "engineer.run_git_ops"
    FIX_ERROR = "engineer.fix_error"

    # Reviewer
    CHECK_MERGE_CONFLICTS = "reviewer.check_merge_conflicts"
    RESOLVE_CONFLICT = "reviewer.resolve_conflict"
    GATHER_CONTEXT = "reviewer.gather_context"
    REVIEW_PULL_REQUEST = "reviewer.review_pull_request"

    # Tester
    RUN_INHOUSE_TESTS = "tester.run_inhouse_tests"
    REPORT_TEST_RESULTS = "tester.report_test_results"