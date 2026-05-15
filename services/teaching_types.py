"""
teaching_types.py - إدارة الأنواع التدريسية المخصصة

يحتوي على دوال موحدة للتعامل مع:
- الأنواع الأساسية: حضوري، الكتروني، مدمج
- الأنواع المخصصة: دورة صيفية، مراجعة مركزة، إلخ

الأنواع المخصصة تُخزن في عمود custom_type_settings بصيغة JSON
"""

import json
import logging
from typing import Dict, Any, Optional, Tuple

# الأنواع الأساسية الثابتة
BASE_TEACHING_TYPES = ['حضوري', 'الكتروني', 'مدمج']

# الحد الأعلى المنطقي لقسط نوع التدريس (بالدينار العراقي)
MAX_REASONABLE_FEE = 50_000_000  # 50 مليون د.ع

# خريطة الأنواع الأساسية لحقل القسط في جدول teachers
BASE_FEE_MAP = {
    'حضوري': 'fee_in_person',
    'الكتروني': 'fee_electronic',
    'مدمج': 'fee_blended',
}

# خريطة الأنواع الأساسية لحقل نسبة الخصم
BASE_PCT_MAP = {
    'حضوري': 'institute_pct_in_person',
    'الكتروني': 'institute_pct_electronic',
    'مدمج': 'institute_pct_blended',
}

# خريطة الأنواع الأساسية لحقل نوع الخصم
BASE_DED_TYPE_MAP = {
    'حضوري': 'inst_ded_type_in_person',
    'الكتروني': 'inst_ded_type_electronic',
    'مدمج': 'inst_ded_type_blended',
}

# خريطة الأنواع الأساسية لحقل المبلغ اليدوي
BASE_MANUAL_MAP = {
    'حضوري': 'inst_ded_manual_in_person',
    'الكتروني': 'inst_ded_manual_electronic',
    'مدمج': 'inst_ded_manual_blended',
}


def parse_custom_type_settings(settings_raw: Any) -> Dict[str, Dict]:
    """
    قراءة بيانات الأنواع المخصصة من JSON وتنظيفها
    
    المعامل: settings_raw - قيمة custom_type_settings من قاعدة البيانات (str أو dict أو None)
    القيمة المرجعة: dict حيث المفتاح اسم النوع والقيمة dict يحتوي:
        - fee: القسط (int)
        - deduction_type: نوع الخصم ('percentage' أو 'manual')
        - deduction_pct: نسبة الخصم (int)
        - deduction_manual: مبلغ الخصم اليدوي (int)
    """
    if not settings_raw:
        return {}
    
    if isinstance(settings_raw, dict):
        raw = settings_raw
    elif isinstance(settings_raw, str):
        try:
            raw = json.loads(settings_raw)
        except (json.JSONDecodeError, TypeError):
            return {}
    else:
        return {}
    
    if not isinstance(raw, dict):
        return {}
    
    cleaned = {}
    for type_name, type_data in raw.items():
        if not isinstance(type_name, str) or not type_name.strip():
            continue
        if not isinstance(type_data, dict):
            continue
        
        # لا نقبل الأنواع الأساسية كأنواع مخصصة
        if type_name.strip() in BASE_TEACHING_TYPES:
            continue
        
        cleaned[type_name.strip()] = {
            'fee': int(type_data.get('fee', 0) or 0),
            'deduction_type': type_data.get('deduction_type', 'percentage') or 'percentage',
            'deduction_pct': int(type_data.get('deduction_pct', 0) or 0),
            'deduction_manual': int(type_data.get('deduction_manual', 0) or 0),
        }
    
    return cleaned


def dump_custom_type_settings(settings: Dict[str, Dict]) -> str:
    """
    تحويل بيانات الأنواع المخصصة إلى JSON للحفظ في قاعدة البيانات
    
    المعامل: settings - dict حيث المفتاح اسم النوع والقيمة dict بيانات النوع
    القيمة المرجعة: JSON string
    """
    if not settings:
        return '{}'
    
    cleaned = {}
    for type_name, type_data in settings.items():
        if not type_name or not type_name.strip():
            continue
        if type_name.strip() in BASE_TEACHING_TYPES:
            continue
        
        ded_type = type_data.get('deduction_type', 'percentage') or 'percentage'
        
        cleaned[type_name.strip()] = {
            'fee': int(type_data.get('fee', 0) or 0),
            'deduction_type': ded_type,
            'deduction_pct': int(type_data.get('deduction_pct', 0) or 0) if ded_type == 'percentage' else 0,
            'deduction_manual': int(type_data.get('deduction_manual', 0) or 0) if ded_type == 'manual' else 0,
        }
    
    return json.dumps(cleaned, ensure_ascii=False)


