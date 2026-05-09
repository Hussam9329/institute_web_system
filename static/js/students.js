// ============================================
// students.js - JavaScript لإدارة الطلاب
// ============================================

// ===== متغيرات عامة =====
let linkTeacherModal, installmentsListModal;

document.addEventListener('DOMContentLoaded', function() {
    // تهيئة Modals
    const linkModalEl = document.getElementById('linkTeacherModal');
    const instListModalEl = document.getElementById('installmentsListModal');
    
    if (linkModalEl) linkTeacherModal = new bootstrap.Modal(linkModalEl);
    if (instListModalEl) installmentsListModal = new bootstrap.Modal(instListModalEl);
    
    // معالجة أحداث الأزرار عبر data-action (بدون XSS)
    document.addEventListener('click', function(e) {
        const btn = e.target.closest('[data-action]');
        if (!btn) return;
        const action = btn.dataset.action;
        if (action === 'unlink-teacher') {
            const studentId = parseInt(btn.dataset.studentId);
            const teacherId = parseInt(btn.dataset.teacherId);
            const teacherName = btn.dataset.teacherName || '';
            
            if (isNaN(studentId) || isNaN(teacherId)) {
                showAlert('بيانات الربط غير صحيحة', 'error');
                return;
            }
            
            unlinkTeacher(studentId, teacherId, teacherName);
        }
    });
});

// ===== وظائف ربط المدرسين =====

/**
 * فتح نموذج ربط المدرس
 */
function openLinkTeacherModal() {
    // إعادة تعيين الاختيار
    clearLinkTeacher();
    // إعادة تحميل البطاقات
    if (typeof loadTeachersForLink === 'function') {
        loadTeachersForLink();
    }
    linkTeacherModal.show();
}

/**
 * ربط طالب بمدرس
 */
async function linkStudentTeacher(event) {
    event.preventDefault();
    
    const studentId = document.getElementById('link_student_id').value;
    const teacherId = document.getElementById('link_teacher_id').value;
    
    if (!teacherId) {
        showAlert('يرجى اختيار مدرس', 'warning');
        return;
    }

    const studyType = document.getElementById('link_study_type').value;
    const status = document.getElementById('link_status').value;

    try {
        const result = await apiRequest('/api/link-student-teacher', {
            method: 'POST',
            body: JSON.stringify({
                student_id: parseInt(studentId),
                teacher_id: parseInt(teacherId),
                study_type: studyType,
                status: status
            })
        });

        if (result.success) {
            showAlert(result.message, 'success');
            linkTeacherModal.hide();
            // إعادة تحميل الصفحة بعد ثانيتين
            location.reload();
        } else {
            showAlert(result.message, 'warning');
        }
    } catch (error) {
        showAlert(error.message, 'error');
    }
}

/**
 * إلغاء ربط طالب بمدرس
 */
async function unlinkTeacher(studentId, teacherId, teacherName) {
    const message = `هل أنت متأكد من إلغاء ربط المدرس "${teacherName}"؟\n\nملاحظة: لا يمكن إلغاء الربط إذا وُجدت أقساط مسجلة بين الطالب والمدرس.`;
    
    if (!confirmAction(message)) return;

    try {
        const result = await apiRequest(`/api/unlink-student-teacher/${studentId}/${teacherId}`, {
            method: 'DELETE'
        });

        if (result.success) {
            showAlert(result.message, 'success');
            location.reload();
        } else {
            showAlert(result.message, 'error');
        }
    } catch (error) {
        showAlert(error.message, 'error');
    }
}

// ===== وظائف الأقساط =====


/**
 * عرض تفاصيل الأقساط
 */
async function viewInstallments(studentId, teacherId) {
    try {
        const result = await apiRequest(`/api/installments/student/${studentId}/teacher/${teacherId}`);
        
        // فحص هل المستخدم مدير عام لإظهار زر الحذف
        let isAdmin = false;
        try {
            const userInfo = document.querySelector('[data-user-role]');
            if (userInfo && userInfo.dataset.userRole === 'مدير عام') {
                isAdmin = true;
            }
        } catch(e) {}
        
        let html = `
            <h6 class="mb-3">إجمالي المدفوع: <strong class="text-success">${formatCurrency(result.total_paid)}</strong></h6>
            <div class="table-responsive">
                <table class="table table-sm table-bordered">
                    <thead class="table-light">
                        <tr>
                            <th>#</th>
                            <th>المبلغ</th>
                            <th>التاريخ</th>
                            <th>النوع</th>
                            <th>ملاحظات</th>
                            <th>إجراءات</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        if (result.data && result.data.length > 0) {
            result.data.forEach((inst, index) => {
                html += `
                    <tr>
                        <td>${index + 1}</td>
                        <td class="fw-bold">${formatCurrency(inst.amount)}</td>
                        <td>${formatDate(inst.payment_date)}</td>
                        <td><span class="badge bg-info">${inst.installment_type}</span></td>
                        <td>${inst.notes || '-'}</td>
                        <td>
                            <div class="btn-group btn-group-xs">
                                <a href="/reports/receipt/${inst.id}" target="_blank" class="btn btn-outline-success btn-xs" title="طباعة الوصل">
                                    <i class="fas fa-print"></i>
                                </a>
                                ${isAdmin ? `<button class="btn btn-outline-danger btn-xs" onclick="deleteInstallment(${inst.id})" title="حذف (مدير فقط)">
                                    <i class="fas fa-trash"></i>
                                </button>` : ''}
                            </div>
                        </td>
                    </tr>
                `;
            });
        } else {
            html += '<tr><td colspan="6" class="text-center text-muted">لا توجد أقساط</td></tr>';
        }

        html += '</tbody></table></div>';
        
        document.getElementById('installmentsListContent').innerHTML = html;
        installmentsListModal.show();
        
    } catch (error) {
        showAlert(error.message, 'error');
    }
}

/**
 * حذف قسط
 */
async function deleteInstallment(installmentId) {
    if (!confirmAction('هل أنت متأكد من حذف هذا القسط؟')) return;

    try {
        const result = await apiRequest(`/api/installments/${installmentId}`, {
            method: 'DELETE'
        });

        if (result.success) {
            showAlert(result.message, 'success');
            // إعادة تحميل القائمة
            const studentId = document.getElementById('inst_student_id').value;
            const teacherId = document.getElementById('inst_teacher_id').value;
            viewInstallments(studentId, teacherId);
        } else {
            showAlert(result.message, 'error');
        }
    } catch (error) {
        showAlert(error.message, 'error');
    }
}
