# Wi-Fi Equipment — REST API

Веб-сервис (REST API) для каталога Wi-Fi оборудования. Бэкенд для SPA: список устройств с фильтрацией, лента, черновики, публикация, лайки, мягкое удаление и загрузка файлов в MinIO.

## Таблицы БД

### equipment

| Поле | Тип | Описание |
|---|---|---|
| id_equipment | INTEGER PK | Идентификатор |
| title | VARCHAR(100) | Название |
| standard | VARCHAR(50) | Стандарт Wi-Fi |
| max_speed | INTEGER | Макс. скорость, Мбит/с |
| band | VARCHAR(20) | Диапазон (строка) |
| antennas | VARCHAR(30) | Количество антенн |
| frequency | FLOAT | Частота, ГГц |
| image_url | VARCHAR(255) | Имя файла изображения в MinIO (латиница) |
| video_url | VARCHAR(255) | Имя файла видео в MinIO (латиница) |
| description | TEXT | Описание |
| date_created | TIMESTAMP | Дата создания |
| creator | VARCHAR(50) | Создатель |
| date_formed | TIMESTAMP | Дата публикации |
| date_completed | TIMESTAMP | Дата удаления |
| status | VARCHAR(20) | черновик / опубликован / удален |

### users

| Поле | Тип | Описание |
|---|---|---|
| id_user | INTEGER PK | Идентификатор |
| username | VARCHAR(50) UNIQUE | Логин |
| password | VARCHAR(255) | Пароль |

### likes

| Поле | Тип | Описание |
|---|---|---|
| id_user | INTEGER FK | Пользователь |
| id_equipment | INTEGER FK | Устройство |

---

## HTTP-методы

Все адреса начинаются с `/api`.

### Домен устройства

| Метод | URL | Описание |
|---|---|---|
| GET | `/api/equipments?freq_min=&freq_max=` | Список опубликованных с фильтрацией по частоте. Поле `is_creator` (0/1) — совпадает ли создатель с текущим пользователем |
| GET | `/api/equipment?next=true` | Лента с начала: первое опубликованное + `like_count` + `is_liked` (0/1) |
| GET | `/api/equipment/{id_equipment}?next=true` | Лента по ид: устройство + `like_count` + `is_liked`. `next=true` — следующее после указанного (цикл) |
| GET | `/api/equipment/draft` | Черновик текущего пользователя (не более 1 записи) |
| POST | `/api/equipment` | Создать черновик. Form: `title`, `image` (файл), `video` (файл). Файлы кладутся в MinIO, их имена (латиница, uuid) — в БД |
| PUT | `/api/equipment/{id_equipment}` | Опубликовать (только свой черновик). Form: `description`, `frequency`, `standard`, `max_speed`, `antennas` |
| DELETE | `/api/equipment/{id_equipment}` | Soft delete (только свои). Ответ: 200, пустое тело |
| POST | `/api/equipment/{id_equipment}` | Лайк. Form: `like` (1=поставить, 0=отменить). Ответ: `{like_count}` |

### Домен пользователя

| Метод | URL | Описание |
|---|---|---|
| POST | `/api/register` | Регистрация. Form: `username`, `password` |
| POST | `/api/login` | Аутентификация (заглушка) |
| POST | `/api/logout` | Деавторизация (заглушка) |

---

## Текущий пользователь

Пользователь-создатель зафиксирован константой в функции-singleton `get_current_user()` (`api/deps.py`): `USER_ID = 1`, `USERNAME = "user_0"`. Эта функция используется во всех методах домена устройства.

## Статусы

`черновик → опубликован → удалён`. Вернуть в черновик нельзя: у создателя два разных метода (`POST` — создание черновика, `PUT` — публикация). Записи в статусе `удален` на клиент не передаются. Системные поля (ид, статус, создатель, даты) с клиента не передаются — вычисляются на бэкенде.

## Запуск

```bash
docker compose up -d
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload
```

MinIO-бакет создаётся автоматически при старте приложения.
