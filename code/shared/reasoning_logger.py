"""
Structured trace logging for agent pipelines.

Each tool records compact step metadata that can be printed in the terminal and
serialized to the UI for auditability during local runs.
"""

import time
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field, asdict
import json


@dataclass
class ReasoningStep:
    """One recorded pipeline step."""
    step_number: int
    title: str
    description: str
    input_data: Optional[str] = None
    output_data: Optional[str] = None
    duration_ms: Optional[float] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    step_type: str = "processing"  # processing, retrieval, decision, generation, tool_call

    def to_dict(self) -> dict:
        return asdict(self)


class ReasoningLogger:
    """Capture ordered pipeline activity for terminal logs and UI trace panels."""

    def __init__(self, task_name: str):
        self.task_name = task_name
        self.steps: list[ReasoningStep] = []
        self.start_time = time.time()
        self._current_step_start: Optional[float] = None

    def start_step(self, title: str, description: str, step_type: str = "processing", input_data: Optional[str] = None):
        """Start a trace step."""
        self._current_step_start = time.time()
        step = ReasoningStep(
            step_number=len(self.steps) + 1,
            title=title,
            description=description,
            input_data=input_data,
            step_type=step_type,
        )
        self.steps.append(step)
        self._print_step_start(step)
        return step

    def end_step(self, output_data: Optional[str] = None):
        """Finish the active trace step."""
        if self.steps and self._current_step_start:
            step = self.steps[-1]
            step.duration_ms = round((time.time() - self._current_step_start) * 1000, 2)
            step.output_data = output_data
            self._print_step_end(step)
            self._current_step_start = None

    def get_all_steps(self) -> list[dict]:
        """Return all trace steps as JSON-serializable dictionaries."""
        return [step.to_dict() for step in self.steps]

    def get_summary(self) -> dict:
        """Return a compact trace summary."""
        total_time = round((time.time() - self.start_time) * 1000, 2)
        return {
            "task_name": self.task_name,
            "total_steps": len(self.steps),
            "total_duration_ms": total_time,
            "steps": self.get_all_steps(),
        }

    def _print_step_start(self, step: ReasoningStep):
        """Emit the start of a trace step to stdout."""
        icons = {
            "processing": "⚙️",
            "retrieval": "🔍",
            "decision": "🧠",
            "generation": "✍️",
            "tool_call": "🔧",
        }
        icon = icons.get(step.step_type, "▶️")
        print(f"\n{'='*60}")
        print(f"{icon}  STEP {step.step_number}: {step.title}")
        print(f"{'='*60}")
        print(f"   {step.description}")
        if step.input_data:
            preview = step.input_data[:200] + "..." if len(step.input_data) > 200 else step.input_data
            print(f"   📥 Input: {preview}")

    def _print_step_end(self, step: ReasoningStep):
        """Emit the completion of a trace step to stdout."""
        if step.output_data:
            preview = step.output_data[:300] + "..." if len(step.output_data) > 300 else step.output_data
            print(f"   📤 Output: {preview}")
        print(f"   ⏱️  Completed in {step.duration_ms}ms")

    def to_json(self) -> str:
        """Serialize the full trace summary."""
        return json.dumps(self.get_summary(), indent=2, default=str)
