"""Errors with stable codes, so the CLI, the SDK and later the web UI report failures the same way."""

from __future__ import annotations

# Stable codes: callers and tests branch on these, never on message text.
HARNESS_MISSING = "HARNESS_MISSING"
HARNESS_INCOMPATIBLE = "HARNESS_INCOMPATIBLE"
CAPABILITY_MISSING = "CAPABILITY_MISSING"
UNSUPPORTED_TRANSPORT = "UNSUPPORTED_TRANSPORT"
WORKSPACE_INVALID = "WORKSPACE_INVALID"
HARNESS_FAILED = "HARNESS_FAILED"
INVALID_INPUT = "INVALID_INPUT"
CODES = frozenset(
    {
        HARNESS_MISSING,
        HARNESS_INCOMPATIBLE,
        CAPABILITY_MISSING,
        UNSUPPORTED_TRANSPORT,
        WORKSPACE_INVALID,
        HARNESS_FAILED,
        INVALID_INPUT,
    }
)


class GuruError(Exception):
    """A failure Dev Guru can explain: a stable ``code``, a message, an optional hint and run id."""

    def __init__(
        self, code: str, message: str, *, hint: str = "", run_id: str | None = None
    ) -> None:
        if code not in CODES:
            raise ValueError(f"unknown error code {code!r}")
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.run_id = run_id

    def to_dict(self) -> dict[str, str | None]:
        return {
            "code": self.code,
            "message": self.message,
            "hint": self.hint,
            "run_id": self.run_id,
        }
