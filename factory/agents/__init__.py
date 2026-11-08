"""L2 Agent 层：8 个协作角色与可插拔算法模板。"""

from factory.agents.roles import (
    REPAIR_STRATEGIES,
    Coder,
    Curator,
    Interpreter,
    Planner,
    Repairer,
    Retriever,
    Reviewer,
    Verifier,
)
from factory.agents.templates import list_templates, register, render

__all__ = [
    "REPAIR_STRATEGIES",
    "Coder",
    "Curator",
    "Interpreter",
    "Planner",
    "Repairer",
    "Retriever",
    "Reviewer",
    "Verifier",
    "list_templates",
    "register",
    "render",
]
