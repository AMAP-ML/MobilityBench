"""Tool call evaluation metric."""

from collections import Counter

from mobility_bench.evaluation.base import BaseMetric, MetricResult


class ToolCallMetric(BaseMetric):
    """Tool call evaluation metric.

    Evaluation dimensions:
    - tool_selection_coverage: Tool selection coverage rate
    - tool_selection_redundancy: Tool selection redundancy rate
    - schema_compliance_rate: Schema compliance rate
    - schema_extra_field_penalty: Extra field penalty
    - parameter_filling_accuracy: Parameter filling accuracy
    """

    name = "tool"
    description = "Tool call evaluation"

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.check_min = config.get("check_min", {}) if config else {}
        self.check_max = config.get("check_max", {}) if config else {}
        self.defaults = config.get("defaults", {}) if config else {}

        # Tool name mapping
        self.tool_name_map = {
            "traffic_status_road_api": "traffic_status",
        }

    def compute(
        self,
        case_id: str,
        prediction: dict,
        ground_truth: dict,
    ) -> MetricResult:
        """Compute single evaluation result."""
        actual_calls = prediction.get("tool_calls", [])
        expected_tools = ground_truth.get("tool_list", [])

        if not expected_tools:
            return MetricResult(
                case_id=case_id,
                metric_name=self.name,
                score=1.0,
                details={"source_file": ground_truth.get("source_file", "")},
            )

        # Map tool names
        for tool in expected_tools:
            if "name" in tool and tool["name"] in self.tool_name_map:
                tool["name"] = self.tool_name_map[tool["name"]]

        metrics = self._evaluate_tool_calls(actual_calls, expected_tools)

        # Calculate composite score
        coverage = metrics["tool_selection"]["coverage"]
        redundancy = metrics["tool_selection"]["redundancy"]
        schema_score = metrics["schema"]["all_score"]
        param_score = metrics["parameter_filling"]

        # Composite score = (coverage * 0.3 + (1-redundancy) * 0.1 + schema * 0.3 + param * 0.3)
        score = (
            coverage * 0.3
            + (1 - redundancy) * 0.1
            + schema_score * 0.3
            + param_score * 0.3
        )

        return MetricResult(
            case_id=case_id,
            metric_name=self.name,
            score=score,
            details={
                "source_file": ground_truth.get("source_file", ""),
                "tool_selection_coverage": coverage,
                "tool_selection_redundancy": redundancy,
                "schema_compliance_rate": metrics["schema"]["compliance_rate"],
                "schema_extra_field_penalty": metrics["schema"]["extra_field_penalty"],
                "schema_all_score": schema_score,
                "parameter_filling_accuracy": param_score,
            },
        )

    def _evaluate_tool_calls(
        self,
        actual_calls: list,
        expected_tools: list,
    ) -> dict:
        """Evaluate tool calls."""
        # Extract tool names
        gt_names = [t.get("name", "") for t in expected_tools]
        act_names = [a.get("tool_name", a.get("name", "")) for a in actual_calls]

        gt_counts = Counter(gt_names)
        act_counts = Counter(act_names)

        # Tool selection coverage
        unique_gt = set(gt_names)
        unique_act = set(act_names)
        coverage = len(unique_gt & unique_act) / len(unique_gt) if unique_gt else 0

        # Tool selection redundancy
        useful_calls_count = 0
        for name, count in act_counts.items():
            useful_calls_count += min(count, gt_counts.get(name, 0))

        redundancy = (len(actual_calls) - useful_calls_count) / len(actual_calls) if actual_calls else 0

        # Parameter evaluation
        compliance_scores = []
        extra_field_scores = []
        param_filling_scores = []
        schema_all_scores = []

        temp_gt_by_name = {name: [t for t in expected_tools if t.get("name") == name] for name in unique_gt}

        for act in actual_calls:
            name = act.get("tool_name", act.get("name", ""))
            error_type = act.get("error_type")
            schema_valid = 0.0 if error_type == "Input parameter error" else 1.0

            if name in temp_gt_by_name and temp_gt_by_name[name]:
                exp = temp_gt_by_name[name].pop(0)

                defaults = self.defaults.get(name, {})
                act_args = act.get("arguments", act.get("tool_args", {}))
                if isinstance(act_args, str):
                    try:
                        import json
                        act_args = json.loads(act_args)
                    except Exception:
                        act_args = {}

                exp_args = exp.get("arguments", {})
                act_keys = set(act_args.keys()) if isinstance(act_args, dict) else set()

                min_keys = set(self.check_min.get(name, []))
                max_keys = set(self.check_max.get(name, []))

                # Schema compliance
                missing_keys = min_keys - act_keys
                base_c_score = (len(min_keys) - len(missing_keys)) / len(min_keys) if min_keys else 1.0
                c_score = base_c_score * schema_valid
                compliance_scores.append(c_score)

                # Extra fields
                extra_keys = act_keys - max_keys
                f_score = 0.0 if len(extra_keys) > 0 else 1.0
                extra_field_scores.append(f_score)

                schema_all_scores.append(c_score * f_score)

                # Parameter value accuracy
                act_args_filled = {**defaults, **act_args} if isinstance(act_args, dict) else defaults
                exp_args_filled = {**defaults, **exp_args}
                keys_to_compare = min_keys & set(exp_args_filled.keys())

                correct_val_count = 0
                for k in keys_to_compare:
                    if self._normalize_value(act_args_filled.get(k)) == self._normalize_value(exp_args_filled.get(k)):
                        correct_val_count += 1

                p_score = correct_val_count / len(keys_to_compare) if keys_to_compare else 1.0
                param_filling_scores.append(p_score)

        return {
            "tool_selection": {
                "coverage": round(coverage, 4),
                "redundancy": round(redundancy, 4),
            },
            "schema": {
                "compliance_rate": round(sum(compliance_scores) / len(compliance_scores), 4) if compliance_scores else 0,
                "extra_field_penalty": round(sum(extra_field_scores) / len(extra_field_scores), 4) if extra_field_scores else 0,
                "all_score": round(sum(schema_all_scores) / len(schema_all_scores), 4) if schema_all_scores else 0,
            },
            "parameter_filling": round(sum(param_filling_scores) / len(param_filling_scores), 4) if param_filling_scores else 0,
        }

    def _normalize_value(self, val):
        """Normalize value for comparison."""
        if isinstance(val, list):
            return sorted(str(v) for v in val)
        elif isinstance(val, (int, float)):
            return round(float(val), 6)
        else:
            return str(val).strip().lower() if isinstance(val, str) else str(val)
