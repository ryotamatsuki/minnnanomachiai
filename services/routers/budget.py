"""
Budget Draft API router.
Generates evidence-backed budget proposals using Gemini.
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class BudgetRequest(BaseModel):
    prompt: str
    target_area: str = "東京都千代田区"
    period: str = ""
    budget_limit: str = ""
    purpose: str = ""


class BudgetResponse(BaseModel):
    success: bool
    request_id: str = ""
    proposals: list[dict] = []
    evidences: list[dict] = []
    hypotheses: list[str] = []
    job_log: list[dict] = []
    error: str = ""


@router.post("/generate", response_model=BudgetResponse)
async def generate_budget(req: BudgetRequest):
    """Generate a budget draft with A/B/C proposals."""
    try:
        from src.llm.budget_generator import generate_budget_draft
        from src.rag.retriever import search_documents, add_sample_documents, get_all_documents
        import dataclasses

        # Ensure sample docs exist
        if not get_all_documents():
            add_sample_documents()

        # Build full prompt
        full_prompt = req.prompt
        if req.target_area:
            full_prompt += f"\n対象地域: {req.target_area}"
        if req.period:
            full_prompt += f"\n期間: {req.period}"
        if req.budget_limit:
            full_prompt += f"\n予算上限: {req.budget_limit}"
        if req.purpose:
            full_prompt += f"\n目的: {req.purpose}"

        # RAG search
        rag_results = search_documents(req.prompt)

        # Generate
        result = generate_budget_draft(
            prompt=full_prompt,
            rag_results=rag_results,
        )

        return BudgetResponse(
            success=True,
            request_id=result.request_id,
            proposals=[dataclasses.asdict(p) for p in result.proposals],
            evidences=[dataclasses.asdict(e) for e in result.evidences],
            hypotheses=result.hypotheses,
            job_log=result.job_log,
        )

    except Exception as e:
        return BudgetResponse(success=False, error=str(e))


@router.get("/documents")
async def list_documents():
    """List all RAG documents."""
    from src.rag.retriever import get_all_documents
    return {"documents": get_all_documents()}
