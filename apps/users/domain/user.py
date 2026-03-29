import dataclasses
from datetime import datetime

@dataclasses.dataclass(frozen=True)
class User:
    id: str
    username: str
    email: str
    first_name: str
    last_name: str
    date_joined: datetime

    @classmethod
    def from_model(cls, model_instance) -> "User":
        return cls(
            id=str(model_instance.id),
            username=model_instance.username,
            email=model_instance.email,
            first_name=model_instance.first_name,
            last_name=model_instance.last_name,
            date_joined=model_instance.date_joined,
        )

    def __str__(self) -> str:
        return self.username
