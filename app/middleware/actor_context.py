from contextvars import ContextVar

actor_id_var: ContextVar[str | None] = ContextVar("actor_id", default=None)
