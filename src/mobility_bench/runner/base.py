"""Runner base class."""

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from mobility_bench.config.settings import Settings
from mobility_bench.dataset.schema import Case, RunResult

logger = logging.getLogger(__name__)


@dataclass
class RunConfig:
    """Run configuration."""

    model_name: str
    output_dir: Path
    framework: str = "plan_and_execute"  # Agent framework: plan_and_execute or react
    sandbox: bool = True
    max_iterations: int = 10
    timeout: int = 300
    retry_count: int = 3


class BaseRunner(ABC):
    """Runner base class."""

    def __init__(
        self,
        settings: Settings | None = None,
        output_dir: Path | None = None,
    ):
        self.settings = settings or Settings.get_instance()
        self.output_dir = Path(output_dir) if output_dir else Path("data/results")

    @abstractmethod
    def run_single(self, case: Case, config: RunConfig) -> RunResult:
        """Run single case.

        Args:
            case: Test case
            config: Run configuration

        Returns:
            Run result
        """
        pass

    def run_batch(
        self,
        cases: list[Case],
        config: RunConfig,
        progress_callback=None,
    ) -> list[RunResult]:
        """Batch run.

        Args:
            cases: List of test cases
            config: Run configuration
            progress_callback: Optional callback for progress reporting.
                Signature: (event, model_name, case_id, current, total, status)

        Returns:
            List of run results
        """
        results = []
        total = len(cases)
        for i, case in enumerate(cases):
            logger.info(f"Running {i+1}/{total}: {case.case_id}")
            try:
                result = self.run_single(case, config)
                results.append(result)
                status = "failed" if result.error else "success"
            except Exception as e:
                logger.error(f"Run failed {case.case_id}: {e}")
                results.append(RunResult(
                    case_id=case.case_id,
                    model_name=config.model_name,
                    error=str(e),
                ))
                status = "failed"

            if progress_callback:
                progress_callback(
                    "case_complete", config.model_name,
                    case.case_id, i + 1, total, status,
                )

        return results

    def save_results(
        self,
        results: list[RunResult],
        output_dir: Path,
        model_name: str,
    ):
        """Save run results.

        Args:
            results: List of run results
            output_dir: Output directory
            model_name: Model name
        """
        model_dir = output_dir / model_name
        model_dir.mkdir(parents=True, exist_ok=True)

        # Save raw results
        raw_file = model_dir / "raw_results.json"
        with open(raw_file, "w", encoding="utf-8") as f:
            json.dump(
                [r.to_dict() for r in results],
                f,
                ensure_ascii=False,
                indent=2,
            )

        logger.info(f"Results saved to: {model_dir}")

    def load_checkpoint(self, output_dir: Path, model_name: str) -> list[str]:
        """Load checkpoint, return list of completed case_ids.

        Args:
            output_dir: Output directory
            model_name: Model name

        Returns:
            List of completed case_ids
        """
        checkpoint_file = output_dir / model_name / "checkpoint.json"
        if checkpoint_file.exists():
            with open(checkpoint_file) as f:
                data = json.load(f)
                return data.get("completed", [])
        return []

    def save_checkpoint(
        self,
        output_dir: Path,
        model_name: str,
        completed: list[str],
    ):
        """Save checkpoint.

        Args:
            output_dir: Output directory
            model_name: Model name
            completed: List of completed case_ids
        """
        model_dir = output_dir / model_name
        model_dir.mkdir(parents=True, exist_ok=True)

        checkpoint_file = model_dir / "checkpoint.json"
        with open(checkpoint_file, "w") as f:
            json.dump({"completed": completed}, f)
