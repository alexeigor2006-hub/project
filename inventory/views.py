"""
views.py — Бэкенд-контроллеры проекта Cometa.
"""

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth import login
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.contrib import messages
from django.db import models

from .models import Equipment, Location, TransferHistory, User


# ─────────────────────────────────────────────
# ВСПОМОГАТЕЛЬНЫЕ МИКСИНЫ
# ─────────────────────────────────────────────

class TeacherRequiredMixin(LoginRequiredMixin):
    login_url = "/login/"


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    login_url = "/login/"

    def test_func(self):
        return self.request.user.is_admin


# ─────────────────────────────────────────────
# РЕГИСТРАЦИЯ (только для администраторов)
# ─────────────────────────────────────────────

class RegisterView(AdminRequiredMixin, View):
    """
    GET  /register/ — форма создания нового пользователя
    POST /register/ — сохранение нового пользователя
    """
    template_name = "inventory/register.html"

    def get(self, request):
        return render(request, self.template_name)

    @transaction.atomic
    def post(self, request):
        username   = request.POST.get("username", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name  = request.POST.get("last_name", "").strip()
        email      = request.POST.get("email", "").strip()
        role       = request.POST.get("role", User.Role.TEACHER)
        department = request.POST.get("department", "").strip()
        phone      = request.POST.get("phone", "").strip()
        password   = request.POST.get("password", "")
        password2  = request.POST.get("password2", "")

        # Валидация
        if not username:
            messages.error(request, "Имя пользователя обязательно.")
            return render(request, self.template_name)

        if User.objects.filter(username=username).exists():
            messages.error(request, f"Пользователь «{username}» уже существует.")
            return render(request, self.template_name)

        if password != password2:
            messages.error(request, "Пароли не совпадают.")
            return render(request, self.template_name)

        if len(password) < 6:
            messages.error(request, "Пароль должен быть не менее 6 символов.")
            return render(request, self.template_name)

        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name,
            email=email,
            role=role,
            department=department,
            phone=phone,
        )
        messages.success(request, f"✓ Пользователь «{user.get_full_name() or username}» создан.")
        return redirect("user_list")


# ─────────────────────────────────────────────
# СПИСОК И УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ
# ─────────────────────────────────────────────

class UserListView(AdminRequiredMixin, View):
    """GET /admin-panel/users/ — список всех пользователей."""
    template_name = "inventory/user_list.html"

    def get(self, request):
        users = User.objects.filter(is_active=True).order_by("last_name", "first_name")
        context = {
            "users": users,
            "total": users.count(),
            "active": users.filter(status=User.Status.ACTIVE).count(),
            "offboarding": users.filter(status=User.Status.OFFBOARDING).count(),
        }
        return render(request, self.template_name, context)


class UserEditView(AdminRequiredMixin, View):
    """
    GET  /admin-panel/users/<id>/edit/ — форма редактирования
    POST /admin-panel/users/<id>/edit/ — сохранение изменений
    """
    template_name = "inventory/user_edit.html"

    def get(self, request, user_id):
        employee = get_object_or_404(User, pk=user_id)
        return render(request, self.template_name, {"employee": employee})

    @transaction.atomic
    def post(self, request, user_id):
        employee = get_object_or_404(User, pk=user_id)

        employee.first_name = request.POST.get("first_name", "").strip()
        employee.last_name  = request.POST.get("last_name", "").strip()
        employee.email      = request.POST.get("email", "").strip()
        employee.role       = request.POST.get("role", employee.role)
        employee.status     = request.POST.get("status", employee.status)
        employee.department = request.POST.get("department", "").strip()
        employee.phone      = request.POST.get("phone", "").strip()

        # Смена пароля (опционально)
        new_password = request.POST.get("new_password", "").strip()
        if new_password:
            if len(new_password) < 6:
                messages.error(request, "Пароль должен быть не менее 6 символов.")
                return render(request, self.template_name, {"employee": employee})
            employee.set_password(new_password)

        employee.save()
        messages.success(request, f"✓ Данные пользователя обновлены.")
        return redirect("user_list")


