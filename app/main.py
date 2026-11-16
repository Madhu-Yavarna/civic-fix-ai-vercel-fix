import os
import shutil
import uuid
from datetime import datetime
from typing import Optional, List
from pathlib import Path

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Form,
    status
)
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.config import (
    BASE_DIR,
    UPLOADS_DIR,
    GUIDELINES_DIR,
    COMPLAINT_IMAGES_DIR,
    CATEGORY_DEPARTMENT_MAP,
    CATEGORIES,
    JURISDICTION_DISCLAIMER
)
from app.database import engine, get_db, Base
from app.models import User, Department, Complaint, Document
from app.schemas import (
    GuidanceRequest,
    GuidanceResponse,
    ComplaintResponse,
    StatusUpdateRequest,
    LLMConfigPayload
)
from app.guidance_service import get_ai_guidance
from app.rag_engine import rag_engine
from app.llm_engine import llm_engine, save_llm_config, get_llm_config, LLMUnavailableError
from app.letter_generator import generate_letter_pdf
from app.sample_data import initialize_sample_data_if_needed

# Create DB tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="CivicFix AI",
    description="Smart Public Grievance Guidance System with LLM & RAG",
    version="2.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static and Uploads mounts
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")


@app.on_event("startup")
def startup_event():
    """Initializes tables, default departments, demo users, and sample RAG guidelines in FAISS."""
    db = next(get_db())
    try:
        initialize_sample_data_if_needed(db)
    finally:
        db.close()


