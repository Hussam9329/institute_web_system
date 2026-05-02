// ============================================
// students.js - JavaScript لإدارة الطلاب
// ============================================

// ===== متغيرات عامة =====
let linkTeacherModal, installmentModal, installmentsListModal;

document.addEventListener('DOMContentLoaded', function() {
    // تهيئة Modals
    linkTeacherModal = new bootstrap.Modal(document.getElementById('linkTeacherModal'));
    installmentModal = new bootstrap.Modal(document.getElementById('installmentModal'));
    installmentsListModal = new bootstrap.Modal(document.getElementById('installmentsListModal'));
    
    // تحميل قائمة المدرسين عند فتح modal الربط
    loadTeachersList();

    // معالجة أحداث الأزرار عبر data-action (بدون XSS)
    document.addEventListener('click', function(e) {
        const btn = e.target.closest('[data-action]');
        if (!btn) return;
        const action = btn.dataset.action;
        if (action === 'pay-installment') {
            openInstallmentModal(
                parseInt(btn.dataset.studentId),
                parseInt(btn.dataset.teacherId),
                btn.dataset.teacherName,
                btn.dataset.studyType,
                parseInt(btn.dataset.totalFee)
            );
        } else if (action === 'unlink-teacher') {
            unlinkTeacher(
                parseInt(btn.dataset.studentId),
                parseInt(btn.dataset.teacherId),
                btn.dataset.teacherName
            );
        }
    });
});

// ===== وظائف ربط المدرسين =====

/**
 * فتح نموذج ربط المدرس
 */
function openLinkTeacherModal() {
    loadTeachersList();
    linkTeacherModal.show();
}

/**
 * تحميل قائمة المدرسين
 */
async function loadTeachersList() {
    try {
        const response = await apiRequest('/api/teachers');
        populateSelect('link_teacher_id', response.data, 'id', 'name');
    } catch (error) {
        showAlert('خطأ في تحميل قائمة المدرسين', 'error');
    }
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
    const message = `هل أنت متأكد من إلغاء ربط المدرس "${teacherName}"؟\n\n⚠️ سيتم حذف جميع الأقساط المسجلة لهذا المدرس!`;
    
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
 * فتح نموذج إضافة قسط
 */
function openInstallmentModal(studentId, teacherId, teacherName, studyType, totalFee) {
    document.getElementById('inst_student_id').value = studentId;
    document.getElementById('inst_teacher_id').value = teacherId;
    document.getElementById('inst_teacher_name').textContent = teacherName;
    document.getElementById('inst_amount').value = '';
    document.getElementById('inst_date').value = getTodayDate();
    document.getElementById('inst_type').selectedIndex = 0;
    document.getElementById('inst_notes').value = '';

    // عرض قسط الاستاد حسب نوع الدراسة
    const hintEl = document.getElementById('inst_fee_hint');
    const hintText = document.getElementById('inst_fee_hint_text');
    if (totalFee && totalFee > 0 && studyType) {
        const formatted = formatCurrency(totalFee);
        hintText.textContent = `قسط الاستاد ${teacherName} (${studyType}) = ${formatted}`;
        hintEl.classList.remove('d-none');
    } else {
        hintEl.classList.add('d-none');
    }

    installmentModal.show();
}

/**
 * إضافة قسط جديد
 */
async function addInstallment(event) {
    event.preventDefault();
    
    const data = {
        student_id: parseInt(document.getElementById('inst_student_id').value),
        teacher_id: parseInt(document.getElementById('inst_teacher_id').value),
        amount: toFullAmount(document.getElementById('inst_amount').value),
        payment_date: document.getElementById('inst_date').value,
        installment_type: document.getElementById('inst_type').value,
        notes: document.getElementById('inst_notes').value
    };

    // التحقق من البيانات
    if (!data.amount || data.amount <= 0) {
        showAlert('يرجى إدخال مبلغ صحيح', 'warning');
        return;
    }

    try {
        const result = await apiRequest('/api/installments', {
            method: 'POST',
            body: JSON.stringify(data)
        });

        if (result.success) {
            showAlert(result.message, 'success');
            installmentModal.hide();
            location.reload();
        } else {
            showAlert(result.message, 'error');
        }
    } catch (error) {
        showAlert(error.message, 'error');
    }
}

/**
 * عرض تفاصيل الأقساط
 */
async function viewInstallments(studentId, teacherId) {
    try {
        const result = await apiRequest(`/api/installments/student/${studentId}/teacher/${teacherId}`);
        
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
                                <a href="/pdf/receipt/${inst.id}" target="_blank" class="btn btn-outline-danger btn-xs" title="طباعة الوصل">
                                    <i class="fas fa-print"></i>
                                </a>
                                <button class="btn btn-outline-danger btn-xs" onclick="deleteInstallment(${inst.id})" title="حذف">
                                    <i class="fas fa-trash"></i>
                                </button>
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
