# System UML Diagram (Current Implementation)

This diagram reflects the current code structure, not the target architecture described in the requirements.

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
        -doc_structure Dict~str,object~
        -thread_config Dict
        -graph CompiledGraph
        -_plan List~Task~
        -_planned bool
        +generate_plan() List~Task~
        +update_plan(tasks) void
        +run() Optional~str~
    }

    class GraphBuilder {
        +build_graph() CompiledGraph
        +map_analyses(state) List~Send~
        -checkpointer MemorySaver
        -interrupt_before List~str~
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
        doc_structure Dict~str,object~
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
        +parse_pdf_structure(source) Dict~str,object~
    }
    class MemorySaver

    note for WorkerNode "Retries up to 3 times; invalid results set is_valid=false."
    note for AggregatorNode "Aggregates only analyses where is_valid=true."
    class ContextLookup {
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
    GraphBuilder --> MemorySaver : checkpoint
    Task "1" o-- "*" AgentState
    AnalysisResult "1" o-- "*" AgentState
    LLMFactory --> Settings : load defaults
    PlannerNode --> LLMFactory
    PlannerNode --> PromptRegistry
    WorkerNode --> LLMFactory
    WorkerNode --> PromptRegistry
    AggregatorNode --> AgentState
    ParsingUtils --> Telemetry
    Telemetry --> Settings
    CLICommands --> ParsingUtils : parse_pdf_structure()
    WorkerNode --> ContextLookup : section context
    CLICommands --> AnalysisSession : orchestrates
```

Render with any Mermaid-compatible viewer (e.g., `npx @mermaid-js/mermaid-cli -i docs/system-uml.md -o diagram.svg`).
