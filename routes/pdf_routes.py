# ============================================
# routes/pdf_routes.py
# مسارات توليد وتحميل تقارير PDF
# ============================================

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import os

from services.pdf_service import pdf_service

router = APIRouter(prefix="/pdf")


@router.get("/student/{student_id}")
async def generate_student_pdf(student_id: int):
    """
    توليد وتحميل تقرير PDF للطالب
    """
    try:
        filepath = pdf_service.generate_student_report(student_id)
        
        if not os.path.exists(filepath):
            raise HTTPException(status_code=500, detail="فشل في إنشاء التقرير")
        
        filename = os.path.basename(filepath)
        
        return FileResponse(
            path=filepath,
            filename=filename,
            media_type='application/pdf'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/teacher/{teacher_id}")
async def generate_teacher_pdf(teacher_id: int):
    """
    توليد وتحميل تقرير PDF للمدرس
    """
    try:
        filepath = pdf_service.generate_teacher_report(teacher_id)
        
        if not os.path.exists(filepath):
            raise HTTPException(status_code=500, detail="فشل في إنشاء التقرير")
        
        filename = os.path.basename(filepath)
        
        return FileResponse(
            path=filepath,
            filename=filename,
            media_type='application/pdf'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/receipt/{installment_id}")
async def generate_receipt_pdf(installment_id: int):
    """
    توليد وتحميل وصل دفع PDF
    """
    try:
        filepath = pdf_service.generate_receipt(installment_id)
        
        if not os.path.exists(filepath):
            raise HTTPException(status_code=500, detail="فشل في إنشاء الوصل")
        
        filename = os.path.basename(filepath)
        
        return FileResponse(
            path=filepath,
            filename=filename,
            media_type='application/pdf'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))