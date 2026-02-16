"""Dataset schema definitions."""

from dataclasses import dataclass, field


@dataclass
class GroundTruth:
    """Ground truth data."""

    tool_list: list[dict] = field(default_factory=list)
    llm_class: str = ""
    route_ans: str | None = None
    weather_description: str | None = None
    poi_result: dict | None = None
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "GroundTruth":
        return cls(
            tool_list=data.get("tool_list", []),
            llm_class=data.get("llm_class", ""),
            route_ans=data.get("route_ans"),
            weather_description=data.get("weather_description"),
            poi_result=data.get("poi_result"),
            extra={k: v for k, v in data.items() if k not in [
                "tool_list", "llm_class", "route_ans",
                "weather_description", "poi_result"
            ]},
        )


@dataclass
class Case:
    """Test case."""

    case_id: str
    query: str
    context: str = ""
    source_file: str = ""
    task_scenario: str = ""
    intent_family: str = ""
    ground_truth: GroundTruth | None = None
    metadata: dict = field(default_factory=dict)

    # Fields that belong to Case directly (not metadata)
    _CASE_FIELDS = {
        "case_id", "Case ID", "query", "user_query", "context",
        "source_file", "task_scenario", "intent_family",
    }

    @classmethod
    def from_dict(cls, data: dict) -> "Case":
        # Extract ground truth related fields
        gt_fields = ["tool_list", "llm_class", "route_ans",
                     "weather_description", "poi_result"]
        gt_data = {k: data.get(k) for k in gt_fields if k in data}

        return cls(
            case_id=str(data.get("case_id", data.get("Case ID", ""))),
            query=data.get("query", data.get("user_query", "")),
            context=data.get("context", ""),
            source_file=data.get("source_file", ""),
            task_scenario=data.get("task_scenario", ""),
            intent_family=data.get("intent_family", ""),
            ground_truth=GroundTruth.from_dict(gt_data) if gt_data else None,
            metadata={k: v for k, v in data.items() if k not in (
                cls._CASE_FIELDS | set(gt_fields)
            )},
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        result = {
            "case_id": self.case_id,
            "query": self.query,
            "context": self.context,
            "source_file": self.source_file,
            "task_scenario": self.task_scenario,
            "intent_family": self.intent_family,
        }
        if self.ground_truth:
            result.update({
                "tool_list": self.ground_truth.tool_list,
                "llm_class": self.ground_truth.llm_class,
            })
        result.update(self.metadata)
        return result


@dataclass
class RunResult:
    """Run result."""

    case_id: str
    model_name: str
    planner_output: dict = field(default_factory=dict)
    worker_output: list = field(default_factory=list)
    reporter_output: str = ""
    token_usage: dict = field(default_factory=dict)
    execution_time: float = 0.0
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "model_name": self.model_name,
            "planner_output": self.planner_output,
            "worker_output": self.worker_output,
            "reporter_output": self.reporter_output,
            "token_usage": self.token_usage,
            "execution_time": self.execution_time,
            "error": self.error,
        }