class UserDeleteView(AdminRequiredMixin, View):
    """POST /admin-panel/users/<id>/delete/ — деактивация пользователя."""

    def post(self, request, user_id):
        employee = get_object_or_404(User, pk=user_id)

        # Нельзя удалить самого себя
        if employee == request.user:
            messages.error(request, "Нельзя удалить собственный аккаунт.")
            return redirect("user_list")

        # Проверяем есть ли за ним ТМЦ
        eq_count = employee.equipment_set.filter(is_active=True).count()
        if eq_count > 0:
            messages.error(
                request,
                f"Нельзя удалить: за сотрудником числится {eq_count} единиц ТМЦ. "
                f"Сначала открепите или передайте оборудование."
            )
            return redirect("user_list")

        name = employee.get_full_name() or employee.username
        employee.delete()
        messages.success(request, f"Пользователь «{name}» удалён.")
        return redirect("user_list")


# ─────────────────────────────────────────────
# ЛИЧНЫЙ КАБИНЕТ ПРЕПОДАВАТЕЛЯ
# ─────────────────────────────────────────────

class TeacherDashboardView(TeacherRequiredMixin, View):
    template_name = "inventory/teacher_dashboard.html"

    def get(self, request):
        
        equipment_qs = (
            Equipment.objects
            .filter(assigned_to=request.user, is_active=True)
            .select_related("location")
            .order_by("category", "name")
        )

        needs_check = [e for e in equipment_qs if e.needs_verification]
        up_to_date  = [e for e in equipment_qs if not e.needs_verification]

        # Списки для модального окна «Передать»
        all_users   = User.objects.filter(is_active=True).exclude(pk=request.user.pk)
        locations   = Location.objects.all().order_by("name")

        context = {
            "equipment_needs_check": needs_check,
            "equipment_up_to_date":  up_to_date,
            "total_count":           equipment_qs.count(),
            "needs_check_count":     len(needs_check),
            "all_users":             all_users,
            "locations":             locations,
            "recent_history": (
                TransferHistory.objects
                .filter(performed_by=request.user)
                .select_related("equipment", "to_user", "to_location")
                .order_by("-timestamp")[:10]
            ),
        }
        return render(request, self.template_name, context)


