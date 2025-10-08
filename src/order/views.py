import base64
import binascii
import hashlib
import json
import logging
import hmac

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from order.click_up import exceptions
from order.click_up.const import Action
from order.click_up.typing.request import ClickShopApiRequest
from core.utils.constants import CONSTANTS
from order.errors.exceptions import MethodNotFound
from order.errors.exceptions import PerformTransactionDoesNotExist
from order.errors.exceptions import PermissionDenied
from order.methods.cancel_transaction import CancelTransaction
from order.methods.check_perform_transaction import CheckPerformTransaction
from order.methods.check_transaction import CheckTransaction
from order.methods.create_transaction import CreateTransaction
from order.methods.perform_transaction import PerformTransaction
from order.models import Order, Transaction
from order.services import SubscriptionService
from users.models import User

logger = logging.getLogger(__name__)


class MerchantAPIView(APIView):
    permission_classes = ()
    authentication_classes = ()

    def post(self, request, *args, **kwargs):
        password = request.META.get('HTTP_AUTHORIZATION')
        if self.authorize(password):
            incoming_data: dict = request.data
            incoming_method: str = incoming_data.get("method")

            try:
                paycom_method = self.get_paycom_method_by_name(
                    incoming_method=incoming_method
                )
            except ValidationError:
                raise MethodNotFound()
            except PerformTransactionDoesNotExist:
                raise PerformTransactionDoesNotExist()

            paycom_method = paycom_method(incoming_data.get("params"))

        return Response(data=paycom_method)

    @staticmethod
    def get_paycom_method_by_name(incoming_method: str) -> object:
        """
        Use this static method to get the paycom method by name.
        :param incoming_method: string -> incoming method name
        """
        available_methods: dict = {
            "CheckTransaction": CheckTransaction,
            "CreateTransaction": CreateTransaction,
            "CancelTransaction": CancelTransaction,
            "PerformTransaction": PerformTransaction,
            "CheckPerformTransaction": CheckPerformTransaction
        }

        try:
            MerchantMethod = available_methods[incoming_method]
        except Exception:
            error_message = "Unavailable method: %s" % incoming_method
            raise MethodNotFound(error_message=error_message)

        merchant_method = MerchantMethod()

        return merchant_method

    @staticmethod
    def authorize(password: str):
        """
        Authorize the Merchant.
        :param password: string -> Merchant authorization password
        """
        is_payme: bool = False
        error_message: str = ""

        if not isinstance(password, str):
            error_message = "Request from an unauthorized source!"
            raise PermissionDenied(error_message=error_message)

        password = password.split()[-1]

        try:
            password = base64.b64decode(password).decode('utf-8')
        except (binascii.Error, UnicodeDecodeError):
            error_message = "Error when authorize request to merchant!"
            raise PermissionDenied(error_message=error_message)

        merchant_key = password.split(':')[-1]

        if merchant_key == settings.PAYME.get('PAYME_KEY'):
            is_payme = True

        if merchant_key != settings.PAYME.get('PAYME_KEY'):
            raise PermissionDenied(error_message="Invalid Payme Key")
        if is_payme is False:
            raise PermissionDenied(
                error_message="Unavailable data for unauthorized users!"
            )

        return is_payme


