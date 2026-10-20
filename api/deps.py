from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.users import Users


class CurrentUser:
    _instance = None
    USER_ID = 1
    USERNAME = "user_0"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def get_user(self, db: AsyncSession) -> Users:
        result = await db.execute(
            select(Users).where(Users.id_user == self.USER_ID)
        )
        return result.scalar_one()


def get_current_user() -> CurrentUser:
    return CurrentUser()
