from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect
from django.urls import path
from inventory import views

urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(template_name='inventory/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('setup-admin/', views.SetupAdminView.as_view(), name='setup_admin'),
    # Личный кабинет преподавателя
    path('dashboard/', views.TeacherDashboardView.as_view(), name='teacher_dashboard'),
    path('equipment/<int:equipment_id>/verify/', views.VerifyEquipmentView.as_view(), name='verify_equipment'),
    path('equipment/add/', views.EquipmentAddView.as_view(), name='equipment_add'),
    path('equipment/<int:equipment_id>/delete/', views.EquipmentDeleteView.as_view(), name='equipment_delete'),
    path('admin-panel/equipment/', views.EquipmentListView.as_view(), name='equipment_list'),
    # Пользователи
    path('register/', views.RegisterView.as_view(), name='register'),
    path('admin-panel/users/', views.UserListView.as_view(), name='user_list'),
    path('admin-panel/users/<int:user_id>/edit/', views.UserEditView.as_view(), name='user_edit'),
    path('admin-panel/users/<int:user_id>/delete/', views.UserDeleteView.as_view(), name='user_delete'),
    path('users/search/', views.UserSearchView.as_view(), name='user_search'),
    path('admin-panel/equipment/<int:equipment_id>/unassign/', views.EquipmentUnassignView.as_view(), name='equipment_unassign'),
    # Панель администратора
    path('admin-panel/', views.AdminDashboardView.as_view(), name='admin_dashboard'),
    path('admin-panel/offboarding/<int:user_id>/', views.OffboardingView.as_view(), name='offboarding'),
    path('admin-panel/equipment/<int:equipment_id>/history/', views.EquipmentHistoryView.as_view(), name='equipment_history'),
    path('admin-panel/equipment/<int:equipment_id>/hard-delete/', views.EquipmentHardDeleteView.as_view(), name='equipment_hard_delete'),
    path('', lambda req: redirect('teacher_dashboard')),
]