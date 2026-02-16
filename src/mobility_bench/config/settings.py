"""Unified configuration management."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv


@dataclass
class ModelConfig:
    """Model configuration."""

    name: str
    provider: str
    base_url: str = ""
    api_key: str = ""
    temperature: float = 0.1
    max_tokens: int = 8192
    timeout: int = 60
    roles: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, name: str, data: dict) -> "ModelConfig":
        return cls(
            name=name,
            provider=data.get("provider", "openai"),
            base_url=os.path.expandvars(data.get("base_url", "")),
            api_key=os.path.expandvars(data.get("api_key", "")),
            temperature=data.get("temperature", 0.1),
            max_tokens=data.get("max_tokens", 8192),
            timeout=data.get("timeout", 60),
            roles=data.get("roles", {}),
        )


@dataclass
class DatasetConfig:
    """Dataset configuration."""

    name: str
    path: str
    format: str = "excel"
    schema: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, name: str, data: dict) -> "DatasetConfig":
        return cls(
            name=name,
            path=data.get("path", ""),
            format=data.get("format", "excel"),
            schema=data.get("schema", {}),
        )


@dataclass
class EvaluationConfig:
    """Evaluation configuration."""

    metrics: list = field(default_factory=list)
    ground_truth: str = ""
    tool: dict = field(default_factory=dict)
    instruction: dict = field(default_factory=dict)
    planning: dict = field(default_factory=dict)
    answer: dict = field(default_factory=dict)
    efficiency: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "EvaluationConfig":
        return cls(
            metrics=data.get("metrics", ["tool", "instruction", "planning", "answer", "efficiency"]),
            ground_truth=data.get("ground_truth", ""),
            tool=data.get("tool", {}),
            instruction=data.get("instruction", {}),
            planning=data.get("planning", {}),
            answer=data.get("answer", {}),
            efficiency=data.get("efficiency", {}),
        )


@dataclass
class PlanAndExecuteConfig:
    """Plan-and-Execute 框架配置。"""

    max_plan_iterations: int = 10
    max_worker_retries: int = 3

    @classmethod
    def from_dict(cls, data: dict) -> "PlanAndExecuteConfig":
        return cls(
            max_plan_iterations=data.get("max_plan_iterations", 10),
            max_worker_retries=data.get("max_worker_retries", 3),
        )


@dataclass
class ReactConfig:
    """ReAct 框架配置。"""

    max_iterations: int = 15

    @classmethod
    def from_dict(cls, data: dict) -> "ReactConfig":
        return cls(
            max_iterations=data.get("max_iterations", 15),
        )


@dataclass
class AgentConfig:
    """Agent 配置。"""

    default_framework: str = "plan_and_execute"
    sandbox_data_dir: str = "data/sandbox"
    plan_and_execute: PlanAndExecuteConfig = field(default_factory=PlanAndExecuteConfig)
    react: ReactConfig = field(default_factory=ReactConfig)

    @classmethod
    def from_dict(cls, data: dict) -> "AgentConfig":
        pae_data = data.get("plan_and_execute", {})
        react_data = data.get("react", {})
        return cls(
            default_framework=data.get("default_framework", "plan_and_execute"),
            sandbox_data_dir=data.get("sandbox_data_dir", "data/sandbox"),
            plan_and_execute=PlanAndExecuteConfig.from_dict(pae_data),
            react=ReactConfig.from_dict(react_data),
        )


@dataclass
class Settings:
    """Global configuration management."""

    models: dict[str, ModelConfig] = field(default_factory=dict)
    datasets: dict[str, DatasetConfig] = field(default_factory=dict)
    evaluation: EvaluationConfig = field(default_factory=EvaluationConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    output_dir: str = "data/results"
    log_level: str = "INFO"

    _instance: Optional["Settings"] = None

    @classmethod
    def load(cls, config_path: Path | None = None) -> "Settings":
        """Load configuration.

        Priority: specified config file > environment variables > defaults
        """
        # Load .env
        load_dotenv()

        settings = cls()

        # Load default configuration
        settings._load_defaults()

        # Load configuration file
        if config_path:
            settings._load_from_file(config_path)
        else:
            # Try loading from default configs directory
            settings._load_from_configs_dir()

        # Override with environment variables
        settings._load_from_env()

        cls._instance = settings
        return settings

    @classmethod
    def get_instance(cls) -> "Settings":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls.load()
        return cls._instance

    def _load_defaults(self):
        """Load default configuration."""
        # Default evaluation configuration
        self.evaluation = EvaluationConfig(
            metrics=["tool", "instruction", "planning", "answer", "efficiency"],
            tool={
                "check_min": {
                    "query_poi": ["keywords"],
                    "driving_route": ["origin", "destination"],
                    "walking_route": ["origin", "destination"],
                    "bicycling_route": ["origin", "destination"],
                    "bus_route": ["origin", "destination"],
                    "weather_query": ["city"],
                    "reverse_geocoding": ["longitude", "latitude"],
                    "search_around_poi": ["location", "keywords"],
                    "traffic_status": ["name", "city"],
                },
                "check_max": {
                    "query_poi": ["keywords", "city"],
                    "driving_route": ["origin", "destination", "waypoints", "strategy"],
                    "bicycling_route": ["origin", "destination"],
                    "walking_route": ["origin", "destination"],
                    "bus_route": ["origin", "destination", "strategy"],
                    "weather_query": ["city", "need_forecast"],
                    "reverse_geocoding": ["longitude", "latitude", "radius"],
                    "search_around_poi": ["location", "keywords", "radius"],
                    "traffic_status": ["name", "city"],
                },
            },
            instruction={"similarity_threshold": 0.7},
            planning={"alpha": 0.8, "beta": 0.2},
        )

    def _load_from_file(self, path: Path):
        """Load from configuration file."""
        if not path.exists():
            return

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        self._apply_config(data)

    def _load_from_configs_dir(self):
        """Load configuration from configs directory."""
        configs_dir = Path("configs")
        if not configs_dir.exists():
            return

        # Load model configurations
        models_dir = configs_dir / "models"
        if models_dir.exists():
            for f in models_dir.glob("*.yaml"):
                with open(f) as fp:
                    data = yaml.safe_load(fp) or {}
                    if "models" in data:
                        for name, cfg in data["models"].items():
                            self.models[name] = ModelConfig.from_dict(name, cfg)

        # Load dataset configurations
        datasets_dir = configs_dir / "datasets"
        if datasets_dir.exists():
            for f in datasets_dir.glob("*.yaml"):
                with open(f) as fp:
                    data = yaml.safe_load(fp) or {}
                    if "dataset" in data:
                        cfg = data["dataset"]
                        name = cfg.get("name", f.stem)
                        self.datasets[name] = DatasetConfig.from_dict(name, cfg)

        # Load evaluation configuration
        eval_config = configs_dir / "evaluation" / "default.yaml"
        if eval_config.exists():
            with open(eval_config) as f:
                data = yaml.safe_load(f) or {}
                if "evaluation" in data:
                    self.evaluation = EvaluationConfig.from_dict(data["evaluation"])

        # Load agent configuration
        agent_config = configs_dir / "agent" / "default.yaml"
        if agent_config.exists():
            with open(agent_config) as f:
                data = yaml.safe_load(f) or {}
                if "agent" in data:
                    self.agent = AgentConfig.from_dict(data["agent"])

    def _load_from_env(self):
        """Load from environment variables."""
        # LLM configuration
        base_url = os.getenv("LLM_BASE_URL", "")
        api_key = os.getenv("LLM_API_KEY", "")

        # Update default values for all models
        for model in self.models.values():
            if not model.base_url:
                model.base_url = base_url
            if not model.api_key:
                model.api_key = api_key

        # Log level
        self.log_level = os.getenv("LOG_LEVEL", "INFO")

    def _apply_config(self, data: dict):
        """Apply configuration data."""
        # Run configuration
        if "run" in data:
            run_cfg = data["run"]
            if "output_dir" in run_cfg or "dir" in data.get("output", {}):
                self.output_dir = run_cfg.get("output_dir") or data.get("output", {}).get("dir", self.output_dir)

        # Sandbox data directory
        if "sandbox_data_dir" in data:
            self.agent.sandbox_data_dir = data["sandbox_data_dir"]

        # Agent configuration
        if "agent" in data:
            self.agent = AgentConfig.from_dict(data["agent"])

        # Model configuration
        if "models" in data:
            for name, cfg in data["models"].items():
                self.models[name] = ModelConfig.from_dict(name, cfg)

        # Dataset configuration
        if "datasets" in data:
            for name, cfg in data["datasets"].items():
                self.datasets[name] = DatasetConfig.from_dict(name, cfg)

        # Evaluation configuration
        if "evaluation" in data:
            self.evaluation = EvaluationConfig.from_dict(data["evaluation"])

    def get_model(self, name: str) -> ModelConfig | None:
        """Get model configuration."""
        return self.models.get(name)

    def get_dataset(self, name: str) -> DatasetConfig | None:
        """Get dataset configuration."""
        return self.datasets.get(name)

    def validate(self) -> list[str]:
        """Validate configuration, return list of errors."""
        errors = []

        # Validate model configuration
        for name, model in self.models.items():
            if not model.base_url:
                errors.append(f"Model {name} missing base_url")
            if not model.api_key:
                errors.append(f"Model {name} missing api_key")

        # Validate dataset configuration
        for name, dataset in self.datasets.items():
            if not dataset.path:
                errors.append(f"Dataset {name} missing path")
            elif not Path(dataset.path).exists():
                errors.append(f"Dataset {name} path does not exist: {dataset.path}")

        return errors

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "models": {name: vars(cfg) for name, cfg in self.models.items()},
            "datasets": {name: vars(cfg) for name, cfg in self.datasets.items()},
            "evaluation": vars(self.evaluation),
            "agent": {
                "default_framework": self.agent.default_framework,
                "sandbox_data_dir": self.agent.sandbox_data_dir,
                "plan_and_execute": vars(self.agent.plan_and_execute),
                "react": vars(self.agent.react),
            },
            "output_dir": self.output_dir,
            "log_level": self.log_level,
        }
