// ============================================
// teachers.js - JavaScript لإدارة المدرسين
// ============================================

document.addEventListener('DOMContentLoaded', function() {
    // يمكن إضافة تهيئات خاصة هنا
    
    // مثال: فلترة المدرسين حسب المادة
    initSubjectFilter();
});

/**
 * تهيئة فلتر المواد
 */
function initSubjectFilter() {
    const subjectLinks = document.querySelectorAll('.subject-filter-link');
    
    subjectLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const subject = this.dataset.subject;
            filterBySubject(subject);
        });
    });
}

/**
 * فلترة المدرسين حسب المادة
 * @param {string} subject - اسم المادة
 */
function filterBySubject(subject) {
    const rows = document.querySelectorAll('#teachersTable tbody tr');
    
    rows.forEach(row => {
        const rowSubject = row.dataset.subject;
        if (!subject || rowSubject === subject) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
}

/**
 * عرض تفاصيل المدرس في modal
 * @param {number} teacherId - رقم المدرس
 */
async function showTeacherQuickView(teacherId) {
    try {
        const result = await apiRequest(`/api/teachers/${teacherId}`);
        const teacher = result.data;
        
        // إنشاء محتوى سريع
        const content = `
            <div class="p-3">
                <h5 class="mb-3">${teacher.name}</h5>
                <table class="table table-sm table-borderless">
                    <tr><td class="fw-bold">المادة:</td><td>${teacher.subject}</td></tr>
                    <tr><td class="fw-bold">الأجر الكلي:</td><td>${formatCurrency(teacher.total_fee)}</td></tr>
                </table>
            </div>
        `;
        
        // يمكن عرضه في modal أو tooltip
        
    } catch (error) {
        showAlert(error.message, 'error');
    }
}