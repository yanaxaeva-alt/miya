"""AgentGraph schema and validation helpers."""

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class NodeType(StrEnum):
    """Node types supported by the AgentGraph MVP."""

    INPUT = "input"
    LLM = "llm"
    CRITIC = "critic"
    APPROVAL = "approval"
    OUTPUT = "output"
    TOOL = "tool"


class NodeSpec(BaseModel):
    """A graph node specification."""

    id: str = Field(min_length=1)
    type: NodeType
    label: str | None = None
    config: dict[str, str | int | bool] = Field(default_factory=dict)


class EdgeSpec(BaseModel):
    """A directed graph edge specification."""

    source: str = Field(min_length=1)
    target: str = Field(min_length=1)


class AgentGraphSpec(BaseModel):
    """A minimal DAG graph specification for MAS execution."""

    graph_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    nodes: list[NodeSpec]
    edges: list[EdgeSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_graph(self) -> "AgentGraphSpec":
        """Validate node ids, edge endpoints, and required node types."""
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            msg = "graph node ids must be unique"
            raise ValueError(msg)

        node_id_set = set(node_ids)
        for edge in self.edges:
            if edge.source not in node_id_set or edge.target not in node_id_set:
                msg = f"edge references unknown node: {edge.source}->{edge.target}"
                raise ValueError(msg)

        node_types = {node.type for node in self.nodes}
        if NodeType.INPUT not in node_types:
            msg = "graph must contain an input node"
            raise ValueError(msg)
        if NodeType.OUTPUT not in node_types:
            msg = "graph must contain an output node"
            raise ValueError(msg)

        topological_order(self)
        return self

    def node_by_id(self, node_id: str) -> NodeSpec:
        """Return a node by id."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        msg = f"unknown node id: {node_id}"
        raise ValueError(msg)


def topological_order(spec: AgentGraphSpec) -> list[str]:
    """Return a topological order or raise if the graph contains a cycle."""
    node_ids = {node.id for node in spec.nodes}
    incoming = dict.fromkeys(node_ids, 0)
    outgoing: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    for edge in spec.edges:
        outgoing[edge.source].append(edge.target)
        incoming[edge.target] += 1

    ready = sorted(node_id for node_id, count in incoming.items() if count == 0)
    order: list[str] = []
    while ready:
        node_id = ready.pop(0)
        order.append(node_id)
        for target in outgoing[node_id]:
            incoming[target] -= 1
            if incoming[target] == 0:
                ready.append(target)
                ready.sort()

    if len(order) != len(node_ids):
        msg = "graph must be acyclic"
        raise ValueError(msg)
    return order