def get_fee_for_study_type(teacher: Dict, study_type: str) -> int:
    """
    ترجع القسط الصحيح حسب نوع الدراسة
    
    المعاملات:
        teacher: dict بيانات المدرس من قاعدة البيانات
        study_type: str نوع الدراسة
    
    القيمة المرجعة: int القسط (0 إذا لم يوجد)
    """
    if not study_type or not teacher:
        return 0
    
    study_type = study_type.strip()
    
    # الأنواع الأساسية
    if study_type in BASE_FEE_MAP:
        fee_key = BASE_FEE_MAP[study_type]
        return int(teacher.get(fee_key, 0) or 0)
    
    # الأنواع المخصصة
    custom_settings = parse_custom_type_settings(teacher.get('custom_type_settings'))
    if study_type in custom_settings:
        return custom_settings[study_type].get('fee', 0)
    
    return 0


def get_deduction_for_study_type(teacher: Dict, study_type: str) -> Tuple[str, int]:
    """
    ترجع خصم المعهد حسب نوع الدراسة
    
    المعاملات:
        teacher: dict بيانات المدرس
        study_type: str نوع الدراسة
    
    القيمة المرجعة: tuple (deduction_type, deduction_value)
        - deduction_type: 'percentage' أو 'manual'
        - deduction_value: النسبة أو المبلغ
    """
    if not study_type or not teacher:
        return ('percentage', 0)
    
    study_type = study_type.strip()
    
    # الأنواع الأساسية
    if study_type in BASE_DED_TYPE_MAP:
        ded_type_key = BASE_DED_TYPE_MAP[study_type]
        ded_type = teacher.get(ded_type_key, 'percentage') or 'percentage'
        
        if ded_type == 'manual':
            manual_key = BASE_MANUAL_MAP[study_type]
            return ('manual', int(teacher.get(manual_key, 0) or 0))
        else:
            pct_key = BASE_PCT_MAP[study_type]
            return ('percentage', int(teacher.get(pct_key, 0) or 0))
    
    # الأنواع المخصصة
    custom_settings = parse_custom_type_settings(teacher.get('custom_type_settings'))
    if study_type in custom_settings:
        type_data = custom_settings[study_type]
        ded_type = type_data.get('deduction_type', 'percentage')
        if ded_type == 'manual':
            return ('manual', type_data.get('deduction_manual', 0))
        else:
            return ('percentage', type_data.get('deduction_pct', 0))
    
    return ('percentage', 0)


def get_all_teaching_types(teacher: Dict) -> list:
    """
    ترجع قائمة بكل أنواع التدريس المتاحة للمدرس (أساسية + مخصصة)
    
    المعامل: teacher: dict بيانات المدرس
    القيمة المرجعة: list of str
    """
    teaching_types_str = teacher.get('teaching_types', 'حضوري') or 'حضوري'
    types = [t.strip() for t in teaching_types_str.split(',') if t.strip()]
    
    # إضافة أي أنواع مخصصة ليست في teaching_types
    custom_settings = parse_custom_type_settings(teacher.get('custom_type_settings'))
    for custom_type in custom_settings:
        if custom_type not in types:
            types.append(custom_type)
    
    return types


def validate_custom_type_data(type_name: str, type_data: Dict) -> Optional[str]:
    """
    التحقق من صحة بيانات نوع مخصص
    
    القيمة المرجعة: رسالة خطأ أو None إذا صحيح
    """
    if not type_name or not type_name.strip():
        return 'اسم النوع مطلوب'
    
    type_name = type_name.strip()
    
    if type_name in BASE_TEACHING_TYPES:
        return f'لا يمكن استخدام "{type_name}" كنوع مخصص - هو نوع أساسي'
    
    fee = int(type_data.get('fee', 0) or 0)
    if fee <= 0:
        return f'قسط النوع "{type_name}" يجب أن يكون أكبر من صفر'
    if fee > MAX_REASONABLE_FEE:
        return f'قسط نوع التدريس مرتفع جداً. يرجى إدخال المبلغ بالدينار العراقي، والحد الأعلى المسموح هو 50,000,000 د.ع.'
    
    ded_type = type_data.get('deduction_type', 'percentage')
    if ded_type == 'percentage':
        pct = int(type_data.get('deduction_pct', 0) or 0)
        if pct < 0 or pct > 99:
            return f'نسبة خصم المعهد لـ "{type_name}" يجب أن تكون بين 0 و 99'
    elif ded_type == 'manual':
        manual = int(type_data.get('deduction_manual', 0) or 0)
        if manual < 0:
            return f'مبلغ خصم المعهد لـ "{type_name}" يجب أن يكون صفر أو أكثر'
        if manual > fee:
            return f'مبلغ خصم المعهد لـ "{type_name}" لا يمكن أن يتجاوز القسط'
    
    return None


