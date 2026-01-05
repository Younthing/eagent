# Development Guide

<cite>
**Referenced Files in This Document**   
- [test_completeness_validator.py](file://tests/unit/test_completeness_validator.py)
- [check_bm25_retrieval.py](file://scripts/check_bm25_retrieval.py)
- [pyproject.toml](file://pyproject.toml)
- [test_rob2_workflow_retry.py](file://tests/integration/test_rob2_workflow_retry.py)
- [audit.py](file://src/cli/commands/audit.py)
- [check_fusion.py](file://scripts/check_fusion.py)
- [check_validation.py](file://scripts/check_validation.py)
- [completeness.py](file://src/pipelines/graphs/nodes/validators/completeness.py)
- [bm25.py](file://src/retrieval/engines/bm25.py)
- [rob2.py](file://src/schemas/internal/rob2.py)
- [check_question_bank.py](file://scripts/check_question_bank.py)
- [check_rule_based_locator.py](file://scripts/check_rule_based_locator.py)
- [rob2_runner.py](file://src/services/rob2_runner.py)
- [rob2_graph.py](file://src/pipelines/graphs/rob2_graph.py)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Testing Strategy](#testing-strategy)
3. [Utility Scripts](#utility-scripts)
4. [Development Workflow](#development-workflow)
5. [Writing Tests for New Features](#writing-tests-for-new-features)
6. [Debugging Tools and Techniques](#debugging-tools-and-techniques)
7. [Performance Testing and Optimization](#performance-testing-and-optimization)
8. [Extending the System](#extending-the-system)
9. [Conclusion](#conclusion)

## Introduction
This development guide provides comprehensive documentation for developers contributing to the eagent project. The system implements a LangGraph-based workflow for ROB2 (Risk of Bias 2) assessment in clinical trials, with a focus on evidence retrieval, validation, and domain-specific reasoning. The guide covers testing strategies, utility scripts for component verification, development workflows, debugging techniques, and extension patterns to ensure consistent and maintainable contributions.

## Testing Strategy

The project employs a comprehensive testing strategy with both unit and integration tests located in the `tests/` directory. The testing framework is built on pytest, with tests organized into `unit/` and `integration/` subdirectories to distinguish between isolated component tests and end-to-end workflow validation.

Unit tests in `tests/unit/` focus on individual components and functions, ensuring that each piece of logic works correctly in isolation. For example, the completeness validator is tested to verify that it properly handles evidence validation under various conditions, including when relevance is required versus optional. These tests use mock data and state objects to simulate different scenarios and validate the expected outputs.

Integration tests in `tests/integration/` validate the interaction between multiple components and the overall workflow. The `test_rob2_workflow_retry.py` file contains tests that verify the retry mechanism in the validation layer, ensuring that the system can recover from consistency failures by adjusting retrieval parameters and reprocessing evidence. These tests use stub implementations of LLM components to simulate different responses and verify the system's behavior under various conditions.

The testing strategy emphasizes state-based validation, where the input state is carefully constructed to represent specific scenarios, and the output state is examined to ensure it matches expected patterns. This approach allows for comprehensive coverage of edge cases and error conditions without requiring actual LLM calls during testing.

**Section sources**
- [test_completeness_validator.py](file://tests/unit/test_completeness_validator.py#L1-L127)
- [test_rob2_workflow_retry.py](file://tests/integration/test_rob2_workflow_retry.py#L1-L278)

## Utility Scripts

The `scripts/` directory contains a collection of utility scripts designed for component verification and debugging. These scripts provide command-line interfaces to exercise specific parts of the system, making it easier to test and debug individual components without running the full workflow.

The `check_bm25_retrieval.py` script allows developers to test the BM25 retrieval engine with various configurations, including different query planners, rerankers, and structure-aware filtering. It prints detailed information about the retrieval process, including queries generated, candidates found, and ranking scores. This script is particularly useful for tuning retrieval parameters and understanding how different configurations affect the results.

The `check_fusion.py` script verifies the evidence fusion process across multiple retrieval methods (rule-based, BM25, and SPLADE). It runs each locator independently, fuses the results using Reciprocal Rank Fusion (RRF), and prints the top-k fused candidates. This script helps developers understand how different retrieval methods contribute to the final evidence set and how the fusion algorithm combines their outputs.

The `check_validation.py` script tests the full validation layer, including relevance, existence, consistency, and completeness validation. It allows developers to configure validation modes and thresholds to see how they affect the final validated evidence. This script is essential for understanding the validation pipeline and debugging issues with evidence filtering.

Other utility scripts include `check_question_bank.py` for inspecting the ROB2 question bank and `check_rule_based_locator.py` for testing the rule-based evidence locator. These scripts provide visibility into the system's configuration and rule-based components, helping developers ensure that questions and rules are correctly defined and loaded.

**Section sources**
- [check_bm25_retrieval.py](file://scripts/check_bm25_retrieval.py#L1-L358)
- [check_fusion.py](file://scripts/check_fusion.py#L1-L296)
- [check_validation.py](file://scripts/check_validation.py#L1-L272)
- [check_question_bank.py](file://scripts/check_question_bank.py#L1-L76)
- [check_rule_based_locator.py](file://scripts/check_rule_based_locator.py#L1-L111)

## Development Workflow

The development workflow for the eagent project follows a structured process that emphasizes testing, code quality, and consistent contribution practices. Developers should set up their environment using the project's dependencies specified in `pyproject.toml`, which includes required packages for development, testing, and visualization.

The workflow begins with understanding the system architecture and component interactions. The core of the system is the LangGraph workflow defined in `rob2_graph.py`, which orchestrates the sequence of operations from document preprocessing to final risk assessment. Developers should familiarize themselves with this workflow and the state structure it uses to pass data between nodes.

When implementing new features or modifying existing ones, developers should follow a test-driven approach. This involves writing tests that define the expected behavior before implementing the code. The tests should cover both normal operation and edge cases, using the same state-based testing pattern as the existing tests.

Code contributions should adhere to the project's coding standards, which include using type hints, writing clear docstrings, and following Python best practices. The project uses Pydantic for data validation, so new components should leverage this framework to ensure data integrity.

Before submitting a pull request, developers should run the full test suite to ensure their changes don't break existing functionality. They should also use the utility scripts to verify that their changes work as expected in the context of the full system.

**Section sources**
- [pyproject.toml](file://pyproject.toml#L1-L56)
- [rob2_graph.py](file://src/pipelines/graphs/rob2_graph.py#L1-L426)

## Writing Tests for New Features

When writing tests for new features, developers should follow the existing patterns in the test suite. Tests should be organized by component and type (unit vs. integration), with clear and descriptive names that indicate what is being tested.

For unit tests, create a new file in the `tests/unit/` directory if one doesn't already exist for the component. Use pytest's parameterized testing features to test multiple scenarios with a single test function. When testing functions that depend on external components, use mocking to isolate the component under test.

For integration tests, add to the `tests/integration/` directory, focusing on how the new feature interacts with existing components. Use the same state-based testing approach as existing integration tests, constructing input states that represent realistic scenarios and verifying the output states against expected patterns.

When testing components that involve LLM calls, use the same stub pattern as in `test_rob2_workflow_retry.py`, where dummy LLM classes are created to simulate different responses. This allows for testing different LLM behaviors without making actual API calls.

Tests should validate both the primary outputs and any side effects, such as state modifications or logging. Use assertions to verify that the results match expected values, and include comments explaining why each assertion is important.

**Section sources**
- [test_completeness_validator.py](file://tests/unit/test_completeness_validator.py#L1-L127)
- [test_rob2_workflow_retry.py](file://tests/integration/test_rob2_workflow_retry.py#L1-L278)

## Debugging Tools and Techniques

The eagent project provides several tools and techniques for debugging issues. The primary debugging approach is to use the utility scripts in the `scripts/` directory, which allow developers to exercise specific components with detailed output.

For debugging the retrieval process, use `check_bm25_retrieval.py` with the `--full` flag to see all candidates instead of just the top-k results. This can help identify issues with query generation or ranking. The script's detailed output shows the queries generated, the candidates found, and the scores assigned, making it easier to understand why certain candidates are ranked higher than others.

For debugging the validation pipeline, use `check_validation.py` with different validation modes and thresholds. This script shows how each validation step filters the evidence and can help identify why certain candidates are being rejected. The `--full` flag can be used to see all validated candidates, not just the top-k.

The system also includes built-in debugging features, such as the ability to include debug payloads in the output. When running the full workflow, set the `debug_level` option to "full" to include the complete state in the output, which can be invaluable for understanding the system's behavior at each step.

For debugging issues with the LangGraph workflow, examine the state transitions and conditional edges in `rob2_graph.py`. The workflow includes retry mechanisms and conditional routing, which can be complex to debug. Use the integration tests as a starting point for understanding how the workflow behaves under different conditions.

**Section sources**
- [check_bm25_retrieval.py](file://scripts/check_bm25_retrieval.py#L1-L358)
- [check_validation.py](file://scripts/check_validation.py#L1-L272)
- [rob2_graph.py](file://src/pipelines/graphs/rob2_graph.py#L1-L426)

## Performance Testing and Optimization

Performance testing in the eagent project focuses on the efficiency of the evidence retrieval and validation pipeline. The system processes academic papers to assess risk of bias, which requires efficient text processing and information retrieval.

Key performance metrics include retrieval speed, memory usage, and the accuracy of the final risk assessment. Developers should use the utility scripts to measure these metrics under different conditions, such as varying document sizes and retrieval configurations.

Optimization opportunities exist in several areas. The BM25 retrieval engine in `bm25.py` could be optimized by improving the indexing strategy or using more efficient data structures. The fusion algorithm could be optimized by adjusting the RRF parameters or implementing more sophisticated fusion methods.

The validation pipeline offers opportunities for parallelization, as some validation steps could potentially be run concurrently rather than sequentially. The system's use of LangGraph provides a foundation for implementing parallel execution, which could significantly improve performance.

When optimizing, developers should use profiling tools to identify bottlenecks and measure the impact of changes. The utility scripts can be modified to include timing information, helping to quantify performance improvements.

**Section sources**
- [bm25.py](file://src/retrieval/engines/bm25.py#L1-L149)
- [check_bm25_retrieval.py](file://scripts/check_bm25_retrieval.py#L1-L358)
- [rob2_graph.py](file://src/pipelines/graphs/rob2_graph.py#L1-L426)

## Extending the System

Extending the eagent system with new features or integrations should follow the existing architectural patterns. New components should be implemented as nodes in the LangGraph workflow, with clear inputs and outputs defined in the state structure.

When adding new retrieval methods, create a new locator node similar to the existing ones in `pipelines/graphs/nodes/locators/`. The node should accept the current state as input and return updated state with the new candidates. Add the node to the workflow in `rob2_graph.py`, ensuring it fits into the existing sequence of operations.

For new validation steps, implement a validator node following the pattern in `pipelines/graphs/nodes/validators/`. The validator should check the evidence against specific criteria and update the state with the results. Integrate the validator into the validation pipeline, considering whether it should run before or after existing validators.

When adding new domain reasoning capabilities, create a new domain node similar to the D1-D5 nodes in `pipelines/graphs/nodes/domains/`. The node should perform domain-specific analysis and return a decision that fits the existing decision structure.

New features should be accompanied by appropriate tests and utility scripts to facilitate testing and debugging. Documentation should be updated to reflect the new capabilities, following the existing documentation style.

**Section sources**
- [rob2_graph.py](file://src/pipelines/graphs/rob2_graph.py#L1-L426)
- [completeness.py](file://src/pipelines/graphs/nodes/validators/completeness.py#L1-L140)

## Conclusion
This development guide provides a comprehensive overview of the eagent project's testing strategy, utility scripts, development workflow, and extension patterns. By following these guidelines, developers can contribute effectively to the project while maintaining code quality and consistency. The combination of unit and integration tests, utility scripts for component verification, and clear development practices ensures that the system remains robust and maintainable as it evolves.