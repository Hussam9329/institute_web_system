# ============================================
# services/cache_service.py
# تخزين مؤقت للخادم (Server-side Cache)
# TTL: 30 ثانية افتراضياً
# ============================================

import time
import threading
import logging
from typing import Any, Optional

try:
    from trial_mode import is_trial_request
except Exception:
    def is_trial_request() -> bool:
        return False

logger = logging.getLogger(__name__)


class CacheService:
    """خدمة التخزين المؤقت - آمنة للخيوط مع TTL"""
    
    def __init__(self, default_ttl: int = 30):
        """
        إنشاء خدمة التخزين المؤقت
        
        Args:
            default_ttl: مدة التخزين المؤقت الافتراضية بالثواني (30 ثانية)
        """
        self._cache = {}
        self._lock = threading.Lock()
        self.default_ttl = default_ttl
    
    def _scope_key(self, key: str) -> str:
        """عزل كاش الحساب التجريبي حتى لا تظهر له بيانات المستخدمين الأصليين."""
        return f"trial:{key}" if is_trial_request() else key

    def _scope_pattern(self, pattern: str) -> str:
        return f"trial:{pattern}" if is_trial_request() else pattern
    
    def get(self, key: str) -> Optional[Any]:
        """
        الحصول على قيمة من التخزين المؤقت
        
        Args:
            key: مفتاح التخزين المؤقت
            
        Returns:
            القيمة المخزنة أو None إذا انتهت الصلاحية أو لم تكن موجودة
        """
        key = self._scope_key(key)
        with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if time.time() < entry['expires_at']:
                    return entry['value']
                else:
                    # انتهت الصلاحية - حذف
                    del self._cache[key]
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        تخزين قيمة في التخزين المؤقت
        
        Args:
            key: مفتاح التخزين المؤقت
            value: القيمة المراد تخزينها
            ttl: مدة الصلاحية بالثواني (يستخدم الافتراضي إذا لم يُحدد)
        """
        if ttl is None:
            ttl = self.default_ttl
        
        key = self._scope_key(key)
        with self._lock:
            self._cache[key] = {
                'value': value,
                'expires_at': time.time() + ttl
            }
    
    def delete(self, key: str):
        """حذف قيمة من التخزين المؤقت"""
        key = self._scope_key(key)
        with self._lock:
            self._cache.pop(key, None)
    
    def clear(self):
        """مسح جميع القيم المخزنة"""
        with self._lock:
            self._cache.clear()
    
    def cleanup_expired(self):
        """حذف جميع القيم منتهية الصلاحية"""
        with self._lock:
            now = time.time()
            expired_keys = [
                key for key, entry in self._cache.items() 
                if now >= entry['expires_at']
            ]
            for key in expired_keys:
                del self._cache[key]
            
            if expired_keys:
                logger.debug(f"تم حذف {len(expired_keys)} عنصر منتهي الصلاحية من التخزين المؤقت")
    
    def get_or_set(self, key: str, factory, ttl: Optional[int] = None) -> Any:
        """
        الحصول على القيمة من التخزين المؤقت، أو حسابها وتخزينها إذا لم تكن موجودة
        
        Args:
            key: مفتاح التخزين المؤقت
            factory: دالة تُرجع القيمة إذا لم تكن مخزنة
            ttl: مدة الصلاحية بالثواني
            
        Returns:
            القيمة المخزنة أو المحسوبة حديثاً
        """
        # محاولة الحصول على القيمة المخزنة أولاً
        cached = self.get(key)
        if cached is not None:
            return cached
        
        # حساب القيمة وتخزينها
        value = factory()
        self.set(key, value, ttl)
        return value
    
    def invalidate_pattern(self, pattern: str):
        """
        حذف جميع القيم التي يبدأ مفتاحها بالنمط المحدد
        
        Args:
            pattern: بداية المفتاح المراد حذفه (مثل 'stats' لحذف 'stats:*')
        """
        pattern = self._scope_pattern(pattern)
        with self._lock:
            keys_to_delete = [
                key for key in self._cache.keys() 
                if key.startswith(pattern)
            ]
            for key in keys_to_delete:
                del self._cache[key]
    
    def stats(self) -> dict:
        """إرجاع إحصائيات التخزين المؤقت"""
        with self._lock:
            now = time.time()
            total = len(self._cache)
            active = sum(1 for entry in self._cache.values() if now < entry['expires_at'])
            expired = total - active
            return {
                'total': total,
                'active': active,
                'expired': expired
            }


# ===== نسخة عامة من خدمة التخزين المؤقت =====
cache_service = CacheService(default_ttl=30)


# ===== تنظيف تلقائي كل 60 ثانية =====
def _cleanup_timer():
    """تنظيف دوري للعناصر منتهية الصلاحية"""
    while True:
        try:
            time.sleep(60)
            cache_service.cleanup_expired()
        except Exception:
            pass

# تشغيل منظف الخلفية
_cleanup_thread = threading.Thread(target=_cleanup_timer, daemon=True)
_cleanup_thread.start()