class VerifyEquipmentView(TeacherRequiredMixin, View):
    """
    POST /equipment/<id>/verify/
    action: present | lost | moved | writeoff | transfer
    """

    def post(self, request, equipment_id):
        equipment = get_object_or_404(
            Equipment,
            pk=equipment_id,
            assigned_to=request.user,
            is_active=True,
        )

        action  = request.POST.get("action")
        comment = request.POST.get("comment", "").strip()

        if action == "present":
            self._handle_present(request, equipment, comment)
        elif action == "lost":
            self._handle_lost(request, equipment, comment)
        elif action == "moved":
            self._handle_moved(
                request, equipment, comment,
                request.POST.get("location_id"),
                request.POST.get("transfer_to"),
            )
        elif action == "writeoff":
            self._handle_writeoff(request, equipment, comment)
        elif action == "transfer":
            self._handle_transfer(request, equipment, comment, request.POST.get("transfer_to"))
        else:
            messages.error(request, "Неизвестное действие.")

        return redirect("teacher_dashboard")

    @transaction.atomic
    def _handle_present(self, request, equipment, comment):
        equipment.last_verified_at = timezone.now()
        equipment.last_verified_by = request.user
        equipment.save(update_fields=["last_verified_at", "last_verified_by"])
        TransferHistory.objects.create(
            equipment=equipment,
            event_type=TransferHistory.EventType.VERIFIED,
            performed_by=request.user,
            comment=comment or "Самостоятельная инвентаризация",
        )
        messages.success(request, f"✓ «{equipment.name}» — наличие подтверждено.")

    @transaction.atomic
    def _handle_lost(self, request, equipment, comment):
        TransferHistory.objects.create(
            equipment=equipment,
            event_type=TransferHistory.EventType.REPORTED_LOST,
            performed_by=request.user,
            from_user=request.user,
            comment=comment or "Сообщено об утере",
        )
        equipment.assigned_to = None
        equipment.last_verified_at = timezone.now()
        equipment.last_verified_by = request.user
        equipment.save(update_fields=["assigned_to", "last_verified_at", "last_verified_by"])
        messages.warning(request, f"⚠ «{equipment.name}» отмечено как утерянное.")

    @transaction.atomic
    def _handle_writeoff(self, request, equipment, comment):
        """Преподаватель инициирует списание — помечает для администратора."""
        TransferHistory.objects.create(
            equipment=equipment,
            event_type=TransferHistory.EventType.WRITTEN_OFF,
            performed_by=request.user,
            from_user=request.user,
            comment=comment or "Запрос на списание от сотрудника",
        )
        # Открепляем, помечаем как неактивное
        equipment.assigned_to = None
        equipment.is_active = False
        equipment.condition = Equipment.Condition.WRITTEN_OFF
        equipment.last_verified_at = timezone.now()
        equipment.last_verified_by = request.user
        equipment.save(update_fields=[
            "assigned_to", "is_active", "condition",
            "last_verified_at", "last_verified_by"
        ])
        messages.info(request, f"📋 «{equipment.name}» отправлено на списание.")

    @transaction.atomic
    def _handle_transfer(self, request, equipment, comment, transfer_to_id):
        """Передача оборудования другому сотруднику."""
        if not transfer_to_id:
            messages.error(request, "Укажите сотрудника для передачи.")
            return

        try:
            new_user = User.objects.get(pk=transfer_to_id, is_active=True)
        except User.DoesNotExist:
            messages.error(request, "Сотрудник не найден.")
            return

        old_user = equipment.assigned_to
        TransferHistory.objects.create(
            equipment=equipment,
            event_type=TransferHistory.EventType.TRANSFERRED,
            performed_by=request.user,
            from_user=old_user,
            to_user=new_user,
            comment=comment or f"Передача от {old_user} к {new_user}",
        )
        equipment.assigned_to = new_user
        equipment.last_verified_at = timezone.now()
        equipment.last_verified_by = request.user
        equipment.save(update_fields=["assigned_to", "last_verified_at", "last_verified_by"])
        messages.success(request, f"↗ «{equipment.name}» передано сотруднику {new_user.get_full_name()}.")

    @transaction.atomic
    def _handle_moved(self, request, equipment, comment, location_id, transfer_to_id):
        old_location = equipment.location
        old_user = equipment.assigned_to
        new_location = None
        new_user = None
        event_type = TransferHistory.EventType.MOVED

        # Местоположение — текстом
        location_name = request.POST.get("location_name", "").strip()
        if location_name:
            new_location, _ = Location.objects.get_or_create(name=location_name)
            equipment.location = new_location

        # Сотрудник — поиск по имени или логину
        transfer_to_name = request.POST.get("transfer_to_name", "").strip()
        transfer_to_id = request.POST.get("transfer_to", "").strip()

        if transfer_to_id:
            try:
                new_user = User.objects.get(pk=transfer_to_id, is_active=True)
            except User.DoesNotExist:
                pass

        if not new_user and transfer_to_name:
            # Ищем по логину или имени
            new_user = User.objects.filter(
                is_active=True
            ).filter(
                models.Q(username__icontains=transfer_to_name) |
                models.Q(first_name__icontains=transfer_to_name) |
                models.Q(last_name__icontains=transfer_to_name)
            ).first()

            if not new_user:
                messages.error(request, f"Сотрудник «{transfer_to_name}» не найден.")
                return

        if new_user:
            equipment.assigned_to = new_user
            event_type = TransferHistory.EventType.TRANSFERRED

        equipment.last_verified_at = timezone.now()
        equipment.last_verified_by = request.user
        equipment.save(update_fields=[
            "assigned_to", "location",
            "last_verified_at", "last_verified_by"
        ])
        TransferHistory.objects.create(
            equipment=equipment,
            event_type=event_type,
            performed_by=request.user,
            from_user=old_user,
            to_user=new_user,   
            from_location=old_location,
            to_location=new_location,
            comment=comment,
        )
        messages.success(request, f"↗ «{equipment.name}» — перемещение сохранено.")


