from enum import Enum

stuffs = 1

class AgentRole(str, Enum):
    CEO = "ceo"
    PRODUCT_MANAGER = "product_manager"
    SCRUM_MASTER = "scrum_master"
    ARCHITECT = "architect"
    BACKEND_ENGINEER = "backend_engineer"
    FRONTEND_ENGINEER = "frontend_engineer"
    DATA_ENGINEER = "data_engineer"
    SECURITY_AUDITOR = "security_auditor"
    PEER_REVIEWER = "peer_review_reviewer"
    AUTOMATION_TESTER = "automation_tester"
    INFRASTRUCTURE_ENGINEER = "infrastructure_engineer"
    RELEASE_MANAGER = "release_manager"

class AgentAction(str, Enum):
    # CEO
    INITIALIZE_PROJECT_ORCHESTRATION = "ceo.initialize_project_orchestration"
    EVALUATE_BUSINESS_OBJECTIVE = "ceo.evaluate_business_objective"
    RECEIVE_FINAL_DELIVERY_REPORT = "ceo.receive_final_delivery_report"

    # Product Manager
    PARSE_MARKET_OR_USER_OBJECTIVE = "product_manager.parse_market_or_user_objective"
    GENERATE_FUNCTIONAL_SPEC = "product_manager.generate_functional_spec"
    VALIDATE_BUSINESS_ACCEPTANCE_CRITERIA = "product_manager.validate_business_acceptance_criteria"

    # Scrum Master
    PROVISION_SQUAD_CLUSTER = "scrum_master.provision_squad_cluster"
    DISPATCH_SUBTASK_TO_WORKER = "scrum_master.dispatch_subtask_to_worker"
    EVALUATE_QUALITY_GATE_CROSSING = "scrum_master.evaluate_quality_gate_crossing"
    TRIGGER_DEVELOPMENT_RETRY_LOOP = "scrum_master.trigger_development_retry_loop"
    COMPILE_SYSTEM_STATUS_REPORT = "scrum_master.compile_system_status_report"

    # Architect
    ANALYZE_EXISTING_CODEBASE_TOPOLOGY = "architect.analyze_codebase_topology"
    GENERATE_TECHNICAL_DESIGN_SPEC = "architect.generate_technical_design_spec"
    VERIFY_INTERFACE_COMPLIANCE = "architect.verify_interface_compliance"

    # Backend Engineer
    READ_BACKEND_CONTEXT = "backend_engineer.read_backend_context"
    WRITE_API_ENDPOINT_LOGIC = "backend_engineer.write_api_endpoint_logic"
    IMPLEMENT_BUSINESS_RULES = "backend_engineer.implement_business_rules"
    STAGE_AND_COMMIT_BACKEND = "backend_engineer.stage_and_commit_backend"

    # Frontend Engineer
    READ_FRONTEND_CONTEXT = "frontend_engineer.read_frontend_context"
    WRITE_UI_COMPONENT_MARKUP = "frontend_engineer.write_ui_component_markup"
    BIND_STATE_MANAGEMENT_HOOKS = "frontend_engineer.bind_state_management_hooks"
    STAGE_AND_COMMIT_FRONTEND = "frontend_engineer.stage_and_commit_frontend"

    # Data Engineer
    READ_SCHEMA_DEFINITION = "data_engineer.read_schema_definition"
    GENERATE_ORM_MODEL_PROPERTIES = "data_engineer.generate_orm_model_properties"
    COMPILE_ALEMBIC_MIGRATION_SCRIPT = "data_engineer.compile_alembic_migration_script"
    STAGE_AND_COMMIT_MIGRATIONS = "data_engineer.stage_and_commit_migrations"

    # Security Auditor
    RUN_STATIC_SYNTAX_ANALYSIS = "security_auditor.run_static_syntax_analysis"
    AUDIT_DEPENDENCY_VULNERABILITIES = "security_auditor.audit_dependency_vulnerabilities"
    VERIFY_SECRET_LEAK_COMPLIANCE = "security_auditor.verify_secret_leak_compliance"

    # Peer Reviewer
    PULL_TRANSACTION_GIT_DIFF = "peer_reviewer.pull_transaction_git_diff"
    EVALUATE_ALGORITHMIC_COMPLEXITY = "peer_reviewer.evaluate_algorithmic_complexity"
    EMIT_LINE_LEVEL_REVIEW_COMMENT = "peer_reviewer.emit_line_level_review_comment"
    APPROVE_WORKSPACE_PULL_REQUEST = "peer_reviewer.approve_workspace_pull_request"

    # Automation Tester
    DISCOVER_EXISTING_TEST_SUITE = "automation_tester.discover_existing_test_suite"
    GENERATE_DYNAMIC_UNIT_TEST = "automation_tester.generate_dynamic_unit_test"
    EXECUTE_TEST_RUNNER_PROCESS = "automation_tester.execute_test_runner_process"

    # Infrastructure Engineer
    BUILD_CONTAINER_IMAGE_SPEC = "infrastructure_engineer.build_container_image_spec"
    PROVISION_EPHEMERAL_STAGING_ENV = "infrastructure_engineer.provision_ephemeral_staging_env"
    EXECUTE_ENVIRONMENT_HEALTH_CHECK = "infrastructure_engineer.execute_env_health_check"

    # Release Manager
    VERIFY_PROD_RELEASE_COMPLIANCE = "release_manager.verify_prod_release_compliance"
    MERGE_UPSTREAM_TARGET_BRANCH = "release_manager.merge_upstream_target_branch"
    TAG_PRODUCTION_RELEASE_VERSION = "release_manager.tag_production_release_version"