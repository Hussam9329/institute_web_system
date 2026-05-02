// ============================================
// accounting.js - JavaScript للمحاسبة
// ============================================

let withdrawalModal;

document.addEventListener('DOMContentLoaded', function() {
    const modalEl = document.getElementById('withdrawalModal');
    if (modalEl) {
        withdrawalModal = new bootstrap.Modal(modalEl);
    }

    // معالجة أحداث الأزرار عبر data-action (بدون XSS)
    document.addEventListener('click', function(e) {
        const btn = e.target.closest('[data-action="withdraw"]');
        if (!btn) return;
        
        // منع النقر المزدوج
        if (btn.disabled) return;
        
        const teacherId = parseInt(btn.dataset.teacherId);
        const teacherName = btn.dataset.teacherName;
        const balance = parseInt(btn.dataset.balance);
        
        if (isNaN(teacherId) || isNaN(balance)) {
            showAlert('بيانات المدرس غير صحيحة', 'error');
            return;
        }
        
        openWithdrawalModal(teacherId, teacherName, balance);
    });
});

/**
 * فتح نموذج تسجيل سحب
 * @param {number} teacherId - رقم المدرس
 * @param {string} teacherName - اسم المدرس
 * @param {number} availableBalance - الرصيد المتاح
 */
function openWithdrawalModal(teacherId, teacherName, availableBalance) {
    const elTeacherId = document.getElementById('w_teacher_id');
    const elTeacherName = document.getElementById('w_teacher_name');
    const elBalance = document.getElementById('w_available_balance');
    const elAmount = document.getElementById('w_amount');
    const elDate = document.getElementById('w_date');
    const elNotes = document.getElementById('w_notes');
    
    if (!elTeacherId || !elAmount || !elDate) {
        showAlert('خطأ في تحميل نموذج السحب', 'error');
        return;
    }
    
    elTeacherId.value = teacherId;
    if (elTeacherName) elTeacherName.textContent = teacherName;
    if (elBalance) {
        elBalance.textContent = formatCurrency(availableBalance);
        elBalance.dataset.balance = availableBalance;
    }
    elAmount.value = '';
    elDate.value = getTodayDate();
    if (elNotes) elNotes.value = '';
    
    if (withdrawalModal) {
        withdrawalModal.show();
        setTimeout(() => elAmount.focus(), 300);
    } else {
        showAlert('خطأ في فتح نموذج السحب', 'error');
    }
}

/**
 * تسجيل سحب جديد
 */
async function addWithdrawal(event) {
    event.preventDefault();
    
    const teacherId = parseInt(document.getElementById('w_teacher_id').value);
    const amountInput = document.getElementById('w_amount').value;
    const amount = toFullAmount(amountInput);
    const dateValue = document.getElementById('w_date').value;
    const availableBalanceEl = document.getElementById('w_available_balance');
    const availableBalance = availableBalanceEl ? parseInt(availableBalanceEl.dataset.balance || '0') : 0;
    
    // التحقق من المبلغ
    if (!amountInput || isNaN(amount) || amount <= 0) {
        showAlert('يرجى إدخال مبلغ صحيح أكبر من صفر', 'warning');
        return;
    }
    
    if (!dateValue) {
        showAlert('يرجى تحديد تاريخ السحب', 'warning');
        return;
    }
    
    if (amount > availableBalance) {
        showAlert('المبلغ (' + formatCurrency(amount) + ') أكبر من الرصيد المتاح (' + formatCurrency(availableBalance) + ')', 'error');
        return;
    }

    const data = {
        teacher_id: teacherId,
        amount: amount,
        withdrawal_date: dateValue,
        notes: (document.getElementById('w_notes').value || '')
    };

    // تعطيل الزر أثناء المعالجة
    const submitBtn = event.target.querySelector('button[type="submit"]');
    const originalText = submitBtn ? submitBtn.innerHTML : '';
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>جاري التسجيل...';
    }

    try {
        const result = await apiRequest('/api/withdrawals', {
            method: 'POST',
            body: JSON.stringify(data)
        });

        if (result.success) {
            showAlert(result.message, 'success');
            if (withdrawalModal) withdrawalModal.hide();
            setTimeout(() => location.reload(), 500);
        } else {
            showAlert(result.message || 'خطأ في تسجيل السحب', 'error');
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
 * حذف سحب
 * @param {number} withdrawalId - رقم السحب
 */
async function deleteWithdrawal(withdrawalId) {
    if (!confirmAction('هل أنت متأكد من حذف هذا السحب؟')) return;

    try {
        const result = await apiRequest(`/api/withdrawals/${withdrawalId}`, {
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
