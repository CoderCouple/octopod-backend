from enum import Enum


class RelationshipType(str, Enum):
    """Type of reporting relationship between an employee and a manager.

    Values:
        SOLID_LINE: A direct, primary reporting relationship.
        DOTTED_LINE: A secondary or indirect reporting relationship.
        MATRIX: A matrix reporting relationship where the employee
            reports to multiple managers.
    """

    SOLID_LINE = "solid_line"
    DOTTED_LINE = "dotted_line"
    MATRIX = "matrix"


class RelationshipStatus(str, Enum):
    """Verification status of a reporting relationship.

    Indicates how confidently the system has established the
    relationship's validity.

    Values:
        CONFIRMED: The relationship has been verified by both parties.
        PROBABLE: The relationship is likely but not yet fully confirmed.
        WEAK: The relationship has minimal supporting evidence.
    """

    CONFIRMED = "confirmed"
    PROBABLE = "probable"
    WEAK = "weak"
