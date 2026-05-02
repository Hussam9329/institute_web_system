// ============================================
// students.js - JavaScript لإدارة الطلاب
// ============================================

// ===== متغيرات عامة =====
let linkTeacherModal, installmentModal, installmentsListModal;

document.addEventListener('DOMContentLoaded', function() {
    // تهيئة Modals
    const linkModalEl = document.getElementById('linkTeacherModal');
    const instModalEl = document.getElementById('installmentModal');
    const instListModalEl = document.getElementById('installmentsListModal');
    
    if (linkModalEl) linkTeacherModal = new bootstrap.Modal(linkModalEl);
    if (instModalEl) installmentModal = new bootstrap.Modal(instModalEl);
    if (instListModalEl) installmentsListModal = new bootstrap.Modal(instListModalEl);
    
    // تحميل قائمة المدرسين عند فتح modal الربط
    loadTeachersList();

    // معالجة أحداث الأزرار عبر data-action (بدون XSS)
    document.addEventListener('click', function(e) {
        const btn = e.target.closest('[data-action]');
        if (!btn) return;
        const action = btn.dataset.action;
        if (action === 'pay-installment') {
            const studentId = parseInt(btn.dataset.studentId);
            const teacherId = parseInt(btn.dataset.teacherId);
            const teacherName = btn.dataset.teacherName || '';
            const studyType = btn.dataset.studyType || 'حضوري';
            const totalFee = parseInt(btn.dataset.totalFee) || 0;
            
            if (isNaN(studentId) || isNaN(teacherId)) {
                showAlert('بيانات القسط غير صحيحة', 'error');
                return;
            }
            
            openInstallmentModal(studentId, teacherId, teacherName, studyType, totalFee);
        } else if (action === 'unlink-teacher') {
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
    const elStudentId = document.getElementById('inst_student_id');
    const elTeacherId = document.getElementById('inst_teacher_id');
    const elTeacherName = document.getElementById('inst_teacher_name');
    const elAmount = document.getElementById('inst_amount');
    const elDate = document.getElementById('inst_date');
    const elType = document.getElementById('inst_type');
    const elNotes = document.getElementById('inst_notes');
    const elStudyType = document.getElementById('inst_study_type');
    
    if (!elStudentId || !elTeacherId) {
        showAlert('خطأ: عناصر النموذج غير موجودة', 'error');
        return;
    }
    
    elStudentId.value = studentId;
    elTeacherId.value = teacherId;
    if (elTeacherName) elTeacherName.textContent = teacherName;
    if (elAmount) elAmount.value = '';
    if (elDate) elDate.value = getTodayDate();
    if (elType) elType.selectedIndex = 0;
    if (elNotes) elNotes.value = '';

    // تعيين نوع الدراسة تلقائياً
    if (elStudyType) {
        for (let i = 0; i < elStudyType.options.length; i++) {
            if (elStudyType.options[i].value === studyType) {
                elStudyType.selectedIndex = i;
                break;
            }
        }
    }

    // عرض قسط الاستاد حسب نوع الدراسة
    const hintEl = document.getElementById('inst_fee_hint');
    const hintText = document.getElementById('inst_fee_hint_text');
    if (hintEl && hintText && totalFee && totalFee > 0 && studyType) {
        const formatted = formatCurrency(totalFee);
        hintText.textContent = `قسط الاستاد ${teacherName} (${studyType}) = ${formatted}`;
        hintEl.classList.remove('d-none');
    } else if (hintEl) {
        hintEl.classList.add('d-none');
    }

    if (installmentModal) {
        installmentModal.show();
    } else {
        showAlert('خطأ في فتح نموذج القسط', 'error');
    }
}

/**
 * إضافة قسط جديد
 */
async function addInstallment(event) {
    event.preventDefault();
    
    const studentIdEl = document.getElementById('inst_student_id');
    const teacherIdEl = document.getElementById('inst_teacher_id');
    const amountEl = document.getElementById('inst_amount');
    const dateEl = document.getElementById('inst_date');
    const typeEl = document.getElementById('inst_type');
    const studyTypeEl = document.getElementById('inst_study_type');
    const notesEl = document.getElementById('inst_notes');
    
    if (!studentIdEl || !teacherIdEl || !amountEl || !dateEl) {
        showAlert('خطأ: عناصر النموذج غير موجودة', 'error');
        return;
    }
    
    const data = {
        student_id: parseInt(studentIdEl.value),
        teacher_id: parseInt(teacherIdEl.value),
        amount: toFullAmount(amountEl.value),
        payment_date: dateEl.value,
        installment_type: typeEl ? typeEl.value : 'القسط الأول',
        study_type: studyTypeEl ? studyTypeEl.value : 'حضوري',
        notes: notesEl ? notesEl.value : ''
    };

    // التحقق من البيانات
    if (!data.student_id || isNaN(data.student_id)) {
        showAlert('بيانات الطالب غير صحيحة', 'warning');
        return;
    }
    
    if (!data.teacher_id || isNaN(data.teacher_id)) {
        showAlert('بيانات المدرس غير صحيحة', 'warning');
        return;
    }
    
    if (!data.amount || data.amount <= 0) {
        showAlert('يرجى إدخال مبلغ صحيح', 'warning');
        return;
    }
    
    if (!data.payment_date) {
        showAlert('يرجى تحديد تاريخ الدفع', 'warning');
        return;
    }

    // تعطيل الزر أثناء المعالجة
    const submitBtn = event.target.querySelector('button[type="submit"]');
    const originalText = submitBtn ? submitBtn.innerHTML : '';
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>جاري الحفظ...';
    }

    try {
        const result = await apiRequest('/api/installments', {
            method: 'POST',
            body: JSON.stringify(data)
        });

        if (result.success) {
            showAlert(result.message, 'success');
            if (installmentModal) installmentModal.hide();
            setTimeout(() => location.reload(), 500);
        } else {
            showAlert(result.message || 'خطأ في إضافة القسط', 'error');
        }
    } catch (error) {
        showAlert('خطأ: ' + (error.message || 'فشل الاتصال بالخادم'), 'error');
    } finally {
        // إعادة تفعيل الزر
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalText;
        }
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
                                <a href="/reports/receipt/${inst.id}" target="_blank" class="btn btn-outline-success btn-xs" title="طباعة الوصل">
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
