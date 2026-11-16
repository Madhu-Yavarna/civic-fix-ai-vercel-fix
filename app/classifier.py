import re
from typing import Dict, Any, Optional
from app.config import (
    CATEGORIES,
    CATEGORY_KEYWORDS,
    CATEGORY_DEPARTMENT_MAP,
    JURISDICTION_DISCLAIMER
)


def classify_issue(description: str, selected_category: Optional[str] = None) -> Dict[str, Any]:
    """
    Classifies a civic problem using keyword matching with user selection as fallback.
    Validates clarity and produces department recommendations with jurisdiction disclaimers.
    """
    cleaned_desc = (description or "").strip()
    words = re.findall(r'\b[a-zA-Z]{2,}\b', cleaned_desc)

    # 1. Clarity check: if fewer than 3 meaningful words or description is empty
    if len(cleaned_desc) < 10 or len(words) < 3:
        return {
            "is_clear": False,
            "clarity_message": "The problem description is too brief or unclear. Please provide more details (e.g., what happened, visible symptoms, or nearby landmarks) so CivicFix AI can accurately guide you.",
            "identified_category": selected_category if selected_category in CATEGORIES else None,
            "recommended_department": None,
            "jurisdiction_notes": None,
            "jurisdiction_disclaimer": JURISDICTION_DISCLAIMER
        }

    lower_desc = cleaned_desc.lower()
    scores: Dict[str, int] = {cat: 0 for cat in CATEGORIES}

    # Count keyword matches for each category
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            # Word boundary matching where appropriate
            if " " in kw:
                if kw in lower_desc:
                    scores[cat] += 2
            else:
                if re.search(rf"\b{re.escape(kw)}\b", lower_desc):
                    scores[cat] += 1

    best_category = None
    max_score = 0
    for cat, score in scores.items():
        if score > max_score:
            max_score = score
            best_category = cat

    # Classification logic
    if max_score > 0 and best_category:
        identified_category = best_category
        method = "keyword_analysis"
    elif selected_category and selected_category in CATEGORIES:
        identified_category = selected_category
        method = "category_selection_fallback"
    else:
        # Ambiguous and no valid selection
        return {
            "is_clear": False,
            "clarity_message": "We could not determine the specific civic problem from your description. Please select a category from the dropdown or include specific details like road condition, water leak, drain blockage, garbage, or streetlights.",
            "identified_category": None,
            "recommended_department": None,
            "jurisdiction_notes": None,
            "jurisdiction_disclaimer": JURISDICTION_DISCLAIMER
        }

    dept_info = CATEGORY_DEPARTMENT_MAP.get(
        identified_category,
        {"name": "Local Municipal Authority", "jurisdiction": "General civic grievance grievance jurisdiction."}
    )

    return {
        "is_clear": True,
        "clarity_message": None,
        "identified_category": identified_category,
        "classification_method": method,
        "recommended_department": dept_info["name"],
        "jurisdiction_notes": dept_info["jurisdiction"],
        "jurisdiction_disclaimer": JURISDICTION_DISCLAIMER,
        "match_confidence": "High (Keyword match)" if method == "keyword_analysis" else "Moderate (Citizen category selection)"
    }
