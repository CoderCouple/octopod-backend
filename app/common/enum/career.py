from enum import Enum


class CareerEventType(str, Enum):
    """Type of career milestone event for an employee.

    Values:
        JOIN: The employee joined the organization.
        LEAVE: The employee left the organization.
        PROMOTION: The employee was promoted.
        TRANSFER: The employee transferred to a different team or
            location.
        TITLE_CHANGE: The employee's job title changed.
        MANAGER_CHANGE: The employee's reporting manager changed.
        ROLE_CHANGE: The employee's role or function changed.
    """

    JOIN = "join"
    LEAVE = "leave"
    PROMOTION = "promotion"
    TRANSFER = "transfer"
    TITLE_CHANGE = "title_change"
    MANAGER_CHANGE = "manager_change"
    ROLE_CHANGE = "role_change"
