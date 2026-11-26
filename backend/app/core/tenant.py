"""Per-request tenant (account) context for data isolation."""
from contextvars import ContextVar

current_account_id: ContextVar[str | None] = ContextVar("current_account_id", default=None)


def get_current_account_id() -> str:
    account_id = current_account_id.get()
    if not account_id:
        raise RuntimeError("No authenticated account in request context")
    return account_id