"""Cooperative cancellation escapes tool-level retry handlers."""
class InvestigationCancelled(BaseException):
    pass