@app.get("/", response_class=HTMLResponse)
def read_root():
    """Serves the main application SPA HTML."""
    index_path = BASE_DIR / "templates" / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend template not found")
    with open(index_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


# ==========================================
# LLM CONFIGURATION APIS
# ==========================================

@app.get("/api/llm/status")
def get_llm_status():
    """Returns the active LLM provider."""
    return {
        "active_provider": llm_engine.get_active_provider(),
        "config": get_llm_config()
    }


@app.post("/api/llm/config")
def update_llm_config(payload: LLMConfigPayload):
    """Allows setting an optional API key (Gemini, Groq, OpenAI) or switching to Local."""
    save_llm_config(provider=payload.provider, api_key=payload.api_key or "")
    return {
        "status": "success",
        "active_provider": llm_engine.get_active_provider(),
        "message": f"Switched LLM provider to {llm_engine.get_active_provider()}"
    }


# ==========================================
# CITIZEN DASHBOARD APIS (LLM + RAG)
# ==========================================

@app.post("/api/guidance", response_model=GuidanceResponse)
def analyze_and_guide(req: GuidanceRequest):
    """
    RAG-powered AI Guidance:
    - Identifies problem category via keyword matching with fallback.
    - Recommends responsible department with jurisdiction disclaimer.
    - Retrieves top-3 relevant guideline chunks via FAISS vector search.
    - Generates grounded guidance and procedural steps using the LLM engine.
    - Asks for clarification if problem description is unclear.
    """
    return get_ai_guidance(description=req.description, category=req.category)


@app.post("/api/complaints")
def create_complaint(
    category: str = Form(...),
    description: str = Form(...),
    location: str = Form(...),
    citizen_name: str = Form("Concerned Citizen"),
    citizen_email: str = Form("citizen@civicfix.local"),
    citizen_phone: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """
    Submits a citizen complaint:
    - Stores optional image proof.
    - Assigns unique complaint reference number (CF-2026-XXXX).
    - Matches responsible department.
    """
    if category not in CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category '{category}'. Must be one of: {', '.join(CATEGORIES)}"
        )

    # Save image if provided
    image_rel_path = None
    if image and image.filename:
        ext = os.path.splitext(image.filename)[1].lower()
        if ext in [".jpg", ".jpeg", ".png", ".webp"]:
            saved_name = f"proof_{uuid.uuid4().hex[:10]}{ext}"
            target_path = COMPLAINT_IMAGES_DIR / saved_name
            with open(target_path, "wb") as buffer:
                shutil.copyfileobj(image.file, buffer)
            image_rel_path = f"/uploads/complaints/{saved_name}"

    # Find or create user
    user = db.query(User).filter(User.email == citizen_email).first()
    if not user:
        user = User(
            username=f"citizen_{uuid.uuid4().hex[:6]}",
            email=citizen_email,
            full_name=citizen_name,
            phone=citizen_phone,
            role="citizen"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # Map department
    dept_info = CATEGORY_DEPARTMENT_MAP.get(category, {})
    dept = db.query(Department).filter(Department.name == dept_info.get("name")).first()
    dept_name = dept.name if dept else dept_info.get("name", "Municipal Authority")

    # Generate collision-safe sequential complaint number
    max_id = db.query(func.max(Complaint.id)).scalar() or 0
    next_num = max_id + 1
    year = datetime.utcnow().year
    complaint_no = f"CF-{year}-{next_num:04d}"
    while db.query(Complaint).filter(Complaint.complaint_no == complaint_no).first():
        next_num += 1
        complaint_no = f"CF-{year}-{next_num:04d}"

    # Generate RAG + LLM summary for the complaint
    try:
        rag_hits = rag_engine.query_guidelines(f"{category}: {description}", top_k=1, similarity_threshold=0.30)
        llm_res = llm_engine.generate_rag_guidance(
            query=description,
            category=category,
            department=dept_name,
            rag_sources=rag_hits,
            jurisdiction_notes=dept_info.get("jurisdiction", "")
        )
        ai_summary = llm_res.get("ai_analysis") or f"Categorized under {category}. Routed to {dept_name}."
    except Exception:
        ai_summary = f"Categorized under {category}. Routed to {dept_name}."

    complaint = Complaint(
        complaint_no=complaint_no,
        category=category,
        description=description,
        location=location,
        image_path=image_rel_path,
        status="Pending",
        citizen_id=user.id,
        department_id=dept.id if dept else None,
        ai_summary=ai_summary
    )
    db.add(complaint)
    db.commit()
    db.refresh(complaint)

    return {
        "status": "success",
        "message": "Complaint submitted successfully.",
        "complaint_id": complaint.id,
        "complaint_no": complaint.complaint_no,
        "category": complaint.category,
        "status_value": complaint.status,
        "department_name": dept_name
    }


@app.get("/api/complaints")
def list_complaints(db: Session = Depends(get_db)):
    """Retrieves all complaints for citizen listing."""
    complaints = db.query(Complaint).order_by(desc(Complaint.created_at)).all()
    results = []
    for c in complaints:
        results.append({
            "id": c.id,
            "complaint_no": c.complaint_no,
            "category": c.category,
            "description": c.description,
            "location": c.location,
            "image_path": c.image_path,
            "status": c.status,
            "ai_summary": c.ai_summary,
            "citizen_name": c.citizen.full_name if c.citizen else "Concerned Citizen",
            "citizen_email": c.citizen.email if c.citizen else "citizen@civicfix.local",
            "citizen_phone": c.citizen.phone if c.citizen else None,
            "department_name": c.department.name if c.department else "Municipal Authority",
            "created_at": c.created_at.strftime("%Y-%m-%d %H:%M"),
            "updated_at": c.updated_at.strftime("%Y-%m-%d %H:%M") if c.updated_at else None
        })
    return results


@app.get("/api/complaints/{complaint_id}")
def get_complaint(complaint_id: int, db: Session = Depends(get_db)):
    """Retrieves details of a single complaint."""
    c = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return {
        "id": c.id,
        "complaint_no": c.complaint_no,
        "category": c.category,
        "description": c.description,
        "location": c.location,
        "image_path": c.image_path,
        "status": c.status,
        "ai_summary": c.ai_summary,
        "citizen_name": c.citizen.full_name if c.citizen else "Concerned Citizen",
        "citizen_email": c.citizen.email if c.citizen else "citizen@civicfix.local",
        "citizen_phone": c.citizen.phone if c.citizen else None,
        "department_name": c.department.name if c.department else "Municipal Authority",
        "created_at": c.created_at.strftime("%Y-%m-%d %H:%M"),
        "updated_at": c.updated_at.strftime("%Y-%m-%d %H:%M") if c.updated_at else None
    }


@app.delete("/api/complaints/{complaint_id}")
def delete_complaint(complaint_id: int, db: Session = Depends(get_db)):
    """Deletes a complaint."""
    c = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Complaint not found")
    
    # Remove image if exists
    if c.image_path:
        img_rel = c.image_path.lstrip("/uploads/")
        img_full = UPLOADS_DIR / img_rel
        if img_full.exists():
            try:
                os.remove(img_full)
            except Exception:
                pass

    db.delete(c)
    db.commit()
    return {"status": "success", "message": f"Complaint {c.complaint_no} deleted successfully."}


@app.get("/api/complaints/{complaint_id}/letter-preview")
def get_letter_preview(complaint_id: int, db: Session = Depends(get_db)):
    """
    Generates complaint letter text pre-filled with complaint details
    and augmented by LLM + RAG guidelines for in-browser editing.
    """
    c = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Complaint not found")

    complaint_dict = {
        "complaint_no": c.complaint_no,
        "category": c.category,
        "description": c.description,
        "location": c.location,
        "department_name": c.department.name if c.department else "Municipal Authority",
        "citizen_name": c.citizen.full_name if c.citizen else "Concerned Citizen",
        "citizen_email": c.citizen.email if c.citizen else "",
        "citizen_phone": c.citizen.phone if c.citizen else ""
    }

    # Retrieve relevant RAG guidelines to enrich letter content
    rag_sources = rag_engine.query_guidelines(
        query=f"{c.category}: {c.description}",
        top_k=2,
        similarity_threshold=0.30
    )

    try:
        letter_data = llm_engine.generate_complaint_letter(complaint_dict, rag_sources)
    except LLMUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return letter_data


@app.post("/api/complaints/download-letter-pdf")
def download_letter_pdf(
    complaint_no: str = Form(...),
    subject: str = Form(...),
    recipient: str = Form(...),
    body: str = Form(...),
    date: str = Form(datetime.now().strftime("%B %d, %Y"))
):
    """
    Renders the edited letter data as a professional PDF using ReportLab
    and streams it for direct browser download.
    """
    filename = f"Grievance_Letter_{complaint_no}.pdf"
    output_path = str(UPLOADS_DIR / "temp" / filename)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    letter_data = {
        "complaint_no": complaint_no,
        "subject": subject,
        "recipient": recipient,
        "body": body,
        "date": date
    }

    generate_letter_pdf(letter_data, output_path)

    return FileResponse(
        path=output_path,
        media_type="application/pdf",
        filename=filename
    )
