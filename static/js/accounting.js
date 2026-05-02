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
    document.getElementById('w_teacher_id').value = teacherId;
    document.getElementById('w_teacher_name').textContent = teacherName;
    document.getElementById('w_available_balance').textContent = formatCurrency(availableBalance);
    document.getElementById('w_available_balance').dataset.balance = availableBalance;
    document.getElementById('w_amount').value = '';
    document.getElementById('w_amount').max = availableBalance;
    document.getElementById('w_date').value = getTodayDate();
    document.getElementById('w_notes').value = '';
    
    withdrawalModal.show();
    
    // التركيز على حقل المبلغ
    document.getElementById('w_amount').focus();
}

/**
 * تسجيل سحب جديد
 */
async function addWithdrawal(event) {
    event.preventDefault();
    
    const teacherId = parseInt(document.getElementById('w_teacher_id').value);
    const amount = toFullAmount(document.getElementById('w_amount').value);
    const availableBalance = parseInt(document.getElementById('w_available_balance').dataset.balance);
    
    // التحقق من المبلغ
    if (!amount || amount <= 0) {
        showAlert('يرجى إدخال مبلغ صحيح أكبر من صفر', 'warning');
        return;
    }
    
    if (amount > availableBalance) {
        showAlert(`❌ المبلغ (${formatCurrency(amount)}) أكبر من الرصيد المتاح (${formatCurrency(availableBalance)})`, 'error');
        return;
    }

    const data = {
        teacher_id: teacherId,
        amount: amount,
        withdrawal_date: document.getElementById('w_date').value,
        notes: document.getElementById('w_notes').value
    };

    try {
        const result = await apiRequest('/api/withdrawals', {
            method: 'POST',
            body: JSON.stringify(data)
        });

        if (result.success) {
            showAlert(result.message, 'success');
            withdrawalModal.hide();
            location.reload();
        } else {
            showAlert(result.message, 'error');
        }
    } catch (error) {
        showAlert(error.message, 'error');
    }
}

/**
 * عرض آخر سحوبات المدرس
 * @param {number} teacherId - رقم المدرس
 */
async function showRecentWithdrawals(teacherId) {
    try {
        const result = await apiRequest(`/api/withdrawals/teacher/${teacherId}?limit=10`);
        
        let html = '<ul class="list-group">';
        
        if (result.data && result.data.length > 0) {
            result.data.forEach(w => {
                html += `
                    <li class="list-group-item d-flex justify-content-between align-items-center">
                        <span>
                            ${formatCurrency(w.amount)}
                            <small class="text-muted d-block">${w.notes || 'بدون ملاحظات'}</small>
                        </span>
                        <span class="badge bg-secondary">${formatDate(w.withdrawal_date)}</span>
                    </li>
                `;
            });
        } else {
            html += '<li class="list-group-item text-muted text-center">لا توجد سحوبات</li>';
        }
        
        html += '</ul>';
        html += `<div class="mt-2 text-muted small">الإجمالي: ${formatCurrency(result.total_withdrawn)}</div>`;
        
        // عرض في modal أو popover
        
    } catch (error) {
        showAlert(error.message, 'error');
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