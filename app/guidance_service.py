from typing import Dict, Any, Optional, List
from app.classifier import classify_issue
from app.rag_engine import rag_engine
from app.llm_engine import llm_engine
from app.schemas import GuidanceResponse, RAGSourceItem


def get_ai_guidance(description: str, category: Optional[str] = None) -> GuidanceResponse:
    """
    Coordinates problem classification, RAG FAISS vector retrieval,
    and LLM synthesis to build verified civic guidance.
    """
    classification = classify_issue(description=description, selected_category=category)

    if not classification["is_clear"]:
        return GuidanceResponse(
            is_clear=False,
            clarity_message=classification["clarity_message"],
            identified_category=classification.get("identified_category"),
            classification_method=None,
            recommended_department=None,
            jurisdiction_notes=None,
            jurisdiction_disclaimer=classification["jurisdiction_disclaimer"],
            match_confidence=None,
            has_verified_guidance=False,
            verified_guidance_message=None,
            ai_analysis=None,
            llm_provider=None,
            estimated_turnaround=None,
            procedure_steps=[],
            required_evidence=[],
            sources=[]
        )

    cat = classification["identified_category"]
    dept = classification["recommended_department"]
    jurisdiction_notes = classification["jurisdiction_notes"]
    query_str = f"{cat}: {description}"

    # Query RAG engine for top 3 matching chunks in FAISS
    rag_results = rag_engine.query_guidelines(query=query_str, top_k=3, similarity_threshold=0.30)

    has_verified = len(rag_results) > 0
    source_items: List[RAGSourceItem] = []

    if has_verified:
        verified_msg = (
            f"Successfully retrieved {len(rag_results)} relevant section(s) from official government guidelines."
        )
        for r in rag_results:
            source_items.append(RAGSourceItem(
                document_title=r["document_title"],
                filename=r["filename"],
                page_number=r["page_number"],
                score=r["score"],
                excerpt=r["excerpt"]
            ))
    else:
        verified_msg = (
            "Verified government guideline document not available in knowledge base for this exact query. "
            "LLM is providing standard municipal protocol and evidence checklist."
        )

    # Invoke LLM with retrieved RAG context
    llm_output = llm_engine.generate_rag_guidance(
        query=description,
        category=cat,
        department=dept,
        rag_sources=rag_results,
        jurisdiction_notes=jurisdiction_notes
    )

    return GuidanceResponse(
        is_clear=True,
        clarity_message=None,
        identified_category=cat,
        classification_method=classification["classification_method"],
        recommended_department=dept,
        jurisdiction_notes=jurisdiction_notes,
        jurisdiction_disclaimer=classification["jurisdiction_disclaimer"],
        match_confidence=classification.get("match_confidence"),
        has_verified_guidance=has_verified,
        verified_guidance_message=verified_msg,
        ai_analysis=llm_output.get("ai_analysis"),
        llm_provider=llm_output.get("llm_provider"),
        estimated_turnaround=llm_output.get("estimated_turnaround"),
        procedure_steps=llm_output.get("procedure_steps", []),
        required_evidence=llm_output.get("required_evidence", []),
        sources=source_items
    )
