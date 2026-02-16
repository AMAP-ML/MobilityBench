"""Batch runner."""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from mobility_bench.config.settings import Settings
from mobility_bench.dataset.schema import Case, RunResult
from mobility_bench.runner.base import BaseRunner, RunConfig
from mobility_bench.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class BatchRunner(BaseRunner):
    """Batch runner.

    Supports multi-model parallel execution and checkpoint resumption.
    """

    def __init__(
        self,
        models: list[str],
        settings: Settings | None = None,
        output_dir: Path | None = None,
        parallel: int = 1,
        sandbox: bool = True,
        framework: str = "plan_and_execute",
    ):
        super().__init__(settings, output_dir)
        self.models = models
        self.parallel = parallel
        self.sandbox = sandbox
        self.framework = framework

        # Load tools
        ToolRegistry.load_default_tools(mode="sandbox" if sandbox else "live")

    def run(
        self,
        cases: list[Case],
        resume_from: str | None = None,
    ) -> dict[str, list[RunResult]]:
        """Run all models.

        Args:
            cases: List of test cases
            resume_from: Run ID to resume from

        Returns:
            Results dictionary organized by model name
        """
        all_results = {}

        for model_name in self.models:
            logger.info(f"Starting model: {model_name}")

            # Create run configuration
            config = RunConfig(
                model_name=model_name,
                output_dir=self.output_dir,
                sandbox=self.sandbox,
                framework=self.framework,
            )

            # Load checkpoint
            completed = []
            if resume_from:
                completed = self.load_checkpoint(self.output_dir, model_name)
                logger.info(f"Resumed from checkpoint, completed {len(completed)} cases")

            # Filter incomplete cases
            pending_cases = [c for c in cases if c.case_id not in completed]
            logger.info(f"Pending cases: {len(pending_cases)}")

            # Run
            if self.parallel > 1:
                results = self._run_parallel(pending_cases, config)
            else:
                results = self._run_sequential(pending_cases, config)

            # Save results
            self.save_results(results, self.output_dir, model_name)

            # Save checkpoint
            new_completed = completed + [r.case_id for r in results if not r.error]
            self.save_checkpoint(self.output_dir, model_name, new_completed)

            all_results[model_name] = results

        return all_results

    def _run_sequential(
        self,
        cases: list[Case],
        config: RunConfig,
    ) -> list[RunResult]:
        """Sequential run."""
        return self.run_batch(cases, config)

    def _run_parallel(
        self,
        cases: list[Case],
        config: RunConfig,
    ) -> list[RunResult]:
        """Parallel run."""
        results = []

        with ThreadPoolExecutor(max_workers=self.parallel) as executor:
            futures = {
                executor.submit(self.run_single, case, config): case
                for case in cases
            }

            for future in as_completed(futures):
                case = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Run failed {case.case_id}: {e}")
                    results.append(RunResult(
                        case_id=case.case_id,
                        model_name=config.model_name,
                        error=str(e),
                    ))

        return results

    def run_single(self, case: Case, config: RunConfig) -> RunResult:
        """Run single case.

        Args:
            case: Test case
            config: Run configuration

        Returns:
            Run result
        """
        start_time = time.time()

        try:
            # Try to import and use existing Agent graph
            result = self._run_with_graph(case, config)
        except ImportError:
            # If import fails, use mock run
            logger.warning("Cannot import Agent graph, using mock run")
            result = self._run_mock(case, config)

        result.execution_time = time.time() - start_time
        return result

    def _run_with_graph(self, case: Case, config: RunConfig) -> RunResult:
        """Run with LangGraph.

        Args:
            case: Test case
            config: Run configuration

        Returns:
            Run result
        """
        try:
            # Import from new agent module
            from mobility_bench.agent.frameworks import FrameworkFactory
            from mobility_bench.agent.roles.llm_manager import set_model_config

            # Set model configuration
            model_config = self.settings.get_model(config.model_name)
            if model_config:
                set_model_config(model_config)

            # Create framework and build graph
            framework = FrameworkFactory.create(
                config.framework,
                settings=self.settings,
                model_config=model_config,
            )
            graph = framework.build_graph()

            # Prepare initial state
            initial_state = framework.prepare_initial_state(
                query=case.query,
                context=case.context,
            )

            # Synchronous run (for async graph)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result_state = loop.run_until_complete(
                    graph.ainvoke(initial_state)
                )
            finally:
                loop.close()

            # Extract results using framework
            extracted = framework.extract_result(result_state)

            return RunResult(
                case_id=case.case_id,
                model_name=config.model_name,
                planner_output=extracted.get("planner_training_data", {}),
                worker_output=extracted.get("worker_training_data", []),
                reporter_output=extracted.get("plan_result", ""),
                token_usage=extracted.get("token_usage", {}),
            )

        except Exception as e:
            logger.error(f"Graph run failed: {e}")
            return RunResult(
                case_id=case.case_id,
                model_name=config.model_name,
                error=str(e),
            )

    def _run_mock(self, case: Case, config: RunConfig) -> RunResult:
        """Mock run (for testing).

        Args:
            case: Test case
            config: Run configuration

        Returns:
            Run result
        """
        return RunResult(
            case_id=case.case_id,
            model_name=config.model_name,
            planner_output={"thinking": "Mock thinking", "intent": "Mock intent"},
            worker_output=[{"tool": "mock_tool", "result": "Mock result"}],
            reporter_output="This is a mock report output.",
            token_usage={
                "planner": {"total": 100},
                "worker": {"total": 200},
                "reporter": {"total": 150},
            },
        )


class SingleModelRunner(BatchRunner):
    """Single model runner."""

    def __init__(
        self,
        model: str,
        settings: Settings | None = None,
        output_dir: Path | None = None,
        sandbox: bool = True,
        framework: str = "plan_and_execute",
    ):
        super().__init__(
            models=[model],
            settings=settings,
            output_dir=output_dir,
            parallel=1,
            sandbox=sandbox,
            framework=framework,
        )

    def run(
        self,
        cases: list[Case],
        resume_from: str | None = None,
    ) -> list[RunResult]:
        """Run single model."""
        all_results = super().run(cases, resume_from)
        return all_results.get(self.models[0], [])
