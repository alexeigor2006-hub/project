# ☄ Cometa — Система учёта ТМЦ

## Архитектура проекта

```
cometa/
│
├── cometa/                        # Конфигурационный пакет Django
│   ├── settings.py                # Настройки (БД, apps, auth и т.д.)
│   ├── urls.py                    # Главный роутер URL
│   └── wsgi.py                    # Точка входа для WSGI-сервера
│
├── inventory/                     # Основное Django-приложение
│   ├── models.py                  # ★ Модели БД: User, Equipment, Location, TransferHistory
│   ├── views.py                   # ★ Контроллеры: дашборд преподавателя, verify, admin
│   ├── urls.py                    # URL маршруты приложения
│   ├── forms.py                   # Django-формы (этап 2)
│   ├── admin.py                   # Регистрация моделей в Django admin
│   ├── apps.py                    # Конфигурация приложения
│   │
│   ├── templates/inventory/
│   │   ├── teacher_dashboard.html # ★ Личный кабинет преподавателя
│   │   ├── admin_dashboard.html   # Панель администратора (этап 2)
│   │   ├── offboarding.html       # Обходной лист (этап 2)
│   │   ├── equipment_history.html # История ТМЦ (этап 2)
│   │   └── login.html             # Страница входа
│   │
│   └── migrations/                # Миграции Django (auto-generated)
│
├── static/
│   ├── css/                       # Кастомные стили (при необходимости)
│   └── js/                        # Кастомные скрипты
│
├── db.sqlite3                     # База данных (создаётся после migrate)
├── manage.py
└── requirements.txt
```

## ER-диаграмма

```
User ─────────────────── Equipment ─────── Location
 │  role, status          │  inventory_number    name, building
 │                        │  category, condition
 │                        │  last_verified_at
 │                        │
 └── TransferHistory ─────┘
      event_type
      performed_by → User
      from_user → User
      to_user → User
      from_location → Location
      to_location → Location
      timestamp, comment
```

## Стек технологий

| Слой         | Технология                              | Обоснование                               |
|-------------|------------------------------------------|-------------------------------------------|
| Backend     | **Django 4.x**                           | Встроенные auth, ORM, admin, миграции     |
| Database    | **SQLite → PostgreSQL**                  | SQLite для MVP, переход одной строкой     |
| Frontend    | **Django Templates + custom CSS**        | Быстро, без сборки, SSR из коробки        |
| Auth        | **Django built-in + AbstractUser**       | Готовая система сессий и permissions      |
| Deployment  | **Gunicorn + Nginx** (или Railway/Fly.io)| Стандартный Django production stack       |

## Быстрый старт

```bash
# 1. Создать виртуальное окружение
python -m venv .venv && source .venv/bin/activate

# 2. Установить зависимости
pip install django

# 3. Применить миграции
python manage.py makemigrations inventory
python manage.py migrate

# 4. Создать суперпользователя (администратора)
python manage.py createsuperuser

# 5. Запустить сервер разработки
python manage.py runserver
```

## Роли пользователей

| Роль          | Доступ                                                        |
|---------------|---------------------------------------------------------------|
| Преподаватель | `/dashboard/` — список своих ТМЦ, кнопки инвентаризации      |
| Администратор | + `/admin-panel/` — CRUD оборудования, offboarding, история  |

## Следующие этапы разработки

**Этап 2 — Панель администратора**
- [ ] CRUD для оборудования и пользователей
- [ ] Закрепление/открепление ТМЦ
- [ ] Обходной лист (offboarding template)
- [ ] Поиск и фильтрация по всей базе

**Этап 3 — Расширенные функции**
- [ ] QR-коды на инвентарные карточки (qrcode lib)
- [ ] Экспорт в Excel (openpyxl)
- [ ] Email-уведомления (Django email backend)
- [ ] REST API (DRF) для мобильного приложения

**Миграция на PostgreSQL** — изменить 2 строки в settings.py:
```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "cometa_db",
        "USER": "cometa_user",
        "PASSWORD": "...",
        "HOST": "localhost",
        "PORT": "5432",
    }
}
```
