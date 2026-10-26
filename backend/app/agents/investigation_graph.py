"""LangGraph workflow for project issue investigations and approvals."""

import json
import os
import sqlite3
from typing import TypedDict
from uuid import UUID, uuid4

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, RetryPolicy, interrupt
from pydantic import ValidationError

from app.db.database import DATABASE_PATH, get_connection
from app.agents.investigation_agent import run_project_investigation_agent
from app.agents.roles import plan_document_search, review_retrieved_evidence
from app.agents.tools import create_project_search_tool
from app.rag.vector_store import get_vector_search_min_score
from app.schemas.agent import EvidenceReview, InvestigationPlan
from app.schemas.document import RetrievedChunk
from app.schemas.question import (
    ApprovalDecision,
    IssueInvestigationRequest,
    ProjectAnswerResponse,
    StructuredProjectAnswer,
)


class InvestigationState(TypedDict, total=False):
    """Shared data passed between the investigation workflow's roles."""

    project_id: str
    title: str
    description: str
    plan: InvestigationPlan
    retrieved_chunks: list[RetrievedChunk]
    review: EvidenceReview
    prepared_answer: tuple[StructuredProjectAnswer, str] | None
    response: ProjectAnswerResponse
    workflow_id: str
    approval_status: str
    action_plan_id: str | None

class InvestigationWorkflowNotPendingError(Exception):
    """Raised when a caller tries to resume a workflow with no pending approval."""


def _build_investigation_graph(
    project_id: UUID,
    issue_traceback: str | None,
):
    """Build the workflow; traceback is used at runtime and is not checkpointed."""
    from app.services.qa_service import _answer_with_chunks

    def planner(state: InvestigationState) -> dict[str, object]:
        plan = plan_document_search(
            state["title"],
            state["description"],
            issue_traceback,
        )
        return {"plan": plan}
    def local_researcher(state: InvestigationState) -> dict[str, object]:
        search_tool = create_project_search_tool(project_id)
        result = json.loads(search_tool.invoke({"query": state["plan"].search_query}))
        chunks = [
            RetrievedChunk(
                document_id=item["document_id"],
                filename=item["filename"],
                chunk_index=item["chunk_index"],
                content=item["content"],
                score=item["score"],
            )
            for item in result["results"]
        ]
        return {"retrieved_chunks": chunks, "prepared_answer": None}

    def model_researcher(state: InvestigationState) -> dict[str, object]:
        plan = state["plan"]
        model_question = (
            f"{plan.question}\nPlanner search phrase: {plan.search_query}"
        )
        if issue_traceback:
            model_question += f"\nTraceback:\n{issue_traceback.strip()}"
        answer, chunks, model = run_project_investigation_agent(
            project_id,
            model_question,
        )
        prepared = (answer, model) if answer is not None else None
        return {"retrieved_chunks": chunks, "prepared_answer": prepared}
    def choose_researcher(state: InvestigationState) -> str:
        del state
        if os.getenv("LLM_MODE", "mock").strip().lower() == "openai":
            return "model_researcher"
        return "local_researcher"

    def reviewer(state: InvestigationState) -> dict[str, object]:
        review = review_retrieved_evidence(
            state.get("retrieved_chunks", []),
            get_vector_search_min_score(),
        )
        return {"review": review}
    def save_report(state: InvestigationState) -> dict[str, object]:
        review = state["review"]
        response = _answer_with_chunks(
            project_id,
            state["plan"].question,
            review.accepted_chunks,
            history_question=f"{state['title']}\n{state['description']}",
            prepared_answer=(
                state.get("prepared_answer") if review.passed else None
            ),
        )
        response.workflow_id = UUID(state["workflow_id"])
        response.planner_query = state["plan"].search_query
        return {"response": response}
    def wait_for_approval(state: InvestigationState) -> dict[str, object]:
        structured = state["response"].structured_answer
        suggestions = structured.suggested_next_steps if structured else []
        decision_payload = interrupt(
            {
                "kind": "save_action_plan",
                "project_id": state["project_id"],
                "workflow_id": state["workflow_id"],
                "title": state["title"],
                "proposed_actions": suggestions,
                "message": (
                    "Approve to save these suggested steps as a project action plan. "
                    "Reject to finish without saving a plan."
                ),
            }
        )
        try:
            decision = ApprovalDecision.model_validate(decision_payload)
        except ValidationError as exc:
            raise ValueError("Approval decision must include a boolean 'approved'.") from exc

        action_plan_id = None
        approval_status = "rejected"
        if decision.approved:
            action_plan_id = str(uuid4())
            with get_connection() as connection:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO project_action_plans
                        (id, project_id, workflow_id, title, actions_json)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        action_plan_id,
                        str(project_id),
                        state["workflow_id"],
                        state["title"],
                        json.dumps(suggestions),
                    ),
                )
                saved_plan = connection.execute(
                    "SELECT id FROM project_action_plans WHERE workflow_id = ?",
                    (state["workflow_id"],),
                ).fetchone()
                action_plan_id = saved_plan["id"]
            approval_status = "approved"

        response = state["response"].model_copy(
            update={
                "approval_status": approval_status,
                "action_plan_id": action_plan_id,
            }
        )
        return {
            "approval_status": approval_status,
            "action_plan_id": action_plan_id,
            "response": response,
        }

    builder = StateGraph(InvestigationState)
    builder.add_node("planner", planner)
    builder.add_node(
        "local_researcher",
        local_researcher,
        retry_policy=RetryPolicy(
            max_attempts=2,
            initial_interval=0.1,
            backoff_factor=2.0,
            max_interval=0.5,
            jitter=False,
            retry_on=sqlite3.OperationalError,
        ),
    )
    builder.add_node("model_researcher", model_researcher)
    builder.add_node("reviewer", reviewer)
    builder.add_node("save_report", save_report)
    builder.add_node("wait_for_approval", wait_for_approval)
    builder.add_edge(START, "planner")
    builder.add_conditional_edges(
        "planner",
        choose_researcher,
        {
            "local_researcher": "local_researcher",
            "model_researcher": "model_researcher",
        },
    )
    builder.add_edge("local_researcher", "reviewer")
    builder.add_edge("model_researcher", "reviewer")
    builder.add_edge("reviewer", "save_report")
    builder.add_edge("save_report", "wait_for_approval")
    builder.add_edge("wait_for_approval", END)
    return builder.compile


