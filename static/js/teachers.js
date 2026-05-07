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