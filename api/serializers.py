from models.routers import Router


def router_serializer(router: Router) -> dict:
    return {
        "id_routers": router.id_routers,
        "title": router.title,
        "standard": router.standard,
        "max_speed": router.max_speed,
        "band": router.band,
        "antennas": router.antennas,
        "frequency": router.frequency,
        "image_url": router.image_url,
        "video_url": router.video_url,
        "description": router.description,
        "status": router.status,
        "date_created": router.date_created,
        "creator": router.creator,
        "date_formed": router.date_formed,
        "date_completed": router.date_completed,
    }
