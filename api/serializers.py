from models.equipment import Equipment


def equipment_serializer(equipment: Equipment) -> dict:
    return {
        "id_equipment": equipment.id_equipment,
        "title": equipment.title,
        "standard": equipment.standard,
        "max_speed": equipment.max_speed,
        "band": equipment.band,
        "antennas": equipment.antennas,
        "frequency": equipment.frequency,
        "image_url": equipment.image_url,
        "video_url": equipment.video_url,
        "description": equipment.description,
        "status": equipment.status,
        "date_created": equipment.date_created,
        "creator": equipment.creator,
        "date_formed": equipment.date_formed,
        "date_completed": equipment.date_completed,
    }
