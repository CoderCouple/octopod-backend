from enum import Enum


class EntityType(str, Enum):
    """Identifier for the type of entity tracked in the event log.

    Values:
        ORG: An organization entity.
        EMPLOYEE: An employee entity.
        EMPLOYMENT: An employment record entity.
        REPORTING_RELATIONSHIP: A reporting relationship entity.
        CAREER_EVENT: A career event entity.
        REPORTING_CLAIM: A reporting claim entity.
    """

    ORG = "org"
    EMPLOYEE = "employee"
    EMPLOYMENT = "employment"
    REPORTING_RELATIONSHIP = "reporting_relationship"
    CAREER_EVENT = "career_event"
    REPORTING_CLAIM = "reporting_claim"
    DEVELOPER_PROFILE = "developer_profile"


class VisibilityLevel(int, Enum):
    """Access level controlling what data an actor can view.

    Higher levels grant access to increasingly sensitive information.

    Values:
        NONE: No visibility -- the actor cannot view any data (``0``).
        BASIC: Basic visibility -- limited data access (``1``).
        EXTENDED: Extended visibility -- broader data access (``2``).
        FULL: Full visibility -- unrestricted data access (``3``).
    """

    NONE = 0
    BASIC = 1
    EXTENDED = 2
    FULL = 3
