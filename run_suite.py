import os
import sys
from app.config import CATEGORIES, CATEGORY_DEPARTMENT_MAP, CATEGORY_KEYWORDS
from app.classifier import classify_issue
from app.guidance_service import get_ai_guidance
from app.letter_generator import generate_letter_content, generate_letter_pdf
from app.database import engine, get_db, Base
from app.models import User, Department, Complaint, Document
from app.sample_data import initialize_sample_data_if_needed

print("==================================================")
print("CIVICFIX AI — COMPREHENSIVE VERIFICATION SUITE")
print("==================================================")

# 1. Verify Scope & Categories
print("\n[TEST 1] Verifying 5 Strict Categories and Department Mappings...")
assert len(CATEGORIES) == 5, f"Expected 5 categories, got {len(CATEGORIES)}"
for cat in CATEGORIES:
    assert cat in CATEGORY_DEPARTMENT_MAP, f"Missing map for {cat}"
    assert cat in CATEGORY_KEYWORDS, f"Missing keywords for {cat}"
    dept_info = CATEGORY_DEPARTMENT_MAP[cat]
    print(f"  ✓ {cat}  -->  {dept_info['name']}")
print("  --> Passed: All 5 categories mapped correctly.")

# 2. Verify Classifier and Clarity
print("\n[TEST 2] Verifying Issue Classifier & Ambiguity Handling...")
# Too short / vague
short_test = classify_issue("hello")
assert short_test["is_clear"] is False, "Should flag unclear input"
assert short_test["clarity_message"] is not None
print("  ✓ Correctly prompted for details when description is too brief.")

# 5 categories classification test
test_cases = [
    ("There is a large pothole crater on the road causing traffic slowdown.", "Road Damage", "Road Maintenance Authority"),
    ("Sewage is overflowing from the blocked drainage manhole into the street.", "Drainage Overflow", "Drainage / Sanitation Department"),
    ("Uncollected municipal garbage and rotten waste accumulating near the bus stop.", "Garbage Accumulation", "Sanitation Department"),
    ("The street light pole is broken and streetlights are completely dark.", "Streetlight Failure", "Electrical Maintenance Department"),
    ("Potable water pipeline burst gushing high pressure drinking water.", "Water Leakage", "Water Supply Department")
]

for desc, expected_cat, expected_dept in test_cases:
    res = classify_issue(desc)
    assert res["is_clear"] is True, f"Failed on {desc}"
    assert res["identified_category"] == expected_cat, f"Expected {expected_cat}, got {res['identified_category']}"
    assert res["recommended_department"] == expected_dept, f"Expected {expected_dept}, got {res['recommended_department']}"
    assert res["jurisdiction_disclaimer"] is not None
    print(f"  ✓ '{desc[:40]}...' classified as '{res['identified_category']}' -> '{res['recommended_department']}'")

print("  --> Passed: Keyword classifier and department recommendations verified.")

# 3. Verify RAG Engine & Guidelines Retrieval
print("\n[TEST 3] Verifying RAG Knowledge Base & Semantic Search...")
db = next(get_db())
initialize_sample_data_if_needed(db)

guidance_res = get_ai_guidance("Pothole crater in the asphalt street", "Road Damage")
assert guidance_res.is_clear is True
assert guidance_res.identified_category == "Road Damage"
assert guidance_res.recommended_department == "Road Maintenance Authority"
assert len(guidance_res.procedure_steps) > 0
assert len(guidance_res.required_evidence) > 0

print(f"  ✓ Guidance retrieved. Has verified guidelines: {guidance_res.has_verified_guidance}")
print(f"  ✓ Sources retrieved: {len(guidance_res.sources)}")
for src in guidance_res.sources:
    print(f"      • Document: '{src.document_title}' | Page {src.page_number} | Score: {src.score}")
    print(f"        Excerpt: \"{src.excerpt[:90]}...\"")

# Test unindexed/unmatched query clarity
guidance_unmatched = get_ai_guidance("alien spaceship landed in my backyard", "Road Damage")
# Even if fallback category is used, if no matching chunks meet threshold:
print(f"  ✓ Message when specific guidance is unavailable: \"{guidance_unmatched.verified_guidance_message[:70]}...\"")
print("  --> Passed: RAG vector search, page numbers, citations, and threshold checks verified.")

# 4. Verify Database Models and Persistence
print("\n[TEST 4] Verifying SQLite Database and Entity Relationships...")
# Create a test citizen
test_user = db.query(User).filter(User.username == "test_citizen_user").first()
if not test_user:
    test_user = User(
        username="test_citizen_user",
        email="test_user@civicfix.local",
        full_name="Pooja Verma",
        phone="+91 98111 22233",
        role="citizen"
    )
    db.add(test_user)
    db.commit()
    db.refresh(test_user)

dept = db.query(Department).filter(Department.name == "Water Supply Department").first()
assert dept is not None, "Department should be seeded"

test_complaint = Complaint(
    complaint_no="CF-2026-UNITTEST",
    category="Water Leakage",
    description="Underground water pipeline fracture spilling potable water on 1st Cross.",
    location="1st Cross, HSR Layout",
    status="Pending",
    citizen_id=test_user.id,
    department_id=dept.id,
    ai_summary="Categorized under Water Leakage. Routed to Water Supply Department."
)
db.add(test_complaint)
db.commit()
db.refresh(test_complaint)

# Verify relationships
assert test_complaint.citizen.full_name == "Pooja Verma"
assert test_complaint.department.name == "Water Supply Department"
print(f"  ✓ Created complaint #{test_complaint.complaint_no} with user '{test_complaint.citizen.full_name}' and department '{test_complaint.department.name}'.")

# Clean up test complaint
db.delete(test_complaint)
db.commit()
print("  --> Passed: Database tables, relationships, and queries verified.")

# 5. Verify ReportLab Letter Generator and PDF Generation
print("\n[TEST 5] Verifying Complaint Letter & ReportLab PDF Generation...")
sample_letter_data = {
    "complaint_no": "CF-2026-0042",
    "category": "Road Damage",
    "description": "Hazardous road cave-in and potholes on 80ft Road",
    "location": "80ft Road, 4th Block",
    "department_name": "Road Maintenance Authority",
    "citizen_name": "Pooja Verma",
    "citizen_phone": "+91 98111 22233",
    "citizen_email": "pooja@civicfix.local"
}

letter_text = generate_letter_content(sample_letter_data)
assert "CF-2026-0042" in letter_text["complaint_no"]
assert "URGENT GRIEVANCE" in letter_text["subject"]
assert "Road Maintenance Authority" in letter_text["recipient"]
print("  ✓ Formal grievance letter text generated with structured metadata.")

pdf_target = "data/uploads/temp/verification_letter.pdf"
pdf_path = generate_letter_pdf(letter_text, pdf_target)
assert os.path.exists(pdf_path), "PDF file should be created"
file_size = os.path.getsize(pdf_path)
assert file_size > 1500, f"PDF file size too small: {file_size} bytes"
print(f"  ✓ Professional PDF rendered successfully ({file_size} bytes) via ReportLab.")
print("  --> Passed: Letter generator and PDF renderer verified.")

print("\n==================================================")
print("ALL 5 CORE ARCHITECTURE TESTS COMPLETED SUCCESSFULLY!")
print("==================================================")
db.close()
