"""Built-in graph template registry and factory."""

from pydantic import BaseModel, Field

from miaos.executor import AgentGraphSpec


class GraphTemplate(BaseModel):
    """A reusable graph template bundled with MiaOS Builder."""

    template_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    category: str = Field(default="general", min_length=1)
    tags: list[str] = Field(default_factory=list)
    graph: AgentGraphSpec

    @property
    def node_count(self) -> int:
        """Return graph node count."""
        return len(self.graph.nodes)


def _template_payloads() -> list[dict[str, object]]:
    """Return raw built-in template payloads."""
    return [
        {
            "template_id": "mia-minimal",
            "name": "Mia Minimal",
            "description": "Planner -> Worker -> Approval baseline for supervised local runs.",
            "category": "getting_started",
            "tags": ["persona", "approval", "starter"],
            "graph": {
                "graph_id": "mia-minimal",
                "name": "Mia Minimal",
                "nodes": [
                    {"id": "START", "type": "input", "label": "Start"},
                    {
                        "id": "Planner",
                        "type": "llm",
                        "label": "Планировщик",
                        "config": {
                            "role": "planner",
                            "model": "qwen3.5-8b",
                            "prompt": "Break the user task into safe, reviewable steps.",
                        },
                    },
                    {
                        "id": "Worker",
                        "type": "llm",
                        "label": "Исполнитель",
                        "config": {
                            "role": "executor",
                            "model": "qwen3.5-coder-7b",
                            "prompt": "Execute the approved plan and produce the final answer.",
                        },
                    },
                    {
                        "id": "Approval",
                        "type": "approval",
                        "label": "Согласование",
                        "config": {"action_class": "publish"},
                    },
                    {"id": "END", "type": "output", "label": "End"},
                ],
                "edges": [
                    {"source": "START", "target": "Planner"},
                    {"source": "Planner", "target": "Worker"},
                    {"source": "Worker", "target": "Approval"},
                    {"source": "Approval", "target": "END"},
                ],
            },
        },
        {
            "template_id": "draft-with-tools",
            "name": "Draft With Tools",
            "description": "Planner -> sandbox web search -> draft tool -> approval.",
            "category": "tooling",
            "tags": ["tool", "sandbox", "approval"],
            "graph": {
                "graph_id": "draft-with-tools",
                "name": "Draft With Tools",
                "nodes": [
                    {"id": "START", "type": "input", "label": "Start"},
                    {
                        "id": "Planner",
                        "type": "llm",
                        "label": "Планировщик",
                        "config": {
                            "role": "planner",
                            "model": "qwen3.5-8b",
                            "prompt": "Plan the draft and decide what sandbox context is needed.",
                        },
                    },
                    {
                        "id": "Search",
                        "type": "tool",
                        "label": "Web search",
                        "config": {"tool_name": "web_search_mock"},
                    },
                    {
                        "id": "Draft",
                        "type": "tool",
                        "label": "Draft",
                        "config": {"tool_name": "create_draft"},
                    },
                    {
                        "id": "Approval",
                        "type": "approval",
                        "label": "Согласование",
                        "config": {"action_class": "publish"},
                    },
                    {"id": "END", "type": "output", "label": "End"},
                ],
                "edges": [
                    {"source": "START", "target": "Planner"},
                    {"source": "Planner", "target": "Search"},
                    {"source": "Search", "target": "Draft"},
                    {"source": "Draft", "target": "Approval"},
                    {"source": "Approval", "target": "END"},
                ],
            },
        },
        {
            "template_id": "chat-memory-loop",
            "name": "Chat Memory Loop",
            "description": (
                "Perception -> memory summarizer -> worker for persona chat experiments."
            ),
            "category": "memory",
            "tags": ["memory", "chat", "persona"],
            "graph": {
                "graph_id": "chat-memory-loop",
                "name": "Chat Memory Loop",
                "nodes": [
                    {"id": "START", "type": "input", "label": "Start"},
                    {
                        "id": "Perception",
                        "type": "llm",
                        "label": "Восприятие",
                        "config": {
                            "role": "perception",
                            "model": "qwen3.5-4b",
                            "prompt": "Extract the user's intent and important memory cues.",
                        },
                    },
                    {
                        "id": "Memory",
                        "type": "llm",
                        "label": "Память",
                        "config": {
                            "role": "memory",
                            "model": "qwen3.5-4b",
                            "prompt": "Summarize reusable profile facts and domain notes.",
                        },
                    },
                    {
                        "id": "Worker",
                        "type": "llm",
                        "label": "Исполнитель",
                        "config": {
                            "role": "executor",
                            "model": "qwen3.5-8b",
                            "prompt": "Answer using the persona context and memory summary.",
                        },
                    },
                    {"id": "END", "type": "output", "label": "End"},
                ],
                "edges": [
                    {"source": "START", "target": "Perception"},
                    {"source": "Perception", "target": "Memory"},
                    {"source": "Memory", "target": "Worker"},
                    {"source": "Worker", "target": "END"},
                ],
            },
        },
    ]


BUILTIN_TEMPLATES = [
    GraphTemplate.model_validate(payload)
    for payload in _template_payloads()
]


class TemplateNotFoundError(KeyError):
    """Raised when a template id is unknown."""


def list_templates() -> list[GraphTemplate]:
    """Return all built-in templates."""
    return BUILTIN_TEMPLATES


def get_template(template_id: str) -> GraphTemplate:
    """Return one built-in template."""
    for template in BUILTIN_TEMPLATES:
        if template.template_id == template_id:
            return template
    raise TemplateNotFoundError(template_id)


def instantiate_template(
    template_id: str,
    *,
    graph_id: str | None = None,
    name: str | None = None,
) -> AgentGraphSpec:
    """Create a graph spec from a template with optional id/name overrides."""
    template = get_template(template_id)
    graph = template.graph.model_copy(deep=True)
    if graph_id:
        graph.graph_id = graph_id
    if name:
        graph.name = name
    return AgentGraphSpec.model_validate(graph.model_dump(mode="json"))
