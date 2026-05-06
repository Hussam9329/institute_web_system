# ============================================
# routes/pdf_routes.py
# مسارات توليد وتحميل تقارير PDF
# ============================================

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
import os

from services.pdf_service import pdf_service
from auth import check_permission

router = APIRouter(prefix="/pdf")


@router.get("/student/{student_id}")
async def generate_student_pdf(request: Request, student_id: int):
    """
    توليد وتحميل تقرير PDF للطالب
    """
    check_permission(request, 'print_reports')
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
async def generate_teacher_pdf(request: Request, teacher_id: int):
    """
    توليد وتحميل تقرير PDF للمدرس
    """
    check_permission(request, 'print_reports')
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
async def generate_receipt_pdf(request: Request, installment_id: int):
    """
    توليد وتحميل وصل دفع PDF
    """
    check_permission(request, 'print_receipt')
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


@router.get("/subject/{subject_name}")
async def generate_subject_pdf(request: Request, subject_name: str):
    """توليد تقرير PDF لمادة معينة"""
    check_permission(request, 'print_reports')
    try:
        filepath = pdf_service.generate_subject_report(subject_name)
        if not os.path.exists(filepath):
            raise HTTPException(status_code=500, detail="فشل في إنشاء التقرير")
        filename = os.path.basename(filepath)
        return FileResponse(path=filepath, filename=filename, media_type='application/pdf')
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/subjects/all")
async def generate_all_subjects_pdf(request: Request):
    """توليد تقرير PDF شامل لجميع المواد"""
    check_permission(request, 'print_reports')
    try:
        filepath = pdf_service.generate_all_subjects_report()
        if not os.path.exists(filepath):
            raise HTTPException(status_code=500, detail="فشل في إنشاء التقرير")
        filename = os.path.basename(filepath)
        return FileResponse(path=filepath, filename=filename, media_type='application/pdf')
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))