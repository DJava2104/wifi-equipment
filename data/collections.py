equipment_db = [
    {
        "id": 1,
        "title": "TP-Link Archer AX73",
        "standard": "Wi-Fi 6 (802.11ax)",
        "max_speed": 4804,
        "band": "5 ГГц",
        "antennas": "6 антенн",
        "image_url": "http://localhost:9000/img/AX73.webp",
        "video_url": "http://localhost:9000/img/AX73.mp4",
        "likes": 24,
    },
    {
        "id": 2,
        "title": "TP-Link Archer AX55",
        "standard": "Wi-Fi 6 (802.11ax)",
        "max_speed": 2400,
        "band": "5 ГГц",
        "antennas": "4 антенны",
        "image_url": "http://localhost:9000/img/AX55.jpg",
        "video_url": "http://localhost:9000/img/AX55.mp4",
        "likes": 18,
    },
    {
        "id": 3,
        "title": "ASUS RT-AX86U",
        "standard": "Wi-Fi 6 (802.11ax)",
        "max_speed": 5700,
        "band": "5 ГГц",
        "antennas": "4 антенны",
        "image_url": "http://localhost:9000/img/AX86U.jpeg",
        "video_url": "http://localhost:9000/img/AX86U.mp4",
        "likes": 37,
    },
    {
        "id": 4,
        "title": "Xiaomi Router BE7000",
        "standard": "Wi-Fi 7 (802.11be)",
        "max_speed": 6933,
        "band": "5 ГГц",
        "antennas": "6 антенн",
        "image_url": "http://localhost:9000/img/BE7000.jpg",
        "video_url": "http://localhost:9000/img/BE7000.mp4",
        "likes": 12,
    },
    {
        "id": 5,
        "title": "Keenetic Giga KN-1011",
        "standard": "Wi-Fi 6 (802.11ax)",
        "max_speed": 1800,
        "band": "5 ГГц",
        "antennas": "4 антенны",
        "image_url": "http://localhost:9000/img/KN-1011.jpg",
        "video_url": "http://localhost:9000/img/KN-1011.mp4",
        "likes": 9,
    },
    {
        "id": 6,
        "title": "ROG Rapture GT-BE98",
        "standard": "Wi-Fi 6 (802.11ax)",
        "max_speed": 1200,
        "band": "5 ГГц",
        "antennas": "4 антенны",
        "image_url": "http://localhost:9000/img/GT-BE98.png",
        "video_url": "http://localhost:9000/img/GT-BE98.mp4",
        "likes": 6,
    },
]


def get_filtered_equipment(speed_min=None):
    if speed_min is None:
        return equipment_db
    return [e for e in equipment_db if e["max_speed"] >= speed_min]