# ─────────────────────────────────────────────
# ПАНЕЛЬ АДМИНИСТРАТОРА
# ─────────────────────────────────────────────

class AdminDashboardView(AdminRequiredMixin, View):
    template_name = "inventory/admin_dashboard.html"

    def get(self, request):
        context = {
            "total_equipment":    Equipment.objects.filter(is_active=True).count(),
            "unassigned":         Equipment.objects.filter(is_active=True, assigned_to=None).count(),
            "total_users":        User.objects.filter(is_active=True).count(),
            "offboarding_users":  User.objects.filter(status=User.Status.OFFBOARDING),
            "recent_history":     TransferHistory.objects.select_related(
                                      "equipment", "performed_by"
                                  ).order_by("-timestamp")[:20],
        }
        return render(request, self.template_name, context)


class OffboardingView(AdminRequiredMixin, View):
    template_name = "inventory/offboarding.html"

    def get(self, request, user_id):
        employee = get_object_or_404(User, pk=user_id)
        equipment_list = Equipment.objects.filter(
            assigned_to=employee, is_active=True
        ).select_related("location")
        return render(request, self.template_name, {
            "employee": employee,
            "equipment_list": equipment_list,
            "equipment_count": equipment_list.count(),
        })

    def post(self, request, user_id):
        employee = get_object_or_404(User, pk=user_id)
        employee.status = User.Status.OFFBOARDING
        employee.save(update_fields=["status"])
        messages.info(request, f"Сотрудник {employee.get_full_name()} отмечен как «Увольняется».")
        return redirect("offboarding", user_id=user_id)


class EquipmentHistoryView(AdminRequiredMixin, View):
    template_name = "inventory/equipment_history.html"

    def get(self, request, equipment_id):
        equipment = get_object_or_404(Equipment, pk=equipment_id)
        history = equipment.history.select_related(
            "performed_by", "from_user", "to_user",
            "from_location", "to_location"
        ).order_by("-timestamp")
        return render(request, self.template_name, {
            "equipment": equipment,
            "history": history,
        })
class EquipmentAddView(TeacherRequiredMixin, View):
    """
    GET  /equipment/add/ — форма добавления ТМЦ
    POST /equipment/add/ — сохранение нового ТМЦ
    """
    template_name = "inventory/equipment_add.html"

    def get(self, request):
        locations = Location.objects.all().order_by("name")
        return render(request, self.template_name, {"locations": locations})

    @transaction.atomic
    def post(self, request):
        name             = request.POST.get("name", "").strip()
        inventory_number = request.POST.get("inventory_number", "").strip()
        category         = request.POST.get("category", Equipment.Category.OTHER)
        location_name    = request.POST.get("location_name", "").strip()
        description      = request.POST.get("description", "").strip()
        purchase_date    = request.POST.get("purchase_date") or None
        purchase_price   = request.POST.get("purchase_price") or None

        locations = Location.objects.all().order_by("name")

        if not name:
            messages.error(request, "Название обязательно.")
            return render(request, self.template_name, {"locations": locations})

        if not inventory_number:
            messages.error(request, "Инвентарный номер обязателен.")
            return render(request, self.template_name, {"locations": locations})

        if Equipment.objects.filter(inventory_number=inventory_number).exists():
            messages.error(request, f"ТМЦ с номером «{inventory_number}» уже существует.")
            return render(request, self.template_name, {"locations": locations})

        location = None
        if location_name:
            location, _ = Location.objects.get_or_create(name=location_name)

        equipment = Equipment.objects.create(
            name=name,
            inventory_number=inventory_number,
            category=category,
            location=location,
            description=description,
            purchase_date=purchase_date,
            purchase_price=purchase_price,
            assigned_to=request.user,
            last_verified_at=timezone.now(),
            last_verified_by=request.user,
        )

        TransferHistory.objects.create(
            equipment=equipment,
            event_type=TransferHistory.EventType.ASSIGNED,
            performed_by=request.user,
            to_user=request.user,
            comment="Добавлено сотрудником",
        )

        messages.success(request, f"✓ «{equipment.name}» добавлено в ваш кабинет.")
        return redirect("teacher_dashboard")


