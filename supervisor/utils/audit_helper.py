# supervisor/utils/audit_helper.py

import json
from datetime import datetime, date
from decimal import Decimal

class AuditHelper:
    """
    Modeller üzerindeki değişiklikleri (Diff) yakalamak için yardımcı sınıf.
    Eski Veri vs Yeni Veri karşılaştırmasını otomatik yapar.
    """

    @staticmethod
    def serialize_value(value):
        """Tarih, Decimal gibi JSON olmayan verileri string'e çevirir"""
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        return value

    @staticmethod
    def get_changes(model_instance):
        """
        Bir model nesnesindeki (dirty) değişiklikleri yakalar.
        SQLAlchemy'nin session history özelliğini kullanır.
        """
        from sqlalchemy import inspect
        
        changes = {}
        ins = inspect(model_instance)
        
        # Sadece değişen attribute'ları gez
        for attr in ins.attrs:
            history = attr.history
            
            # Eğer bir değişiklik varsa (has_changes)
            if history.has_changes():
                old_val = history.deleted[0] if history.deleted else None
                new_val = history.added[0] if history.added else None
                
                # Değerler gerçekten farklı mı? (Bazen type farkı olabilir '5' vs 5)
                if str(old_val) != str(new_val):
                    changes[attr.key] = {
                        'old': AuditHelper.serialize_value(old_val),
                        'new': AuditHelper.serialize_value(new_val)
                    }
                    
        return changes

    @staticmethod
    def capture_snapshot(model_instance, include_fields=None):
        """
        Silme işlemi öncesi nesnenin son halini JSON olarak saklar.
        """
        data = {}
        for column in model_instance.__table__.columns:
            if include_fields and column.name not in include_fields:
                continue
            val = getattr(model_instance, column.name)
            data[column.name] = AuditHelper.serialize_value(val)
        return data