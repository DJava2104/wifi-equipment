from datetime import datetime

from pydantic import BaseModel, Field


class UserSchema(BaseModel):
    id_user: int = Field(description="Идентификатор пользователя")
    username: str = Field(description="Логин")


class AuthResponseSchema(BaseModel):
    user: UserSchema = Field(description="Аутентифицированный пользователь")


class EquipmentSchema(BaseModel):
    id_equipment: int = Field(description="Идентификатор услуги")
    title: str = Field(description="Название")
    standard: str | None = Field(default=None, description="Стандарт Wi-Fi")
    max_speed: int | None = Field(default=None, description="Макс. скорость, Мбит/с")
    band: str | None = Field(default=None, description="Диапазон (строка)")
    antennas: str | None = Field(default=None, description="Количество антенн")
    frequency: float | None = Field(default=None, description="Частота, ГГц")
    image_url: str | None = Field(default=None, description="Имя файла изображения в MinIO")
    video_url: str | None = Field(default=None, description="Имя файла видео в MinIO")
    description: str | None = Field(default=None, description="Описание")
    status: str = Field(description="черновик / опубликован / удален")
    date_created: datetime | None = Field(default=None, description="Дата создания")
    creator: str = Field(description="Логин создателя (заполняется из сессии)")
    date_formed: datetime | None = Field(default=None, description="Дата публикации")
    date_completed: datetime | None = Field(default=None, description="Дата удаления")


class EquipmentListItemSchema(EquipmentSchema):
    is_creator: int = Field(description="1 — текущий пользователь является создателем, иначе 0")


class FeedItemSchema(EquipmentSchema):
    like_count: int = Field(description="Количество лайков")
    is_liked: int = Field(description="1 — лайк текущего пользователя, иначе 0")


class LikeResponseSchema(BaseModel):
    like_count: int = Field(description="Количество лайков после изменения")