class ClickWebhook(APIView):
    """
    API endpoint for handling incoming CLICK webhooks.
    """
    def post(self, request):
        """
        Check if request is valid
        """
        # check 1 validation
        result = None
        params: ClickShopApiRequest = self.serialize(request)
        account = self.fetch_account(params)

        # check 2 check perform transaction
        self.check_perform_transaction(account, params)

        if params.action == Action.PREPARE:
            result = self.create_transaction(account, params)

        elif params.action == Action.COMPLETE:
            result = self.perform_transaction(account, params)

        return Response(result)

    def serialize(self, request):
        """
        serialize request data to object
        """
        request_data = {
            'click_trans_id': request.POST.get('click_trans_id'),
            'service_id': request.POST.get('service_id'),
            'click_paydoc_id': request.POST.get('click_paydoc_id'),
            'merchant_trans_id': request.POST.get('merchant_trans_id'),
            'amount': request.POST.get('amount'),
            'action': request.POST.get('action'),
            'error': request.POST.get('error'),
            'sign_time': request.POST.get('sign_time'),
            'sign_string': request.POST.get('sign_string'),
            'error_note': request.POST.get('error_note'),
            'merchant_prepare_id': request.POST.get('merchant_prepare_id'),
        }

        try:
            request_data = ClickShopApiRequest(**request_data)
            self.check_auth(request_data)

            request_data.is_valid()
            return request_data

        except exceptions.errors_whitelist as exc:
            raise exc

        except Exception as exc:
            logger.error(f"error in request data: {exc}")
            raise exceptions.BadRequest("error in request from click_up")

    def check_auth(self, params, service_id=None, secret_key=None):
        """
        Verifies the authenticity of the transaction using the secret key.

        :return: True if the signature is valid,
            otherwise raises an AuthFailed exception.
        """
        # by default it should be get from settings
        # in the another case u can override
        if not secret_key or not service_id:
            service_id = settings.CLICK_SERVICE_ID
            secret_key = settings.CLICK_SECRET_KEY

        if not all([service_id, secret_key]):
            error = "Missing required CLICK_SETTINGS: service_id, secret_key, or merchant_id" # noqa
            raise exceptions.AuthFailed(error)

        text_parts = [
            params.click_trans_id,
            service_id,
            secret_key,
            params.merchant_trans_id,
            params.merchant_prepare_id or "",
            params.amount,
            params.action,
            params.sign_time,
        ]
        text = ''.join(map(str, text_parts))

        calculated_hash = hashlib.md5(text.encode('utf-8')).hexdigest()

        if calculated_hash != params.sign_string:
            raise exceptions.AuthFailed("invalid signature")

    def fetch_account(self, params: ClickShopApiRequest):
        """
        fetching account for given merchant transaction id
        """
        try:
            return Order.objects.get(id=params.merchant_trans_id)

        except Order.DoesNotExist:
            raise exceptions.AccountNotFound("Account not found")

    def check_amount(self, order: Order, params: ClickShopApiRequest): # type: ignore # noqa
        """
        check if amount is valid
        """
        received_amount = float(params.amount)
        expected_amount = float(getattr(order, settings.CLICK_AMOUNT_FIELD))

        if received_amount - expected_amount > 0.01:
            raise exceptions.IncorrectAmount("Incorrect parameter amount")

    def check_dublicate_transaction(self, params: ClickShopApiRequest):  # type: ignore # noqa
        """
        check if transaction already exist
        """
        if Transaction.objects.filter(
            order_id=params.merchant_trans_id,
            state=Transaction.SUCCESSFULLY
        ).exists():
            raise exceptions.AlreadyPaid("Transaction already paid")

    def check_transaction_cancelled(self, params: ClickShopApiRequest):
        """
        check if transaction cancelled
        """
        if Transaction.objects.filter(
            order_id=params.merchant_trans_id,
            state=Transaction.CANCELED
        ).exists() or int(params.error) < 0:
            raise exceptions.TransactionCancelled("Transaction cancelled")

    def check_perform_transaction(self, order: Order, params: ClickShopApiRequest): # type: ignore # noqa
        """
        Check perform transaction with CLICK system
        """
        self.check_amount(order, params)
        self.check_dublicate_transaction(params)
        self.check_transaction_cancelled(params)

    def create_transaction(self, order: Order, params: ClickShopApiRequest): # type: ignore # noqa
        """
        create transaction in your system
        """
        transaction, created = Transaction.objects.get_or_create(
            order_id=order.id,
            defaults={
                'amount': params.amount,
                'transaction_id': params.click_trans_id,
                'user_id': order.user.telegram_id,
                "perform_time": timezone.now(),
            }
        )

        return {
            "click_trans_id": params.click_trans_id,
            "merchant_trans_id": order.id,
            "merchant_prepare_id": transaction.id,
            "error": 0,
            "error_note": "success"
        }

    def perform_transaction(self, account: Order, params: ClickShopApiRequest): # type: ignore # noqa
        """
        perform transaction with CLICK system
        """
        state = Transaction.SUCCESSFULLY

        if params.error is not None:
            if int(params.error) < 0:
                state = Transaction.CANCELED

        transaction = Transaction.update_or_create(
            order_id=account.id,
            amount=params.amount,
            transaction_id=params.click_trans_id,
            state=state
        )

        if state == Transaction.SUCCESSFULLY:
            self.successfully_payment(transaction)

        elif state == Transaction.CANCELED:
            self.cancelled_payment(transaction)

        return {
            "click_trans_id": params.click_trans_id,
            "merchant_trans_id": transaction.order_id,
            "merchant_prepare_id": transaction.id,
            "error": params.error,
            "error_note": params.error_note
        }

    def created_payment(self, params):
        """
        created payment method process you can ovveride it
        """
        pass

    def successfully_payment(self, transaction: Transaction):
        """
        successfully payment method process you can ovveride it
        """
        subscription_service = SubscriptionService(transaction)
        subscription_service.create_subscription()

    def cancelled_payment(self, transaction):
        """
        cancelled payment method process you can ovveride it
        """
        subscription = SubscriptionService(transaction)
        subscription.cancel_subscription()


