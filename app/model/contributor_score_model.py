import uuid

from sqlalchemy import TIMESTAMP, Column, Integer, Numeric, String, func

from app.db.base import Base


def generate_prefixed_uuid():
    """Generate a UUID4 string prefixed with ``cs_``.

    Returns:
        A string in the form ``"cs_<uuid4>"``, used as the default
        primary key for the ``ContributorScore`` model.
    """
    return f"cs_{uuid.uuid4()}"


class ContributorScore(Base):
    """SQLAlchemy model for the ``contributor_score`` table.

    Tracks cumulative reputation metrics for each actor (user) based
    on their claim-related activity, including submissions,
    verifications, confirmations, and rejections.

    Table name:
        ``contributor_score``

    Primary key:
        ``id`` -- prefixed UUID (``cs_<uuid4>``).

    Key columns:
        * ``actor_id`` -- unique identifier of the actor (user).
        * ``total_claims_submitted`` -- count of claims submitted.
        * ``total_claims_verified`` -- count of claims verified.
        * ``total_confirmations_given`` -- count of confirmations given.
        * ``total_rejections_given`` -- count of rejections given.
        * ``visibility_level`` -- integer level controlling what data
          the actor can access.
        * ``raw_score`` -- computed numeric reputation score.
        * ``created_at`` / ``updated_at`` -- timestamp audit fields.
    """

    __tablename__ = "contributor_score"

    id = Column(String(), primary_key=True, default=generate_prefixed_uuid, nullable=False)
    actor_id = Column(String(), unique=True, nullable=False)
    total_claims_submitted = Column(Integer, default=0, nullable=False)
    total_claims_verified = Column(Integer, default=0, nullable=False)
    total_confirmations_given = Column(Integer, default=0, nullable=False)
    total_rejections_given = Column(Integer, default=0, nullable=False)
    visibility_level = Column(Integer, default=0, nullable=False)
    raw_score = Column(Numeric(10, 2), default=0, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