def run_investigation_graph(
    project_id: UUID,
    issue: IssueInvestigationRequest,
) -> ProjectAnswerResponse:
    """Run planner, researcher, reviewer, then wait for human approval."""
    workflow_id = uuid4()
    graph_builder = _build_investigation_graph(project_id, issue.traceback)
    checkpoint_path = DATABASE_PATH.with_name("langgraph_checkpoints.db")
    config = {"configurable": {"thread_id": str(workflow_id)}}
    initial_state = {
        "project_id": str(project_id),
        "title": issue.title,
        "description": issue.description,
        "workflow_id": str(workflow_id),
    }
    with SqliteSaver.from_conn_string(str(checkpoint_path)) as checkpointer:
        graph = graph_builder(checkpointer=checkpointer)
        result = graph.invoke(initial_state, config=config)
        snapshot = graph.get_state(config)
        values = snapshot.values or result
    if str(values.get("project_id")) != str(project_id):
        raise InvestigationWorkflowNotPendingError
    response = values["response"]
    response.workflow_id = workflow_id
    if snapshot.next:
        response.approval_status = "pending"
        with get_connection() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO pending_investigations
                    (workflow_id, project_id, title, response_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    str(workflow_id),
                    str(project_id),
                    issue.title,
                    response.model_dump_json(),
                ),
            )
    return response


def resume_investigation_approval(
    project_id: UUID,
    workflow_id: UUID,
    approved: bool,
) -> ProjectAnswerResponse:
    """Resume only a matching workflow that is currently waiting for approval."""
    graph_builder = _build_investigation_graph(project_id, issue_traceback=None)
    checkpoint_path = DATABASE_PATH.with_name("langgraph_checkpoints.db")
    config = {"configurable": {"thread_id": str(workflow_id)}}
    with SqliteSaver.from_conn_string(str(checkpoint_path)) as checkpointer:
        graph = graph_builder(checkpointer=checkpointer)
        snapshot = graph.get_state(config)
        values = snapshot.values or {}
        if (
            str(values.get("project_id")) != str(project_id)
            or "wait_for_approval" not in snapshot.next
        ):
            raise InvestigationWorkflowNotPendingError
        result = graph.invoke(
            Command(resume={"approved": approved}),
            config=config,
        )
        response = result["response"]
    response.workflow_id = workflow_id
    with get_connection() as connection:
        connection.execute(
            "DELETE FROM pending_investigations WHERE workflow_id = ? AND project_id = ?",
            (str(workflow_id), str(project_id)),
        )
    return response
