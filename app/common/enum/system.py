from enum import Enum


class EntityType(str, Enum):
    """Identifier for the type of entity tracked in the system."""

    DEVELOPER_PROFILE = "developer_profile"
