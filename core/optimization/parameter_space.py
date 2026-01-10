"""
Parameter Space Definition
Prompt #92: Define searchable parameter spaces for optimization

Defines the parameter search space for strategy optimization.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union
import random

logger = logging.getLogger("jarvis.optimization.parameter_space")


# =============================================================================
# MODELS
# =============================================================================

class ParameterType(Enum):
    """Type of parameter"""
    FLOAT = "float"
    INT = "int"
    CATEGORICAL = "categorical"
    BOOLEAN = "boolean"


@dataclass
class Parameter:
    """A single parameter definition"""
    name: str
    param_type: ParameterType
    low: Optional[float] = None
    high: Optional[float] = None
    choices: Optional[List[Any]] = None
    default: Optional[Any] = None
    step: Optional[float] = None  # For discrete steps
    log_scale: bool = False  # Use log scale for float params
    description: str = ""

    def validate(self) -> bool:
        """Validate parameter definition"""
        if self.param_type == ParameterType.FLOAT:
            return self.low is not None and self.high is not None and self.low < self.high
        elif self.param_type == ParameterType.INT:
            return self.low is not None and self.high is not None and self.low < self.high
        elif self.param_type == ParameterType.CATEGORICAL:
            return self.choices is not None and len(self.choices) > 0
        elif self.param_type == ParameterType.BOOLEAN:
            return True
        return False

    def sample(self) -> Any:
        """Sample a random value from this parameter's range"""
        if self.param_type == ParameterType.FLOAT:
            if self.log_scale:
                import math
                log_low = math.log(max(self.low, 1e-10))
                log_high = math.log(self.high)
                return math.exp(random.uniform(log_low, log_high))
            return random.uniform(self.low, self.high)

        elif self.param_type == ParameterType.INT:
            if self.step:
                steps = int((self.high - self.low) / self.step)
                return int(self.low + random.randint(0, steps) * self.step)
            return random.randint(int(self.low), int(self.high))

        elif self.param_type == ParameterType.CATEGORICAL:
            return random.choice(self.choices)

        elif self.param_type == ParameterType.BOOLEAN:
            return random.choice([True, False])

        return self.default


@dataclass
class ParameterSpace:
    """
    Defines the search space for strategy parameters.

    Supports:
    - Float parameters with optional log scaling
    - Integer parameters with optional step size
    - Categorical parameters
    - Boolean parameters
    - Conditional parameters
    """
    name: str
    parameters: List[Parameter] = field(default_factory=list)
    conditionals: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def add_float(
        self,
        name: str,
        low: float,
        high: float,
        default: float = None,
        log_scale: bool = False,
        description: str = "",
    ) -> "ParameterSpace":
        """Add a float parameter"""
        self.parameters.append(Parameter(
            name=name,
            param_type=ParameterType.FLOAT,
            low=low,
            high=high,
            default=default or (low + high) / 2,
            log_scale=log_scale,
            description=description,
        ))
        return self

    def add_int(
        self,
        name: str,
        low: int,
        high: int,
        default: int = None,
        step: int = None,
        description: str = "",
    ) -> "ParameterSpace":
        """Add an integer parameter"""
        self.parameters.append(Parameter(
            name=name,
            param_type=ParameterType.INT,
            low=low,
            high=high,
            default=default or (low + high) // 2,
            step=step,
            description=description,
        ))
        return self

    def add_categorical(
        self,
        name: str,
        choices: List[Any],
        default: Any = None,
        description: str = "",
    ) -> "ParameterSpace":
        """Add a categorical parameter"""
        self.parameters.append(Parameter(
            name=name,
            param_type=ParameterType.CATEGORICAL,
            choices=choices,
            default=default or choices[0],
            description=description,
        ))
        return self

    def add_bool(
        self,
        name: str,
        default: bool = False,
        description: str = "",
    ) -> "ParameterSpace":
        """Add a boolean parameter"""
        self.parameters.append(Parameter(
            name=name,
            param_type=ParameterType.BOOLEAN,
            default=default,
            description=description,
        ))
        return self

    def add_conditional(
        self,
        param_name: str,
        condition_param: str,
        condition_values: List[Any],
    ):
        """
        Add a conditional parameter relationship.

        The param_name will only be active when condition_param
        has one of the condition_values.
        """
        self.conditionals[param_name] = {
            "depends_on": condition_param,
            "values": condition_values,
        }

    def get_parameter(self, name: str) -> Optional[Parameter]:
        """Get a parameter by name"""
        for param in self.parameters:
            if param.name == name:
                return param
        return None

    def get_defaults(self) -> Dict[str, Any]:
        """Get default values for all parameters"""
        return {p.name: p.default for p in self.parameters}

    def sample(self) -> Dict[str, Any]:
        """Sample a random configuration"""
        config = {}

        for param in self.parameters:
            # Check if this parameter is conditional
            if param.name in self.conditionals:
                cond = self.conditionals[param.name]
                depends_on = cond["depends_on"]
                required_values = cond["values"]

                # Only include if condition is met
                if depends_on in config and config[depends_on] in required_values:
                    config[param.name] = param.sample()
            else:
                config[param.name] = param.sample()

        return config

    def validate(self) -> tuple[bool, List[str]]:
        """Validate the entire parameter space"""
        errors = []

        for param in self.parameters:
            if not param.validate():
                errors.append(f"Invalid parameter: {param.name}")

        # Check conditionals reference valid parameters
        param_names = {p.name for p in self.parameters}
        for cond_param, cond in self.conditionals.items():
            if cond_param not in param_names:
                errors.append(f"Conditional parameter not found: {cond_param}")
            if cond["depends_on"] not in param_names:
                errors.append(f"Condition depends on unknown parameter: {cond['depends_on']}")

        return len(errors) == 0, errors

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "name": self.name,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.param_type.value,
                    "low": p.low,
                    "high": p.high,
                    "choices": p.choices,
                    "default": p.default,
                    "step": p.step,
                    "log_scale": p.log_scale,
                    "description": p.description,
                }
                for p in self.parameters
            ],
            "conditionals": self.conditionals,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ParameterSpace":
        """Create from dictionary representation"""
        space = cls(name=data["name"])

        for p_data in data.get("parameters", []):
            param = Parameter(
                name=p_data["name"],
                param_type=ParameterType(p_data["type"]),
                low=p_data.get("low"),
                high=p_data.get("high"),
                choices=p_data.get("choices"),
                default=p_data.get("default"),
                step=p_data.get("step"),
                log_scale=p_data.get("log_scale", False),
                description=p_data.get("description", ""),
            )
            space.parameters.append(param)

        space.conditionals = data.get("conditionals", {})

        return space


