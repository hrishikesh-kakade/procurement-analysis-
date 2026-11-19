class AppError(Exception):
    """Base class for domain errors that map cleanly onto HTTP responses."""

    status_code = 400
    code = "app_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"

    def __init__(self, entity: str, identifier: object) -> None:
        super().__init__(f"{entity} with id {identifier} not found")


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class InvalidTransitionError(ConflictError):
    code = "invalid_status_transition"


class BusinessRuleError(AppError):
    status_code = 422
    code = "business_rule_violation"


class AuthenticationError(AppError):
    status_code = 401
    code = "unauthorized"


class AuthorizationError(AppError):
    status_code = 403
    code = "forbidden"


class ExternalServiceError(AppError):
    status_code = 502
    code = "external_service_error"