def normalize_thousand_or_dinar_amount(value: Any) -> int:
    """
    يقبل القيمة إذا وصلت بالألف أو بالدينار.
    مثال:
    400 => 400,000
    400000 => 400,000
    """
    try:
        raw = int(float(value or 0))
    except (ValueError, TypeError):
        return 0

    if raw <= 0:
        return 0

    # إذا القيمة 50,000 أو أقل نعتبرها مدخلة بالألف
    if raw <= 50000:
        return raw * 1000

    # إذا أكبر من 50,000 نعتبرها دينار فعلي
    return raw


def build_custom_type_settings_from_form(form_data: Dict) -> Tuple[Dict[str, Dict], list]:
    """
    بناء بيانات الأنواع المخصصة من بيانات الفورم
    
    المعامل: form_data - dict يحتوي مفاتيح مثل:
        custom_type_names: قائمة أسماء الأنواع
        custom_type_fees: قائمة الأقساط
        custom_type_ded_types: قائمة أنواع الخصم
        custom_type_ded_pcts: قائمة نسب الخصم
        custom_type_ded_manuals: قائمة المبالغ اليدوية
    
    القيمة المرجعة: tuple (settings_dict, errors_list)
    """
    settings = {}
    errors = []
    
    names = form_data.getlist('custom_type_names[]') if hasattr(form_data, 'getlist') else form_data.get('custom_type_names[]', [])
    fees = form_data.getlist('custom_type_fees[]') if hasattr(form_data, 'getlist') else form_data.get('custom_type_fees[]', [])
    ded_types = form_data.getlist('custom_type_ded_types[]') if hasattr(form_data, 'getlist') else form_data.get('custom_type_ded_types[]', [])
    ded_pcts = form_data.getlist('custom_type_ded_pcts[]') if hasattr(form_data, 'getlist') else form_data.get('custom_type_ded_pcts[]', [])
    ded_manuals = form_data.getlist('custom_type_ded_manuals[]') if hasattr(form_data, 'getlist') else form_data.get('custom_type_ded_manuals[]', [])
    
    seen_names = set()
    
    for i in range(len(names)):
        type_name = names[i].strip() if i < len(names) else ''
        if not type_name:
            continue
        
        if type_name in seen_names:
            errors.append(f'النوع "{type_name}" مكرر')
            continue
        seen_names.add(type_name)
        
        fee_val = 0
        if i < len(fees):
            try:
                fee_val = normalize_thousand_or_dinar_amount(fees[i])
            except (ValueError, TypeError):
                fee_val = 0
        
        ded_type = ded_types[i] if i < len(ded_types) else 'percentage'
        if ded_type not in ('percentage', 'manual'):
            ded_type = 'percentage'
        
        ded_pct = 0
        if i < len(ded_pcts):
            try:
                ded_pct = int(ded_pcts[i])
            except (ValueError, TypeError):
                ded_pct = 0
        
        ded_manual = 0
        if i < len(ded_manuals):
            try:
                ded_manual = normalize_thousand_or_dinar_amount(ded_manuals[i])
            except (ValueError, TypeError):
                ded_manual = 0
        
        type_data = {
            'fee': fee_val,
            'deduction_type': ded_type,
            'deduction_pct': ded_pct if ded_type == 'percentage' else 0,
            'deduction_manual': ded_manual if ded_type == 'manual' else 0,
        }
        
        # التحقق
        validation_error = validate_custom_type_data(type_name, type_data)
        if validation_error:
            errors.append(validation_error)
            continue
        
        settings[type_name] = type_data
    
    return settings, errors
