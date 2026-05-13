// ============================================
// theme-toggle.js - تبديل الثيم (نهاري/ليلي)
// ============================================

(function () {
    "use strict";

    const THEME_KEY = "institute_theme";

    function getPreferredTheme() {
        const savedTheme = localStorage.getItem(THEME_KEY);

        if (savedTheme === "light" || savedTheme === "dark") {
            return savedTheme;
        }

        var prefersDark =
            window.matchMedia &&
            window.matchMedia("(prefers-color-scheme: dark)").matches;

        return prefersDark ? "dark" : "light";
    }

    function applyTheme(theme) {
        document.documentElement.setAttribute("data-theme", theme);
        localStorage.setItem(THEME_KEY, theme);

        updateToggleButton(theme);
        saveThemeToServer(theme);
    }

    function updateToggleButton(theme) {
        var button = document.getElementById("themeToggleBtn");

        if (!button) return;

        var icon = button.querySelector("i");
        var text = button.querySelector(".theme-toggle-text");

        if (theme === "dark") {
            if (icon) {
                icon.className = "fas fa-sun";
            }

            if (text) {
                text.textContent = "الوضع النهاري";
            }

            button.setAttribute("title", "التبديل إلى الوضع النهاري");
            button.setAttribute("aria-label", "التبديل إلى الوضع النهاري");
        } else {
            if (icon) {
                icon.className = "fas fa-moon";
            }

            if (text) {
                text.textContent = "الوضع الليلي";
            }

            button.setAttribute("title", "التبديل إلى الوضع الليلي");
            button.setAttribute("aria-label", "التبديل إلى الوضع الليلي");
        }
    }

    function toggleTheme() {
        var currentTheme =
            document.documentElement.getAttribute("data-theme") || "light";
        var nextTheme = currentTheme === "dark" ? "light" : "dark";

        applyTheme(nextTheme);
    }

    function saveThemeToServer(theme) {
        // محاولة حفظ الثيم في الخادم (اختياري - يعمل حتى لو فشل)
        try {
            fetch("/api/user/theme", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ theme: theme }),
            }).catch(function () {
                // لا نعرض خطأ للمستخدم لأن localStorage يكفي كخطة بديلة
                console.warn("تعذر حفظ الثيم في الخادم");
            });
        } catch (e) {
            // تجاهل الأخطاء
        }
    }

    // تطبيق الثيم مبكرًا بعد تحميل الملف
    applyTheme(getPreferredTheme());

    document.addEventListener("DOMContentLoaded", function () {
        var button = document.getElementById("themeToggleBtn");

        if (button) {
            button.addEventListener("click", toggleTheme);
        }

        updateToggleButton(
            document.documentElement.getAttribute("data-theme") ||
                getPreferredTheme()
        );
    });
})();