# =============================================================================
# PREDEFINED SPACES
# =============================================================================

def get_dca_parameter_space() -> ParameterSpace:
    """Get parameter space for DCA strategy"""
    space = ParameterSpace(name="dca_strategy")

    space.add_float(
        name="interval_hours",
        low=1.0,
        high=168.0,  # 1 week
        default=24.0,
        description="Hours between DCA purchases",
    )

    space.add_float(
        name="amount_sol",
        low=0.01,
        high=10.0,
        default=0.1,
        description="SOL amount per DCA",
    )

    space.add_float(
        name="max_slippage",
        low=0.001,
        high=0.1,
        default=0.02,
        description="Maximum slippage tolerance",
    )

    space.add_bool(
        name="skip_volatile",
        default=True,
        description="Skip purchase during high volatility",
    )

    space.add_float(
        name="volatility_threshold",
        low=0.05,
        high=0.5,
        default=0.15,
        description="Volatility threshold to skip",
    )

    # volatility_threshold only matters if skip_volatile is True
    space.add_conditional("volatility_threshold", "skip_volatile", [True])

    return space


def get_mean_reversion_parameter_space() -> ParameterSpace:
    """Get parameter space for mean reversion strategy"""
    space = ParameterSpace(name="mean_reversion_strategy")

    space.add_int(
        name="lookback_periods",
        low=10,
        high=200,
        default=50,
        description="Number of periods for moving average",
    )

    space.add_float(
        name="entry_std_devs",
        low=1.0,
        high=4.0,
        default=2.0,
        description="Standard deviations for entry",
    )

    space.add_float(
        name="exit_std_devs",
        low=0.0,
        high=2.0,
        default=0.5,
        description="Standard deviations for exit",
    )

    space.add_float(
        name="position_size_pct",
        low=0.01,
        high=0.3,
        default=0.1,
        description="Position size as % of portfolio",
    )

    space.add_float(
        name="stop_loss_pct",
        low=0.01,
        high=0.2,
        default=0.05,
        description="Stop loss percentage",
    )

    space.add_float(
        name="take_profit_pct",
        low=0.02,
        high=0.5,
        default=0.1,
        description="Take profit percentage",
    )

    space.add_categorical(
        name="ma_type",
        choices=["sma", "ema", "wma"],
        default="sma",
        description="Moving average type",
    )

    return space


def get_momentum_parameter_space() -> ParameterSpace:
    """Get parameter space for momentum strategy"""
    space = ParameterSpace(name="momentum_strategy")

    space.add_int(
        name="fast_period",
        low=5,
        high=50,
        default=12,
        description="Fast moving average period",
    )

    space.add_int(
        name="slow_period",
        low=20,
        high=200,
        default=26,
        description="Slow moving average period",
    )

    space.add_int(
        name="signal_period",
        low=5,
        high=20,
        default=9,
        description="Signal line period",
    )

    space.add_float(
        name="rsi_oversold",
        low=20,
        high=40,
        default=30,
        description="RSI oversold level",
    )

    space.add_float(
        name="rsi_overbought",
        low=60,
        high=80,
        default=70,
        description="RSI overbought level",
    )

    space.add_float(
        name="min_volume_multiplier",
        low=1.0,
        high=5.0,
        default=1.5,
        description="Minimum volume vs average",
    )

    return space
