# app/form_builder/report_designer.py

"""
Report Designer - Kullanıcı Kendi Raporunu Oluşturur (No-Code)

Özellikler:
- Drag & Drop alan seçimi
- Dinamik filtreleme (=, !=, >, <, LIKE, BETWEEN, IN)
- Gruplama ve toplama (SUM, AVG, COUNT, MIN, MAX)
- Sıralama (ASC, DESC)
- Grafik tipi seçimi (Line, Bar, Pie)
- Export (PDF, Excel, CSV, JSON)
- Rapor kaydetme ve paylaşma
- Schedule (Otomatik mail gönderimi)
- Drill-down (Detaya inme)
- Caching (Performans)
- Permissions (İzin yönetimi)
- Versioning (Versiyon geçmişi)
- Query optimizer (SQL optimizasyonu)
- Usage analytics (Kullanım istatistikleri)
"""

from typing import List, Dict, Any, Optional, Type, Tuple, Union
from sqlalchemy import and_, or_, func, cast, String, Integer, Float, Date, DateTime
from sqlalchemy.orm import Query, joinedload
from flask_sqlalchemy.model import Model as BaseModel
from datetime import datetime, date
from hashlib import md5
import json
import logging

logger = logging.getLogger(__name__)


class ReportDesigner:
    """
    Kullanıcı kendi raporunu tasarlasın (No-code Report Builder).

    Enterprise özellikleri:
        - Saved reports (kayıtlı raporlar)
        - Scheduled reports (zamanlanmış raporlar)
        - Drill-down (detaya inme)
        - Caching (önbellekleme)
        - Permissions (izin yönetimi)
        - Versioning (versiyon geçmişi)
        - Query optimizer (sorgu optimizasyonu)
        - Usage analytics (kullanım istatistikleri)

    Example:
        >>> designer = ReportDesigner(MyModel, config)
        >>> data = designer.execute()
    """

    # Desteklenen operatörler
    OPERATORS = {
        'equals': '=',
        'not_equals': '!=',
        'greater_than': '>',
        'less_than': '<',
        'greater_or_equal': '>=',
        'less_or_equal': '<=',
        'contains': 'LIKE',
        'not_contains': 'NOT LIKE',
        'starts_with': 'LIKE',
        'ends_with': 'LIKE',
        'between': 'BETWEEN',
        'in': 'IN',
        'not_in': 'NOT IN',
        'is_null': 'IS NULL',
        'is_not_null': 'IS NOT NULL'
    }

    # Desteklenen toplama fonksiyonları
    AGGREGATIONS = {
        'sum': func.sum,
        'avg': func.avg,
        'count': func.count,
        'min': func.min,
        'max': func.max,
        'count_distinct': lambda col: func.count(func.distinct(col))
    }

    def __init__(
        self,
        model: Type[BaseModel],
        config: Dict[str, Any],
        session: Any = None
    ) -> None:
        """
        Initialize the ReportDesigner.

        Args:
            model: SQLAlchemy model class.
            config: Kullanıcı rapor konfigürasyonu (JSON).
            session: Database session (Firebird için get_tenant_db()).

        Config Örneği:
        {
            "name": "Aylık Satış Raporu",
            "description": "Son 12 ay satış analizi",
            "fields": [
                {"name": "tarih", "label": "Tarih", "visible": true},
                {"name": "tutar", "label": "Tutar", "visible": true, "format": "currency"}
            ],
            "filters": [
                {"field": "tarih", "operator": "between", "value": ["2024-01-01", "2024-12-31"]},
                {"field": "durum", "operator": "equals", "value": "ONAYLANDI"}
            ],
            "group_by": ["EXTRACT(MONTH FROM tarih)", "EXTRACT(YEAR FROM tarih)"],
            "aggregations": [
                {"function": "sum", "field": "tutar", "alias": "toplam_tutar"},
                {"function": "count", "field": "id", "alias": "fatura_sayisi"}
            ],
            "order_by": [
                {"field": "yil", "direction": "DESC"},
                {"field": "ay", "direction": "DESC"}
            ],
            "chart": {
                "enabled": true,
                "type": "line",  # line, bar, pie, doughnut
                "x_axis": "ay",
                "y_axis": "toplam_tutar"
            },
            "export": {
                "formats": ["excel", "pdf", "csv"],
                "filename": "aylik_satis_raporu"
            }
        }
        """
        self.model = model
        self.config = config
        self.session = session
        self.query = None

    # ------------------------------------------------------------------
    # CORE QUERY BUILDING
    # ------------------------------------------------------------------

    def build_query(self) -> Query:
        """
        Kullanıcı konfigürasyonunu SQL Query'e çevirir.

        Returns:
            Query: SQLAlchemy query nesnesi.

        Raises:
            ValueError: Geçersiz konfigürasyon.
            Exception: Veritabanı hatası.

        Example:
            >>> designer = ReportDesigner(Model, config)
            >>> query = designer.build_query()
        """
        try:
            logger.debug(f"Query oluşturuluyor: {self.config.get('name')}")

            # Session belirle (Firebird veya PostgreSQL)
            if self.session:
                query = self.session.query(self.model)
            else:
                from app.extensions import db
                query = db.session.query(self.model)

            # 1. SELECT ALANLARI (Gruplama varsa onları seç)
            if self.config.get('group_by'):
                select_fields: List[Any] = []

                for group_field in self.config['group_by']:
                    # Raw SQL expression mi?
                    if 'EXTRACT' in group_field or 'CAST' in group_field:
                        from sqlalchemy import text
                        select_fields.append(text(group_field))
                    else:
                        select_fields.append(getattr(self.model, group_field))

                # Agregasyon alanları
                for agg in self.config.get('aggregations', []):
                    func_name = agg['function']
                    field_name = agg['field']
                    alias = agg.get('alias', f"{func_name}_{field_name}")

                    if func_name in self.AGGREGATIONS:
                        agg_func = self.AGGREGATIONS[func_name]
                        field_obj = getattr(self.model, field_name)
                        select_fields.append(agg_func(field_obj).label(alias))

                query = query.with_entities(*select_fields)

            # 2. FİLTRELEME
            for filter_config in self.config.get('filters', []):
                filter_clause = self._build_filter(filter_config)
                if filter_clause is not None:
                    query = query.filter(filter_clause)

            # 3. GRUPLAMA
            if self.config.get('group_by'):
                for group_field in self.config['group_by']:
                    if 'EXTRACT' in group_field or 'CAST' in group_field:
                        from sqlalchemy import text
                        query = query.group_by(text(group_field))
                    else:
                        query = query.group_by(getattr(self.model, group_field))

            # 4. SIRALAMA
            for order_config in self.config.get('order_by', []):
                order_clause = self._build_order(order_config)
                if order_clause is not None:
                    query = query.order_by(order_clause)

            # 5. LIMIT (Opsiyonel)
            if self.config.get('limit'):
                query = query.limit(self.config['limit'])

            self.query = query
            logger.debug(f"Query başarıyla oluşturuldu: {self.config.get('name')}")
            return query

        except Exception as e:
            logger.error(f"Query build hatası: {e}", exc_info=True)
            raise

    def _build_filter(self, filter_config: Dict[str, Any]) -> Optional[Any]:
        """
        Tek bir filtre koşulu oluşturur.

        Args:
            filter_config: Filtre konfigürasyonu dict'i.

        Returns:
            Optional[Any]: SQLAlchemy filtre ifadesi veya None.
        """
        field_name = filter_config['field']
        operator = filter_config['operator']
        value = filter_config.get('value')

        # Model'de bu alan var mı kontrol et
        if not hasattr(self.model, field_name):
            logger.warning(f"Model'de '{field_name}' alanı bulunamadı, filtre atlanıyor.")
            return None

        field = getattr(self.model, field_name)

        # Operatöre göre filtre oluştur
        if operator == 'equals':
            return field == value

        elif operator == 'not_equals':
            return field != value

        elif operator == 'greater_than':
            return field > value

        elif operator == 'less_than':
            return field < value

        elif operator == 'greater_or_equal':
            return field >= value

        elif operator == 'less_or_equal':
            return field <= value

        elif operator == 'contains':
            return field.ilike(f"%{value}%")

        elif operator == 'not_contains':
            return ~field.ilike(f"%{value}%")

        elif operator == 'starts_with':
            return field.ilike(f"{value}%")

        elif operator == 'ends_with':
            return field.ilike(f"%{value}")

        elif operator == 'between':
            if isinstance(value, list) and len(value) == 2:
                return field.between(value[0], value[1])

        elif operator == 'in':
            if isinstance(value, list):
                return field.in_(value)

        elif operator == 'not_in':
            if isinstance(value, list):
                return ~field.in_(value)

        elif operator == 'is_null':
            return field.is_(None)

        elif operator == 'is_not_null':
            return field.isnot(None)

        logger.warning(f"Desteklenmeyen operatör: {operator}")
        return None

    def _build_order(self, order_config: Dict[str, Any]) -> Optional[Any]:
        """
        Sıralama koşulu oluşturur.

        Args:
            order_config: Sıralama konfigürasyonu dict'i.

        Returns:
            Optional[Any]: SQLAlchemy sıralama ifadesi veya None.
        """
        field_name = order_config['field']
        direction = order_config.get('direction', 'ASC').upper()

        # Model'de bu alan var mı?
        if not hasattr(self.model, field_name):
            logger.warning(f"Model'de '{field_name}' alanı bulunamadı, sıralama atlanıyor.")
            return None

        field = getattr(self.model, field_name)

        if direction == 'DESC':
            return field.desc()
        else:
            return field.asc()

    # ------------------------------------------------------------------
    # EXECUTION
    # ------------------------------------------------------------------

    def execute(self) -> List[Dict[str, Any]]:
        """
        Raporu çalıştırır ve sonuç döndürür.

        Returns:
            List[Dict[str, Any]]: Rapor satırları.

        Raises:
            Exception: Veritabanı veya query hatası.

        Example:
            >>> data = designer.execute()
        """
        if not self.query:
            self.build_query()

        try:
            results = self.query.all()

            # Sonuçları dict listesine çevir
            data: List[Dict[str, Any]] = []
            for row in results:
                # Eğer tuple ise (gruplama sonucu)
                if hasattr(row, '_asdict'):
                    data.append(row._asdict())
                # Eğer model instance ise
                elif hasattr(row, '__dict__'):
                    row_dict = {col.name: getattr(row, col.name)
                               for col in row.__table__.columns}
                    data.append(row_dict)
                # KeyedTuple (SQLAlchemy result)
                else:
                    data.append(dict(row._mapping))

            logger.debug(f"Rapor çalıştırıldı: {len(data)} satır döndü")
            return data

        except Exception as e:
            logger.error(f"Rapor çalıştırma hatası: {e}", exc_info=True)
            raise

    def execute_cached(self, ttl: int = 300) -> List[Dict[str, Any]]:
        """
        Raporu önbellek (cache) ile çalıştırır.

        Aynı konfigürasyonlu rapor ``ttl`` saniye içinde tekrar
        çalıştırılırsa veritabanına gitmeden önbellekten döner.

        Args:
            ttl: Cache süresi saniye cinsinden (varsayılan: 300).

        Returns:
            List[Dict[str, Any]]: Cached veya fresh veri.

        Example:
            >>> data = designer.execute_cached(ttl=600)
        """
        try:
            from app.extensions import cache as app_cache

            # Config'i hash'le (cache key)
            config_str = json.dumps(self.config, sort_keys=True)
            cache_key = f"report_{md5(config_str.encode()).hexdigest()}"

            cached_data = app_cache.get(cache_key)

            if cached_data is not None:
                logger.debug(f"Cache HIT: {cache_key}")
                return cached_data

            logger.debug(f"Cache MISS: {cache_key}")
            data = self.execute()
            app_cache.set(cache_key, data, timeout=ttl)

            return data

        except Exception as e:
            logger.error(f"execute_cached hatası: {e}", exc_info=True)
            # Cache hatası durumunda doğrudan çalıştır
            return self.execute()

    # ------------------------------------------------------------------
    # SAVED REPORTS
    # ------------------------------------------------------------------

    def save_report(self, user_id: str, is_public: bool = False) -> str:
        """
        Rapor konfigürasyonunu veritabanına kaydeder.

        Args:
            user_id: Kullanıcı ID.
            is_public: Herkese açık mı?

        Returns:
            str: Kaydedilen rapor ID'si.

        Raises:
            Exception: Veritabanı hatası.

        Example:
            >>> report_id = designer.save_report(user_id='abc-123')
        """
        from app.modules.rapor.models import SavedReport
        from app.extensions import db

        try:
            report = SavedReport(
                name=self.config['name'],
                description=self.config.get('description', ''),
                model_name=self.model.__name__,
                config_json=json.dumps(self.config),
                user_id=user_id,
                is_public=is_public
            )
            db.session.add(report)
            db.session.commit()

            logger.info(f"Rapor kaydedildi: {report.id} - {report.name}")
            return report.id

        except Exception as e:
            logger.error(f"Rapor kaydetme hatası: {e}", exc_info=True)
            db.session.rollback()
            raise

    @classmethod
    def load_report(cls, report_id: str, session: Any = None) -> 'ReportDesigner':
        """
        Kaydedilmiş raporu veritabanından yükler.

        Args:
            report_id: Rapor ID.
            session: DB session (opsiyonel).

        Returns:
            ReportDesigner: Yüklenmiş rapor instance'ı.

        Raises:
            ValueError: Rapor bulunamazsa.

        Example:
            >>> designer = ReportDesigner.load_report('abc-123')
        """
        from app.modules.rapor.models import SavedReport

        try:
            report = SavedReport.query.get(report_id)
            if not report:
                raise ValueError(f"Rapor bulunamadı: {report_id}")

            model_class = cls._get_model_by_name(report.model_name)
            config = json.loads(report.config_json)

            logger.info(f"Rapor yüklendi: {report_id} - {report.name}")
            return cls(model_class, config, session)

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Rapor yükleme hatası: {e}", exc_info=True)
            raise

    @classmethod
    def _get_model_by_name(cls, model_name: str) -> Type[BaseModel]:
        """
        Model adından SQLAlchemy model sınıfını döndürür.

        Args:
            model_name: Model sınıfının adı (örn. 'Fatura').

        Returns:
            Type[BaseModel]: Model sınıfı.

        Raises:
            ValueError: Model bulunamazsa.
        """
        # Bilinen modüllerde ara
        model_modules = [
            'app.modules.fatura.models',
            'app.modules.cari.models',
            'app.modules.stok.models',
            'app.modules.muhasebe.models',
            'app.modules.kasa.models',
            'app.modules.banka.models',
        ]

        for module_path in model_modules:
            try:
                import importlib
                module = importlib.import_module(module_path)
                if hasattr(module, model_name):
                    logger.debug(f"Model bulundu: {model_name} in {module_path}")
                    return getattr(module, model_name)
            except ImportError:
                continue

        raise ValueError(f"Model bulunamadı: {model_name}")

    # ------------------------------------------------------------------
    # SCHEDULED REPORTS
    # ------------------------------------------------------------------

    def schedule_report(
        self,
        user_id: str,
        schedule_type: str = 'daily',
        recipients: Optional[List[str]] = None,
        format_type: str = 'excel'
    ) -> str:
        """
        Raporu zamanlar ve otomatik e-posta gönderimini ayarlar.

        Args:
            user_id: Kullanıcı ID.
            schedule_type: Zamanlama tipi ('daily', 'weekly', 'monthly').
            recipients: E-posta adresleri listesi.
            format_type: Export formatı ('excel', 'csv').

        Returns:
            str: Oluşturulan schedule ID.

        Raises:
            Exception: Veritabanı hatası.

        Example:
            >>> schedule_id = designer.schedule_report(
            ...     user_id='abc-123',
            ...     schedule_type='weekly',
            ...     recipients=['boss@company.com']
            ... )
        """
        from app.modules.rapor.models import ScheduledReport
        from app.extensions import db

        try:
            schedule = ScheduledReport(
                report_config=json.dumps(self.config),
                model_name=self.model.__name__,
                schedule_type=schedule_type,
                recipients=json.dumps(recipients or []),
                export_format=format_type,
                user_id=user_id,
                is_active=True
            )

            db.session.add(schedule)
            db.session.commit()

            logger.info(f"Rapor zamanlandı: {schedule.id} ({schedule_type})")
            return schedule.id

        except Exception as e:
            logger.error(f"Rapor zamanlama hatası: {e}", exc_info=True)
            db.session.rollback()
            raise

    @staticmethod
    def run_scheduled_report(schedule_id: str) -> None:
        """
        Zamanlanmış raporu çalıştırır ve e-posta gönderir.

        Celery task olarak kullanılmak üzere tasarlanmıştır.

        Args:
            schedule_id: Zamanlanmış rapor ID.

        Example:
            >>> ReportDesigner.run_scheduled_report('sched-abc-123')
        """
        from app.modules.rapor.models import ScheduledReport

        try:
            schedule = ScheduledReport.query.get(schedule_id)
            if not schedule or not schedule.is_active:
                logger.warning(f"Zamanlama bulunamadı veya pasif: {schedule_id}")
                return

            config = json.loads(schedule.report_config)
            model_class = ReportDesigner._get_model_by_name(schedule.model_name)

            designer = ReportDesigner(model_class, config)

            # Export
            if schedule.export_format == 'excel':
                file_data = designer.export('excel')
                mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                extension = 'xlsx'
            else:
                file_data = designer.export('csv')
                mimetype = 'text/csv'
                extension = 'csv'

            # E-posta gönder
            recipients = json.loads(schedule.recipients or '[]')
            if recipients:
                from app.utils.email import send_email_with_attachment
                send_email_with_attachment(
                    recipients=recipients,
                    subject=f"Otomatik Rapor: {config['name']}",
                    body="Zamanlanmış raporunuz ektedir.",
                    attachment=file_data,
                    filename=f"{config['name']}.{extension}",
                    mimetype=mimetype
                )

            # İstatistik güncelle
            from app.extensions import db
            from datetime import timezone
            schedule.last_run_at = datetime.now(timezone.utc)
            schedule.run_count = (schedule.run_count or 0) + 1
            db.session.commit()

            logger.info(f"Zamanlanmış rapor çalıştırıldı: {schedule_id}")

        except Exception as e:
            logger.error(f"Zamanlanmış rapor çalıştırma hatası: {e}", exc_info=True)
            raise

    # ------------------------------------------------------------------
    # DRILL-DOWN
    # ------------------------------------------------------------------

    def create_drill_down_query(
        self,
        parent_filters: Dict[str, Any]
    ) -> 'ReportDesigner':
        """
        Özet rapor satırından detay rapora geçiş (drill-down).

        Üst rapordaki gruplama ve agregasyonları kaldırıp seçilen
        satırın filtre değerlerini uygular.

        Args:
            parent_filters: Üst rapordan gelen filtreler.
                Örn: {'region': 'Istanbul', 'month': 1}

        Returns:
            ReportDesigner: Detay rapor instance'ı.

        Example:
            >>> detail = designer.create_drill_down_query({
            ...     'region': 'Istanbul',
            ...     'month': 1
            ... })
            >>> data = detail.execute()
        """
        logger.debug(f"Drill-down query oluşturuluyor: {parent_filters}")

        # Yeni config oluştur (group_by kaldır, filters ekle)
        detail_config = self.config.copy()
        detail_config['format'] = 'list'
        detail_config.pop('group_by', None)
        detail_config.pop('aggregations', None)

        # Parent filtrelerini ekle
        existing_filters = list(detail_config.get('filters', []))
        for field, value in parent_filters.items():
            existing_filters.append({
                'field': field,
                'operator': 'equals',
                'value': value
            })

        detail_config['filters'] = existing_filters

        return ReportDesigner(self.model, detail_config, self.session)

    # ------------------------------------------------------------------
    # PERMISSIONS
    # ------------------------------------------------------------------

    def check_permission(self, user_id: str, action: str = 'view') -> bool:
        """
        Kullanıcının rapor iznini kontrol eder.

        Args:
            user_id: Kullanıcı ID.
            action: İzin tipi ('view', 'edit', 'delete').

        Returns:
            bool: İzin var mı?

        Example:
            >>> if designer.check_permission(user_id='abc', action='view'):
            ...     data = designer.execute()
        """
        try:
            from app.models.master.user import User
            from app.modules.rapor.models import ReportPermission

            user = User.query.get(user_id)
            if not user:
                logger.warning(f"Kullanıcı bulunamadı: {user_id}")
                return False

            # Admin her şeyi görebilir
            if getattr(user, 'is_admin', False) or getattr(user, 'is_super_admin', False):
                return True

            # Rapor public ise herkes görebilir
            if self.config.get('is_public') and action == 'view':
                return True

            # Kullanıcı permission tablosunda mı?
            permission = ReportPermission.query.filter_by(
                report_id=self.config.get('report_id'),
                user_id=user_id
            ).first()

            if not permission:
                return False

            if action == 'view':
                return bool(permission.can_view)
            elif action == 'edit':
                return bool(permission.can_edit)
            elif action == 'delete':
                return bool(permission.can_delete)

            return False

        except Exception as e:
            logger.error(f"İzin kontrol hatası: {e}", exc_info=True)
            return False

    # ------------------------------------------------------------------
    # VERSIONING
    # ------------------------------------------------------------------

    def save_version(self, user_id: str, change_note: str = "") -> str:
        """
        Mevcut rapor konfigürasyonunu versiyon olarak kaydeder.

        Args:
            user_id: Değişikliği yapan kullanıcı ID.
            change_note: Değişiklik açıklaması.

        Returns:
            str: Oluşturulan versiyon ID'si.

        Raises:
            Exception: Veritabanı hatası.

        Example:
            >>> version_id = designer.save_version(
            ...     user_id='abc-123',
            ...     change_note='Yeni filtre eklendi'
            ... )
        """
        from app.modules.rapor.models import ReportVersion
        from app.extensions import db

        try:
            # Mevcut en yüksek versiyon numarasını bul
            report_id = self.config.get('report_id')
            last_version = (
                ReportVersion.query
                .filter_by(report_id=report_id)
                .order_by(ReportVersion.version_number.desc())
                .first()
            )
            next_version = (last_version.version_number + 1) if last_version else 1

            version = ReportVersion(
                report_id=report_id,
                config_json=json.dumps(self.config),
                user_id=user_id,
                change_note=change_note,
                version_number=next_version
            )

            db.session.add(version)
            db.session.commit()

            logger.info(
                f"Rapor versiyonu kaydedildi: {version.id} "
                f"(v{next_version}, rapor={report_id})"
            )
            return version.id

        except Exception as e:
            logger.error(f"Versiyon kaydetme hatası: {e}", exc_info=True)
            db.session.rollback()
            raise

    def restore_version(self, version_id: str) -> 'ReportDesigner':
        """
        Raporu belirtilen eski versiyona geri döndürür.

        Args:
            version_id: Geri dönülecek versiyon ID'si.

        Returns:
            ReportDesigner: Eski konfigürasyon ile yeni instance.

        Raises:
            ValueError: Versiyon bulunamazsa.

        Example:
            >>> old_designer = designer.restore_version('ver-abc-123')
        """
        from app.modules.rapor.models import ReportVersion

        try:
            version = ReportVersion.query.get(version_id)
            if not version:
                raise ValueError(f"Version bulunamadı: {version_id}")

            old_config = json.loads(version.config_json)
            logger.info(f"Rapor versiyona geri döndürüldü: {version_id}")
            return ReportDesigner(self.model, old_config, self.session)

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Versiyon geri yükleme hatası: {e}", exc_info=True)
            raise

    # ------------------------------------------------------------------
    # QUERY OPTIMIZER
    # ------------------------------------------------------------------

    def optimize_query(self) -> Query:
        """
        Query'yi optimize eder (eager loading, gereksiz yüklerden kaçınma).

        İlişkili tabloları ``joinedload`` ile önceden yükleyerek
        N+1 problemini çözer.

        Returns:
            Query: Optimize edilmiş SQLAlchemy query nesnesi.

        Example:
            >>> optimized_query = designer.optimize_query()
        """
        try:
            if not self.query:
                self.build_query()

            # Eager loading (N+1 problemi çözümü)
            relationships = self.config.get('relationships', [])
            for rel in relationships:
                rel_attr = getattr(self.model, rel, None)
                if rel_attr is not None:
                    self.query = self.query.options(joinedload(rel_attr))
                else:
                    logger.warning(f"Model'de '{rel}' ilişkisi bulunamadı, atlanıyor.")

            logger.debug(
                f"Query optimize edildi: {len(relationships)} ilişki eager-load edildi"
            )
            return self.query

        except Exception as e:
            logger.error(f"Query optimize hatası: {e}", exc_info=True)
            raise

    # ------------------------------------------------------------------
    # USAGE ANALYTICS
    # ------------------------------------------------------------------

    def track_usage(self, user_id: str, execution_time: float) -> None:
        """
        Rapor kullanımını loglar (analytics için).

        Args:
            user_id: Kullanıcı ID.
            execution_time: Çalışma süresi saniye cinsinden.

        Example:
            >>> import time
            >>> start = time.time()
            >>> data = designer.execute()
            >>> designer.track_usage('abc-123', time.time() - start)
        """
        from app.modules.rapor.models import ReportUsageLog
        from app.extensions import db

        try:
            # Satır sayısını almak için execute çağrısını tekrarlamaktan kaçın
            row_count = 0
            if self.query:
                try:
                    row_count = self.query.count()
                except Exception:
                    pass

            log = ReportUsageLog(
                report_id=self.config.get('report_id'),
                user_id=user_id,
                execution_time=execution_time,
                row_count=row_count
            )

            db.session.add(log)
            db.session.commit()

            logger.debug(
                f"Kullanım kaydedildi: rapor={self.config.get('report_id')} "
                f"user={user_id} süre={execution_time:.3f}s satır={row_count}"
            )

        except Exception as e:
            logger.error(f"Kullanım loglama hatası: {e}", exc_info=True)
            # Loglama hatası rapor çalışmasını durdurmamalı
            try:
                db.session.rollback()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # CHART & EXPORT
    # ------------------------------------------------------------------

    def to_pandas(self) -> Any:
        """
        Sonuçları Pandas DataFrame'e çevirir.

        Returns:
            pandas.DataFrame: Rapor verisi.

        Example:
            >>> df = designer.to_pandas()
        """
        import pandas as pd

        data = self.execute()
        return pd.DataFrame(data)

    def get_chart_config(self) -> Optional[Dict[str, Any]]:
        """
        Chart.js için grafik konfigürasyonu döndürür.

        Returns:
            Optional[Dict[str, Any]]: Chart.js config dict veya None.

        Example:
            >>> chart = designer.get_chart_config()
        """
        chart_config = self.config.get('chart')

        if not chart_config or not chart_config.get('enabled'):
            return None

        data = self.execute()

        if not data:
            return None

        x_axis = chart_config.get('x_axis')
        y_axis = chart_config.get('y_axis')
        chart_type = chart_config.get('type', 'line')

        # Chart.js formatına çevir
        labels = [str(row.get(x_axis, '')) for row in data]
        values = [float(row.get(y_axis, 0)) for row in data]

        return {
            'type': chart_type,
            'data': {
                'labels': labels,
                'datasets': [{
                    'label': chart_config.get('label', y_axis),
                    'data': values,
                    'backgroundColor': chart_config.get('backgroundColor', 'rgba(75, 192, 192, 0.2)'),
                    'borderColor': chart_config.get('borderColor', 'rgb(75, 192, 192)'),
                    'borderWidth': 2
                }]
            },
            'options': {
                'responsive': True,
                'plugins': {
                    'legend': {
                        'display': True,
                        'position': 'top'
                    },
                    'title': {
                        'display': True,
                        'text': self.config.get('name', 'Rapor')
                    }
                }
            }
        }

    def export(self, format_type: str = 'excel') -> bytes:
        """
        Raporu belirtilen formatta dışa aktarır.

        Args:
            format_type: 'excel', 'csv' veya 'json'.

        Returns:
            bytes: Dosya içeriği.

        Raises:
            ValueError: Desteklenmeyen format.

        Example:
            >>> excel_bytes = designer.export('excel')
        """
        import io

        data = self.execute()

        if format_type == 'json':
            return json.dumps(data, ensure_ascii=False, default=str).encode('utf-8')

        elif format_type == 'csv':
            import csv
            output = io.StringIO()
            if data:
                writer = csv.DictWriter(output, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
            return output.getvalue().encode('utf-8')

        elif format_type == 'excel':
            try:
                import openpyxl
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = self.config.get('name', 'Rapor')[:31]

                if data:
                    # Başlık satırı
                    headers = list(data[0].keys())
                    ws.append(headers)
                    # Veri satırları
                    for row in data:
                        ws.append([str(v) if v is not None else '' for v in row.values()])

                output = io.BytesIO()
                wb.save(output)
                return output.getvalue()

            except ImportError:
                logger.warning("openpyxl bulunamadı, CSV formatına geçiliyor")
                return self.export('csv')

        else:
            raise ValueError(f"Desteklenmeyen export formatı: {format_type}")

    # ------------------------------------------------------------------
    # VALIDATION & DEBUG
    # ------------------------------------------------------------------

    def validate_config(self) -> Tuple[bool, str]:
        """
        Konfigürasyonun geçerli olup olmadığını kontrol eder.

        Returns:
            Tuple[bool, str]: (geçerli mi, mesaj).

        Example:
            >>> valid, msg = designer.validate_config()
        """
        # Zorunlu alanlar
        if not self.config.get('name'):
            return False, "Rapor adı zorunludur"

        # Filtre geçerliliği
        for filter_config in self.config.get('filters', []):
            if not filter_config.get('field'):
                return False, "Filtre alanı belirtilmeli"

            if not filter_config.get('operator'):
                return False, "Filtre operatörü belirtilmeli"

            if filter_config['operator'] not in self.OPERATORS:
                return False, f"Geçersiz operatör: {filter_config['operator']}"

        # Agregasyon geçerliliği
        for agg in self.config.get('aggregations', []):
            if agg.get('function') not in self.AGGREGATIONS:
                return False, f"Geçersiz agregasyon fonksiyonu: {agg.get('function')}"

        return True, "Geçerli"

    def get_sql(self) -> str:
        """
        Oluşturulan SQL sorgusunu string olarak döndürür (debug için).

        Returns:
            str: Derlenmiş SQL sorgusu.

        Example:
            >>> print(designer.get_sql())
        """
        if not self.query:
            self.build_query()

        from sqlalchemy.dialects import postgresql

        # Firebird için PostgreSQL dialect kullan (yakın syntax)
        compiled = self.query.statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True}
        )

        return str(compiled)


