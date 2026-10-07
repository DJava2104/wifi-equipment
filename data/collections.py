MINIO_BASE = "http://localhost:9000/img/"

def users(count):
    """ID пользователей, поставивших лайк (u1, u2, ... uN)."""
    return [f"u{i}" for i in range(1, count + 1)]

equipment_db = [
    {
        "id": 1,
        "title": "TP-Link Archer AX73",
        "standard": "Wi-Fi 6 (802.11ax)",
        "max_speed": 4804,
        "band": 5.0,
        "antennas": 6,
        "image_url": f"{MINIO_BASE}AX73.webp",
        "video_url": f"{MINIO_BASE}AX73.mp4",
        "likes": users(24),
        "status": "опубликован",
        "description": "Двухдиапазонный роутер класса AX5400: до 4804 Мбит/с в диапазоне 5 ГГц "
                       "и 574 Мбит/с на 2,4 ГГц. Шесть антенн и поддержка OFDMA уверенно "
                       "справляются с десятками подключённых устройств.",
    },
    {
        "id": 2,
        "title": "TP-Link Archer AX55",
        "standard": "Wi-Fi 6 (802.11ax)",
        "max_speed": 2402,
        "band": 5.0,
        "antennas": 4,
        "image_url": f"{MINIO_BASE}AX55.jpg",
        "video_url": f"{MINIO_BASE}AX55.mp4",
        "likes": users(18),
        "status": "опубликован",
        "description": "Доступный роутер класса AX3000 для квартиры. Четыре антенны дают "
                       "хорошее покрытие, а скорости хватает для видеозвонков, потокового "
                       "видео и нескольких смартфонов одновременно.",
    },
    {
        "id": 3,
        "title": "ASUS RT-AX86U",
        "standard": "Wi-Fi 6 (802.11ax)",
        "max_speed": 4804,
        "band": 5.0,
        "antennas": 3,
        "image_url": f"{MINIO_BASE}AX86U.jpeg",
        "video_url": f"{MINIO_BASE}AX86U.mp4",
        "likes": users(37),
        "status": "опубликован",
        "description": "Игровой роутер класса AX5700 с низкой задержкой и мощным процессором. "
                       "Приоритизирует игровой трафик и стабильно работает под большой "
                       "нагрузкой сети.",
    },
    {
        "id": 4,
        "title": "Xiaomi Router BE7000",
        "standard": "Wi-Fi 7 (802.11be)",
        "max_speed": 6933,
        "band": 5.0,
        "antennas": 6,
        "image_url": f"{MINIO_BASE}BE7000.jpg",
        "video_url": f"{MINIO_BASE}BE7000.mp4",
        "likes": users(12),
        "status": "опубликован",
        "description": "Роутер нового поколения с поддержкой Wi-Fi 7. Широкие каналы и "
                       "модуляция 4096-QAM дают заметный прирост скорости по сравнению "
                       "с Wi-Fi 6 при том же числе устройств.",
    },
    {
        "id": 5,
        "title": "Keenetic Giga KN-1011",
        "standard": "Wi-Fi 6 (802.11ax)",
        "max_speed": 1201,
        "band": 5.0,
        "antennas": 4,
        "image_url": f"{MINIO_BASE}KN-1011.jpg",
        "video_url": f"{MINIO_BASE}KN-1011.mp4",
        "likes": users(9),
        "status": "опубликован",
        "description": "Надёжный домашний роутер класса AX1800 с простой настройкой через "
                       "приложение. Подходит для небольших квартир, где не нужна "
                       "максимальная скорость.",
    },
    {
        "id": 6,
        "title": "ASUS ROG Rapture GT-BE98",
        "standard": "Wi-Fi 7 (802.11be)",
        "max_speed": 11529,
        "band": 6.0,
        "antennas": 8,
        "image_url": f"{MINIO_BASE}GT-BE98.png",
        "video_url": f"{MINIO_BASE}GT-BE98.mp4",
        "likes": users(6),
        "status": "опубликован",
        "description": "Флагманский игровой роутер класса BE25000. Работает в четырёх "
                       "диапазонах, включая 6 ГГц, и рассчитан на требовательные домашние "
                       "сети с большим числом устройств.",
    },
]
