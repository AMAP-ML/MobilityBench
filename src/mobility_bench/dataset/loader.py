"""Dataset loader."""

import ast
import json
from collections.abc import Iterator
from pathlib import Path

import pandas as pd

from mobility_bench.config.settings import Settings
from mobility_bench.dataset.schema import Case, GroundTruth


class DatasetLoader:
    """Dataset loader.

    Supports loading datasets from Excel, JSON, and other formats.
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings.get_instance()

    def load(self, dataset: str) -> list[Case]:
        """Load dataset.

        Args:
            dataset: Dataset name or path

        Returns:
            List of test cases
        """
        # Check if it's a path
        path = Path(dataset)
        if path.exists():
            return self._load_from_path(path)

        # Check dataset in configuration
        ds_config = self.settings.get_dataset(dataset)
        if ds_config:
            return self._load_from_path(Path(ds_config.path))

        # Try to find in data/datasets directory
        for ext in [".xlsx", ".csv", ".json"]:
            candidate = Path("data/datasets") / f"{dataset}{ext}"
            if candidate.exists():
                return self._load_from_path(candidate)

        raise FileNotFoundError(f"Dataset not found: {dataset}")

    def _load_from_path(self, path: Path) -> list[Case]:
        """Load dataset from path."""
        suffix = path.suffix.lower()

        if suffix in [".xlsx", ".xls"]:
            return self._load_excel(path)
        elif suffix == ".csv":
            return self._load_csv(path)
        elif suffix == ".json":
            return self._load_json(path)
        else:
            raise ValueError(f"Unsupported file format: {suffix}")

    def _load_excel(self, path: Path) -> list[Case]:
        """Load from Excel."""
        df = pd.read_excel(path)
        return self._df_to_cases(df)

    def _load_csv(self, path: Path) -> list[Case]:
        """Load from CSV."""
        df = pd.read_csv(path)
        return self._df_to_cases(df)

    def _load_json(self, path: Path) -> list[Case]:
        """Load from JSON."""
        with open(path) as f:
            data = json.load(f)

        if isinstance(data, list):
            return [Case.from_dict(item) for item in data]
        elif isinstance(data, dict) and "cases" in data:
            return [Case.from_dict(item) for item in data["cases"]]
        else:
            raise ValueError("Invalid JSON format, expected list or dict with 'cases' key")

    # Fields that may contain JSON strings in CSV/Excel
    _JSON_FIELDS = [
        "tool_list", "poi_result", "route_ans",
        "strategy_list", "context",
        "std_start", "std_transit", "std_end",
        "near_poi_info", "near_poi_ans",
        "bus_lines_list", "query_poi",
        "weather", "location_ans", "ans_loc",
    ]

    def _df_to_cases(self, df: pd.DataFrame) -> list[Case]:
        """Convert DataFrame to list of Cases."""
        cases = []

        # Generate case_id if not present
        if "case_id" not in df.columns and "Case ID" not in df.columns:
            df["case_id"] = [f"case_{i+1}" for i in range(len(df))]

        for _, row in df.iterrows():
            data = row.to_dict()

            # Parse potential JSON string fields
            for field in self._JSON_FIELDS:
                if field in data:
                    data[field] = self._parse_json_field(data[field])

            # Replace NaN values with appropriate defaults
            for key, value in data.items():
                if pd.isna(value) if isinstance(value, float) else False:
                    data[key] = ""

            cases.append(Case.from_dict(data))

        return cases

    def _parse_json_field(self, value) -> any:
        """Parse JSON field."""
        if pd.isna(value) or value == "":
            return None

        if isinstance(value, (list, dict)):
            return value

        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                try:
                    return ast.literal_eval(value)
                except (ValueError, SyntaxError):
                    return value

        return value

    def get_cases(self, dataset: str) -> Iterator[Case]:
        """Get case iterator (lazy loading)."""
        cases = self.load(dataset)
        yield from cases

    def get_ground_truth(self, case_id: str, dataset: str) -> GroundTruth | None:
        """Get ground truth for specified case."""
        cases = self.load(dataset)
        for case in cases:
            if case.case_id == case_id:
                return case.ground_truth
        return None

    def split(self, dataset: str, train_ratio: float = 0.8) -> tuple[list[Case], list[Case]]:
        """Split dataset.

        Args:
            dataset: Dataset name or path
            train_ratio: Training set ratio

        Returns:
            (train_set, test_set)
        """
        cases = self.load(dataset)
        split_idx = int(len(cases) * train_ratio)
        return cases[:split_idx], cases[split_idx:]

    def filter_by_source(self, cases: list[Case], source_file: str) -> list[Case]:
        """Filter by source_file."""
        return [c for c in cases if c.source_file == source_file]

    def filter_by_llm_class(self, cases: list[Case], llm_class: str) -> list[Case]:
        """Filter by llm_class."""
        return [c for c in cases if c.ground_truth and c.ground_truth.llm_class == llm_class]

    def get_unique_sources(self, cases: list[Case]) -> list[str]:
        """Get all unique source_file values."""
        sources = set()
        for case in cases:
            if case.source_file:
                sources.add(case.source_file)
        return sorted(sources)

    def get_unique_llm_classes(self, cases: list[Case]) -> list[str]:
        """Get all unique llm_class values."""
        classes = set()
        for case in cases:
            if case.ground_truth and case.ground_truth.llm_class:
                classes.add(case.ground_truth.llm_class)
        return sorted(classes)