class TributeWebhookAPIView(APIView):
    """
    Webhook API for handling Tribute Bot events
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Get API key from settings
        self.api_key = getattr(settings, 'TRIBUTE_API_KEY', None)
        if not self.api_key:
            logger.error("TRIBUTE_API_KEY not found in settings")

    def verify_signature(self, request_body, signature_header):
        """
        Verify HMAC-SHA256 signature from trbt-signature header
        """
        if not self.api_key:
            logger.error("Cannot verify signature: API key not configured")
            return False

        if not signature_header:
            logger.error("Missing trbt-signature header")
            return False

        try:
            expected_signature = hmac.new(
                self.api_key.encode('utf-8'),
                request_body,
                hashlib.sha256
            ).hexdigest()

            return hmac.compare_digest(signature_header, expected_signature)
        except Exception as e:
            logger.error(f"Error verifying signature: {str(e)}")
            return False

    def handle_new_subscription(self, payload):
        """
        Handle new subscription event
        """
        try:
            subscription_data = {
                'subscription_name': payload.get('subscription_name'),
                'subscription_id': payload.get('subscription_id'),
                'period_id': payload.get('period_id'),
                'period': payload.get('period'),
                'price': payload.get('price'),
                'amount': payload.get('amount'),
                'currency': payload.get('currency'),
                'user_id': payload.get('user_id'),
                'telegram_user_id': payload.get('telegram_user_id'),
                'channel_id': payload.get('channel_id'),
                'channel_name': payload.get('channel_name'),
                'expires_at': payload.get('expires_at')
            }

            logger.info(f"New subscription received: {subscription_data}")
            try:
                user = User.objects.get(telegram_id=payload.get('telegram_user_id'))
            except Exception as e:
                logger.error(f"Error getting user: {str(e)}")
                return False
            Transaction.objects.create(
                user=user,
                amount=int(subscription_data.get('amount')),
                state=Transaction.SUCCESSFULLY,
                payment_method=CONSTANTS.PaymentMethod.TRIBUTE,
                fiscal_data=subscription_data
            )
            user.is_foreigner = True
            user.is_subscribed = True
            user.is_auto_subscribed = True
            user.subscription_start_date = timezone.now().date()

            expires_at_str = subscription_data.get('expires_at')
            expires_at_datetime = parse_datetime(expires_at_str)
            user.subscription_end_date = expires_at_datetime.date()

            user.save()

            return True

        except Exception as e:
            logger.error(f"Error handling new subscription: {str(e)}")
            return False

    def handle_subscription_cancelled(self, payload):
        """
        Handle subscription cancelled event
        """
        try:
            logger.info(f"Subscription cancelled: {payload}")
            try:
                user = User.objects.get(telegram_id=payload.get('telegram_user_id'))
            except Exception as e:
                logger.error(f"Error getting user: {str(e)}")
                return False
            user.is_auto_subscribe = False
            user.save()

            return True

        except Exception as e:
            logger.error(f"Error handling subscription cancellation: {str(e)}")
            return False

    def post(self, request):
        """
        Handle POST requests from Tribute Bot webhook
        """
        try:
            signature = request.headers.get('trbt-signature')
            request_body = request.body

            if not self.verify_signature(request_body, signature):
                logger.warning("Invalid webhook signature")
                return Response(
                    {'error': 'Invalid signature'},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            try:
                webhook_data = json.loads(request_body.decode('utf-8'))
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON payload: {str(e)}")
                return Response(
                    {'error': 'Invalid JSON payload'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Extract event information
            event_name = webhook_data.get('name')
            created_at = webhook_data.get('created_at')
            sent_at = webhook_data.get('sent_at')
            payload = webhook_data.get('payload', {})

            logger.info(f"Received webhook event: {event_name}")

            if event_name == 'new_subscription':
                success = self.handle_new_subscription(payload)
            elif event_name == 'cancelled_subscription':
                success = self.handle_subscription_cancelled(payload)
            else:
                logger.warning(f"Unknown event type: {event_name}")
                return Response(
                    {'error': f'Unknown event type: {event_name}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if success:
                return Response(
                    {'status': 'success', 'message': f'Event {event_name} processed successfully'},
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {'error': f'Failed to process event {event_name}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        except Exception as e:
            logger.error(f"Unexpected error processing webhook: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