# ==========================================
# RAPOR ŞABLONLARI
# ==========================================

class ReportTemplates:
    """
    Hazır rapor konfigürasyon şablonları.

    Yaygın kullanılan rapor tiplerini hızlıca oluşturmak için
    fabrika metodları sağlar.

    Example:
        >>> config = ReportTemplates.monthly_sales()
        >>> designer = ReportDesigner(Fatura, config)
    """

    @staticmethod
    def monthly_sales(
        date_field: str = 'date',
        amount_field: str = 'amount'
    ) -> Dict[str, Any]:
        """
        Aylık satış raporu şablonu.

        Args:
            date_field: Tarih alanının adı.
            amount_field: Tutar alanının adı.

        Returns:
            Dict[str, Any]: Rapor konfigürasyonu.
        """
        return {
            "name": "Aylık Satış Raporu",
            "format": "summary",
            "fields": [
                {"name": "month", "label": "Ay", "type": "text"},
                {"name": "year", "label": "Yıl", "type": "number"},
                {"name": "total_amount", "label": "Toplam Tutar", "type": "currency"}
            ],
            "group_by": [
                f"EXTRACT(MONTH FROM {date_field})",
                f"EXTRACT(YEAR FROM {date_field})"
            ],
            "aggregations": [
                {"function": "sum", "field": amount_field, "alias": "total_amount"}
            ],
            "order_by": [
                {"field": "year", "direction": "DESC"},
                {"field": "month", "direction": "DESC"}
            ],
            "chart": {
                "enabled": True,
                "type": "line",
                "x_axis": "month",
                "y_axis": "total_amount"
            }
        }

    @staticmethod
    def top_customers(
        customer_field: str = 'customer_id',
        amount_field: str = 'amount',
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        En çok alışveriş yapan müşteriler şablonu.

        Args:
            customer_field: Müşteri alanının adı.
            amount_field: Tutar alanının adı.
            limit: Maksimum satır sayısı.

        Returns:
            Dict[str, Any]: Rapor konfigürasyonu.
        """
        return {
            "name": "En İyi Müşteriler",
            "format": "summary",
            "fields": [
                {"name": customer_field, "label": "Müşteri"},
                {"name": "total_amount", "label": "Toplam Tutar", "type": "currency"},
                {"name": "order_count", "label": "Sipariş Sayısı", "type": "number"}
            ],
            "group_by": [customer_field],
            "aggregations": [
                {"function": "sum", "field": amount_field, "alias": "total_amount"},
                {"function": "count", "field": "id", "alias": "order_count"}
            ],
            "order_by": [{"field": "total_amount", "direction": "DESC"}],
            "limit": limit,
            "chart": {
                "enabled": True,
                "type": "bar",
                "x_axis": customer_field,
                "y_axis": "total_amount"
            }
        }

    @staticmethod
    def aging_report(
        date_field: str = 'date',
        amount_field: str = 'balance'
    ) -> Dict[str, Any]:
        """
        Alacak yaşlandırma raporu şablonu (30-60-90 gün).

        Args:
            date_field: Belge tarih alanının adı.
            amount_field: Bakiye alanının adı.

        Returns:
            Dict[str, Any]: Rapor konfigürasyonu.
        """
        return {
            "name": "Alacak Yaşlandırma Raporu",
            "format": "summary",
            "fields": [
                {"name": "customer", "label": "Cari"},
                {"name": "current_amount", "label": "Cari (0-30 gün)", "type": "currency"},
                {"name": "days_30_60", "label": "30-60 gün", "type": "currency"},
                {"name": "days_60_90", "label": "60-90 gün", "type": "currency"},
                {"name": "days_90_plus", "label": "90+ gün", "type": "currency"}
            ],
            "group_by": ["customer_id"],
            "aggregations": [
                {
                    "function": "sum",
                    "field": (
                        f"CASE WHEN CURRENT_DATE - {date_field} <= 30 "
                        f"THEN {amount_field} ELSE 0 END"
                    ),
                    "alias": "current_amount"
                },
                {
                    "function": "sum",
                    "field": (
                        f"CASE WHEN CURRENT_DATE - {date_field} BETWEEN 31 AND 60 "
                        f"THEN {amount_field} ELSE 0 END"
                    ),
                    "alias": "days_30_60"
                },
                {
                    "function": "sum",
                    "field": (
                        f"CASE WHEN CURRENT_DATE - {date_field} BETWEEN 61 AND 90 "
                        f"THEN {amount_field} ELSE 0 END"
                    ),
                    "alias": "days_60_90"
                },
                {
                    "function": "sum",
                    "field": (
                        f"CASE WHEN CURRENT_DATE - {date_field} > 90 "
                        f"THEN {amount_field} ELSE 0 END"
                    ),
                    "alias": "days_90_plus"
                }
            ]
        }

    @staticmethod
    def stock_summary(
        quantity_field: str = 'quantity',
        value_field: str = 'value'
    ) -> Dict[str, Any]:
        """
        Stok özet raporu şablonu.

        Args:
            quantity_field: Miktar alanının adı.
            value_field: Değer alanının adı.

        Returns:
            Dict[str, Any]: Rapor konfigürasyonu.
        """
        return {
            "name": "Stok Özet Raporu",
            "format": "summary",
            "fields": [
                {"name": "category", "label": "Kategori"},
                {"name": "total_quantity", "label": "Toplam Miktar", "type": "number"},
                {"name": "total_value", "label": "Toplam Değer", "type": "currency"},
                {"name": "item_count", "label": "Stok Kalemi", "type": "number"}
            ],
            "group_by": ["category_id"],
            "aggregations": [
                {"function": "sum", "field": quantity_field, "alias": "total_quantity"},
                {"function": "sum", "field": value_field, "alias": "total_value"},
                {"function": "count", "field": "id", "alias": "item_count"}
            ],
            "order_by": [{"field": "total_value", "direction": "DESC"}],
            "chart": {
                "enabled": True,
                "type": "pie",
                "x_axis": "category",
                "y_axis": "total_value"
            }
        }


# ==========================================
# KULLANIM ÖRNEKLERİ
# ==========================================

def ornek_aylik_satis_raporu(tenant_db: Any) -> Tuple[List[Dict], Optional[Dict]]:
    """
    Örnek: Aylık satış raporu.

    Args:
        tenant_db: Tenant database session.

    Returns:
        Tuple[List[Dict], Optional[Dict]]: (veri, grafik konfigürasyonu).
    """
    from app.modules.fatura.models import Fatura

    config = {
        "name": "Aylık Satış Raporu",
        "description": "2024 yılı aylık satış analizi",
        "fields": [
            {"name": "ay", "label": "Ay"},
            {"name": "yil", "label": "Yıl"},
            {"name": "toplam_tutar", "label": "Toplam Tutar", "format": "currency"},
            {"name": "fatura_sayisi", "label": "Fatura Sayısı"}
        ],
        "filters": [
            {
                "field": "tarih",
                "operator": "between",
                "value": ["2024-01-01", "2024-12-31"]
            },
            {
                "field": "fatura_turu",
                "operator": "equals",
                "value": "SATIS"
            }
        ],
        "group_by": [
            "EXTRACT(MONTH FROM tarih)",
            "EXTRACT(YEAR FROM tarih)"
        ],
        "aggregations": [
            {"function": "sum", "field": "genel_toplam", "alias": "toplam_tutar"},
            {"function": "count", "field": "id", "alias": "fatura_sayisi"}
        ],
        "order_by": [
            {"field": "yil", "direction": "DESC"},
            {"field": "ay", "direction": "DESC"}
        ],
        "chart": {
            "enabled": True,
            "type": "line",
            "x_axis": "ay",
            "y_axis": "toplam_tutar",
            "label": "Aylık Satış (₺)"
        }
    }

    designer = ReportDesigner(Fatura, config, session=tenant_db)

    # Konfigürasyon geçerli mi?
    valid, message = designer.validate_config()
    if not valid:
        raise ValueError(f"Geçersiz konfigürasyon: {message}")

    # Raporu çalıştır
    data = designer.execute()

    # Grafik konfigürasyonu
    chart_config = designer.get_chart_config()

    return data, chart_config


def ornek_cari_bakiye_raporu(tenant_db: Any) -> List[Dict[str, Any]]:
    """
    Örnek: Borçlu cariler raporu.

    Args:
        tenant_db: Tenant database session.

    Returns:
        List[Dict[str, Any]]: Rapor verisi.
    """
    from app.modules.cari.models import CariHesap

    config = {
        "name": "Borçlu Cariler Raporu",
        "filters": [
            {"field": "borc_bakiye", "operator": "greater_than", "value": 1000},
            {"field": "aktif", "operator": "equals", "value": True}
        ],
        "order_by": [
            {"field": "borc_bakiye", "direction": "DESC"}
        ],
        "limit": 50
    }

    designer = ReportDesigner(CariHesap, config, session=tenant_db)
    return designer.execute()