class EquipmentDeleteView(TeacherRequiredMixin, View):
    """
    POST /equipment/<id>/delete/ — удаление ТМЦ из кабинета.
    Администратор может удалять любое, преподаватель — только своё.
    """

    @transaction.atomic
    def post(self, request, equipment_id):
        if request.user.is_admin:
            equipment = get_object_or_404(Equipment, pk=equipment_id)
        else:
            equipment = get_object_or_404(
                Equipment, pk=equipment_id, assigned_to=request.user
            )

        name = equipment.name
        TransferHistory.objects.create(
            equipment=equipment,
            event_type=TransferHistory.EventType.WRITTEN_OFF,
            performed_by=request.user,
            from_user=equipment.assigned_to,
            comment=request.POST.get("comment", "Удалено пользователем"),
        )
        equipment.is_active = False
        equipment.assigned_to = None
        equipment.condition = Equipment.Condition.WRITTEN_OFF
        equipment.save(update_fields=["is_active", "assigned_to", "condition"])

        messages.success(request, f"🗑 «{name}» удалено из учёта.")
        return redirect("teacher_dashboard")
class EquipmentListView(AdminRequiredMixin, View):
    template_name = "inventory/equipment_list.html"

    def get(self, request):
        filter_type = request.GET.get("filter", "all")
        
        qs = Equipment.objects.filter(is_active=True).select_related("assigned_to", "location")
        
        if filter_type == "unassigned":
            qs = qs.filter(assigned_to=None)
        elif filter_type == "needs_check":
            qs = [e for e in qs if e.needs_verification]
        
        qs = list(qs)
        
        context = {
            "equipment_list": qs,
            "filter_type": filter_type,
            "total": Equipment.objects.filter(is_active=True).count(),
            "unassigned": Equipment.objects.filter(is_active=True, assigned_to=None).count(),
            "needs_check": sum(1 for e in Equipment.objects.filter(is_active=True) if e.needs_verification),
        }
        return render(request, self.template_name, context)
class EquipmentHardDeleteView(AdminRequiredMixin, View):
    """POST /admin-panel/equipment/<id>/hard-delete/ — безвозвратное удаление ТМЦ."""

    @transaction.atomic
    def post(self, request, equipment_id):
        equipment = get_object_or_404(Equipment, pk=equipment_id)
        name = equipment.name
        inv = equipment.inventory_number
        # Удаляем всю историю и сам объект
        equipment.history.all().delete()
        equipment.delete()
        messages.success(request, f"🗑 «{name}» (№ {inv}) безвозвратно удалено.")
        return redirect(request.POST.get("next", "/admin-panel/equipment/?filter=unassigned"))
class UserSearchView(TeacherRequiredMixin, View):
    """GET /users/search/?q=... — поиск пользователей для автодополнения."""

    def get(self, request):
        q = request.GET.get("q", "").strip()
        if len(q) < 2:
            return JsonResponse({"users": []})

        users = User.objects.filter(
            is_active=True
        ).filter(
            models.Q(username__icontains=q) |
            models.Q(first_name__icontains=q) |
            models.Q(last_name__icontains=q)
        ).exclude(pk=request.user.pk)[:8]

        return JsonResponse({"users": [
            {"id": u.pk, "name": u.get_full_name() or u.username, "login": u.username}
            for u in users
        ]})
class EquipmentUnassignView(AdminRequiredMixin, View):
    """POST /admin-panel/equipment/<id>/unassign/ — открепить ТМЦ от сотрудника."""

    @transaction.atomic
    def post(self, request, equipment_id):
        equipment = get_object_or_404(Equipment, pk=equipment_id, is_active=True)
        old_user = equipment.assigned_to

        TransferHistory.objects.create(
            equipment=equipment,
            event_type=TransferHistory.EventType.UNASSIGNED,
            performed_by=request.user,
            from_user=old_user,
            comment="Откреплено администратором",
        )

        equipment.assigned_to = None
        equipment.save(update_fields=["assigned_to"])
        messages.success(request, f"🔓 «{equipment.name}» откреплено от {old_user.get_full_name()}.")
        return redirect(request.POST.get("next", "/admin-panel/equipment/"))