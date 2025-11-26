# System UML Diagram

The following Mermaid class diagram captures the major modules, data models, and runtime interactions across the CLI, LangGraph workflow, parsing utilities, and telemetry helpers.

```mermaid
classDiagram
    class CLIApp {
        +create_cli_app(console) Typer
        +run_cli(console) void
    }
    class CLICommands {
        +register_cli_commands(app, console) void
        -show_plan(tasks) void
        -review_plan(session, plan) Tuple
    }

    class AnalysisSession {
        -doc_structure Dict~str,str~
        -thread_config Dict
        -graph CompiledGraph
        -_plan List~Task~
        -_planned bool
        +generate_plan() List~Task~
        +update_plan(tasks) void
        +run() str
    }

    class GraphBuilder {
        +build_graph() CompiledGraph
        +map_analyses(state) List~Send~
    }
    class PlannerNode {
        +plan_node(state) Dict
    }
    class WorkerNode {
        +worker_node(state) Dict
    }
    class AggregatorNode {
        +aggregator_node(state) Dict
    }

    class Task {
        dimension str
        section_filter str
        search_query str
    }
    class AnalysisResult {
        dimension str
        content str
        is_valid bool
        retry_count int
    }
    class AgentState {
        doc_structure Dict~str,str~
        plan List~Task~
        analyses List~AnalysisResult~
        final_report str
    }

    class LLMFactory {
        +get_default_llm() BaseChatModel
    }
    class PromptRegistry {
        planner_prompt
        worker_prompt
    }

    class ParsingUtils {
        +parse_pdf_structure(source) Dict~str,str~
        +get_section_context(doc, key) str
    }
    class Telemetry {
        +traceable_if_enabled(...) callable
        +configure_langsmith_env() void
    }

    class Settings {
        default_model str
        default_temperature float
        langsmith_tracing bool
        langsmith_project str
        langsmith_endpoint Optional~str~
        langsmith_api_key Optional~str~
    }

    CLIApp --> CLICommands : delegates
    AnalysisSession --> GraphBuilder : build_graph()
    AnalysisSession --> AgentState : updates
    GraphBuilder --> PlannerNode
    GraphBuilder --> WorkerNode
    GraphBuilder --> AggregatorNode
    Task "1" o-- "*" AgentState
    AnalysisResult "1" o-- "*" AgentState
    LLMFactory --> Settings : load defaults
    PlannerNode --> LLMFactory
    PlannerNode --> PromptRegistry
    WorkerNode --> LLMFactory
    WorkerNode --> PromptRegistry
    WorkerNode --> ParsingUtils
    AggregatorNode --> AgentState
    ParsingUtils --> Telemetry
    Telemetry --> Settings
    CLICommands --> ParsingUtils : parse_pdf_structure()
    CLICommands --> AnalysisSession : orchestrates
```

Render with any Mermaid-compatible viewer (e.g., `npx @mermaid-js/mermaid-cli -i docs/system-uml.md -o diagram.svg`).
