"""
Init Payme base exception.
"""
import logging
from rest_framework.exceptions import APIException

logger = logging.getLogger(__name__)


# pylint: disable=W0231,W1203


class BaseClickException(APIException):
    """
    BasePaymeException inherits from APIException.
    """
    status_code = 200
    error_code = None

    def __init__(self, message: str = None):
        detail: dict = {
            "error": {
                "error": self.error_code,
                "error_note": message,
            }
        }
        logger.error(f"click error detail: {detail}")
        self.detail = detail


class UnSupportedAction(BaseClickException):
    """
    Raised when the request is invalid.
    """
    status_code = 200
    error_code = -3


class BadRequest(BaseClickException):
    """
    Raised when the request is invalid.
    """
    status_code = 200
    error_code = -8


class AuthFailed(BaseClickException):
    """
    Raised when the request is invalid.
    """
    status_code = 200
    error_code = -1


class AccountNotFound(BaseClickException):
    """
    Raised when the request is invalid.
    """
    status_code = 200
    error_code = -1


class IncorrectAmount(BaseClickException):
    """
    Raised when the request is invalid.
    """
    status_code = 200
    error_code = -2


class AlreadyPaid(BaseClickException):
    """
    Raised when the request is invalid.
    """
    status_code = 200
    error_code = -4


class TransactionNotFound(BaseClickException):
    """
    Raised when the request is invalid.
    """
    status_code = 200
    error_code = -6


class TransactionCancelled(BaseClickException):
    """
    Raised when the request is invalid.
    """
    status_code = 200
    error_code = -9


errors_whitelist = (
    UnSupportedAction,
    BadRequest,
    AuthFailed,
    AccountNotFound,
    IncorrectAmount,
    AlreadyPaid,
    TransactionNotFound,
    TransactionCancelled,
)
