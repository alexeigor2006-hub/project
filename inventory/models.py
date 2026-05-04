"""
models.py — Ядро базы данных проекта Cometa
Описывает все сущности системы учёта ТМЦ.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


# ─────────────────────────────────────────────
# ПОЛЬЗОВАТЕЛИ
# ─────────────────────────────────────────────

class User(AbstractUser):
    """
    Расширенная модель пользователя.
    Роль определяет, какой интерфейс видит пользователь.
    """

    class Role(models.TextChoices):
        TEACHER = "teacher", "Преподаватель"
        ADMIN = "admin", "Администратор"

    class Status(models.TextChoices):
        ACTIVE = "active", "Активен"
        OFFBOARDING = "offboarding", "Увольняется"
        DISMISSED = "dismissed", "Уволен"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.TEACHER,
        verbose_name="Роль",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name="Статус сотрудника",
    )
    department = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Кафедра / подразделение",
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Телефон",
    )

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN

    @property
    def is_offboarding(self):
        return self.status == self.Status.OFFBOARDING

    def get_equipment_count(self):
        """Количество ТМЦ, числящихся за сотрудником."""
        return self.equipment_set.filter(is_active=True).count()


# ─────────────────────────────────────────────
# МЕСТОПОЛОЖЕНИЯ (АУДИТОРИИ)
# ─────────────────────────────────────────────

class Location(models.Model):
    """
    Физическое местоположение оборудования.
    Например: «Аудитория 301», «Лаборатория ИТ», «Склад».
    """
    name = models.CharField(
        max_length=200,
        unique=True,
        verbose_name="Название",
    )
    building = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Корпус",
    )
    description = models.TextField(
        blank=True,
        verbose_name="Описание",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Местоположение"
        verbose_name_plural = "Местоположения"
        ordering = ["name"]

    def __str__(self):
        if self.building:
            return f"{self.name} ({self.building})"
        return self.name


# ─────────────────────────────────────────────
# ОБОРУДОВАНИЕ / ТМЦ
# ─────────────────────────────────────────────

class Equipment(models.Model):
    """
    Единица товарно-материальных ценностей (ТМЦ).
    Может быть закреплена за сотрудником и/или местоположением.
    """

    class Category(models.TextChoices):
        COMPUTER = "computer", "Компьютер / ПК"
        LAPTOP = "laptop", "Ноутбук"
        MONITOR = "monitor", "Монитор"
        PRINTER = "printer", "Принтер / МФУ"
        PROJECTOR = "projector", "Проектор"
        FURNITURE = "furniture", "Мебель"
        OTHER = "other", "Прочее"

    class Condition(models.TextChoices):
        GOOD = "good", "Исправно"
        NEEDS_REPAIR = "needs_repair", "Требует ремонта"
        BROKEN = "broken", "Неисправно"
        WRITTEN_OFF = "written_off", "Списано"

    # Основные поля
    name = models.CharField(max_length=300, verbose_name="Наименование")
    inventory_number = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Инвентарный номер",
    )
    category = models.CharField(
        max_length=30,
        choices=Category.choices,
        default=Category.OTHER,
        verbose_name="Категория",
    )
    condition = models.CharField(
        max_length=20,
        choices=Condition.choices,
        default=Condition.GOOD,
        verbose_name="Состояние",
    )
    description = models.TextField(blank=True, verbose_name="Описание / Примечания")

    # Привязки
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="equipment_set",
        verbose_name="Закреплено за",
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="equipment_set",
        verbose_name="Местоположение",
    )

    # Служебные поля
    is_active = models.BooleanField(default=True, verbose_name="Активно (не списано)")
    purchase_date = models.DateField(null=True, blank=True, verbose_name="Дата приобретения")
    purchase_price = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True,
        verbose_name="Балансовая стоимость (₽)",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Поля инвентаризации
    last_verified_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Дата последней проверки",
    )
    last_verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_equipment",
        verbose_name="Кто последний проверял",
    )

    class Meta:
        verbose_name = "Оборудование (ТМЦ)"
        verbose_name_plural = "Оборудование (ТМЦ)"
        ordering = ["category", "name"]

    def __str__(self):
        return f"{self.name} [{self.inventory_number}]"

    @property
    def needs_verification(self):
        """
        True, если с момента последней проверки прошло более 30 дней.
        Такие позиции подсвечиваются красным в интерфейсе.
        """
        if not self.last_verified_at:
            return True
        delta = timezone.now() - self.last_verified_at
        return delta.days > 30

    @property
    def days_since_verification(self):
        if not self.last_verified_at:
            return None
        return (timezone.now() - self.last_verified_at).days


# ─────────────────────────────────────────────
# ИСТОРИЯ ПЕРЕМЕЩЕНИЙ
# ─────────────────────────────────────────────

class TransferHistory(models.Model):
    """
    Лог каждого события с оборудованием:
    подтверждение наличия, перемещение, утеря, передача.
    """

    class EventType(models.TextChoices):
        VERIFIED = "verified", "Подтверждено наличие"
        TRANSFERRED = "transferred", "Передано сотруднику"
        MOVED = "moved", "Перемещено в другую аудиторию"
        REPORTED_LOST = "reported_lost", "Сообщено об утере"
        ASSIGNED = "assigned", "Закреплено (администратором)"
        UNASSIGNED = "unassigned", "Откреплено (администратором)"
        WRITTEN_OFF = "written_off", "Списано"

    equipment = models.ForeignKey(
        Equipment,
        on_delete=models.CASCADE,
        related_name="history",
        verbose_name="Оборудование",
    )
    event_type = models.CharField(
        max_length=30,
        choices=EventType.choices,
        verbose_name="Тип события",
    )

    # Кто инициировал событие
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="performed_transfers",
        verbose_name="Кто выполнил",
    )

    # От кого / кому (для передач между сотрудниками)
    from_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transfers_from",
        verbose_name="От кого",
    )
    to_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transfers_to",
        verbose_name="Кому",
    )

    # Местоположения (для перемещений между аудиториями)
    from_location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transfers_from",
        verbose_name="Откуда",
    )
    to_location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transfers_to",
        verbose_name="Куда",
    )

    comment = models.TextField(blank=True, verbose_name="Комментарий")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Дата и время")

    class Meta:
        verbose_name = "Запись истории"
        verbose_name_plural = "История перемещений"
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.get_event_type_display()} — {self.equipment} ({self.timestamp:%d.%m.%Y %H:%M})"
