import hashlib

from typing import Optional
from dataclasses import dataclass

from django.conf import settings

from order.click_up import exceptions
from order.click_up.const import Action


@dataclass
class ClickShopApiRequest:
    """
    Represents a transaction in the CLICK payment system.

    Fields:
        click_trans_id: ID of the transaction in the CLICK system.
        service_id: ID of the service.
        click_paydoc_id:
            Payment ID in CLICK system,
            shown to customers in SMS notifications.
        merchant_trans_id:
            Order ID (online shopping)
            or personal account/login in supplier billing.
        amount: Payment amount (in soums).
        action: Action to perform (0 – for Prepare).
        error: Status code indicating completion of payment
            (0 – success; otherwise, an error code).
        error_note: Description of the error if the transaction fails.
        sign_time:
            Date and time of the payment in "YYYY-MM-DD HH:mm:ss" format.
        sign_string: MD5 hash confirming the authenticity of the query.
    """

    click_trans_id: str
    service_id: str
    click_paydoc_id: str
    merchant_trans_id: str
    amount: str
    action: str
    error: str
    sign_time: str
    sign_string: str
    error_note: Optional[str] = None
    merchant_prepare_id: Optional[int] = None

    def is_valid(self) -> bool:
        """
        Validates the request data based on
        the required fields and constraints.
        """
        self.check_fields()
        self.check_allowed_action()

    def check_allowed_action(self):
        """
        Checks if the action is allowed based on the allowed actions.

        :return: True if the action is allowed, False otherwise.
        """
        if self.action not in Action.ALLOWED_ACTIONS:
            raise exceptions.UnSupportedAction("unsupported invalid action")

    def check_fields(self):
        """
        Additional validation for specific fields, if needed
        """
        if self.action == Action.PREPARE and self.merchant_trans_id is None:
            error = "missing required field 'merchant_prepare_id"
            raise exceptions.BadRequest(error)

    def check_auth(self):
        """
        Verifies the authenticity of the transaction using the secret key.

        :return: True if the signature is valid,
            otherwise raises an AuthFailed exception.
        """
        service_id = settings.CLICK_SERVICE_ID
        secret_key = settings.CLICK_SECRET_KEY

        if not all([service_id, secret_key]):
            raise exceptions.AuthFailed("Missing required CLICK_SETTINGS: service_id, secret_key, or merchant_id") # noqa

        text_parts = [
            self.click_trans_id,
            service_id,
            secret_key,
            self.merchant_trans_id,
            self.merchant_prepare_id or "",
            self.amount,
            self.action,
            self.sign_time,
        ]
        text = ''.join(map(str, text_parts))

        calculated_hash = hashlib.md5(text.encode('utf-8')).hexdigest()

        if calculated_hash != self.sign_string:
            raise exceptions.AuthFailed("invalid signature")
