import time
from django.db import transaction

from order.utils.get_params import get_params

from order.models import Transaction
from order.serializers import MerchatTransactionsModelSerializer
from order.errors.exceptions import PerformTransactionDoesNotExist
from order.services import SubscriptionService


class CancelTransaction:

    @transaction.atomic
    def __call__(self, params: dict):
        serializer = MerchatTransactionsModelSerializer(
            data=get_params(params)
        )
        serializer.is_valid(raise_exception=True)
        clean_data: dict = serializer.validated_data
        try:
            with transaction.atomic():
                transactions: Transaction = \
                    Transaction.objects.filter(
                        _id=clean_data.get('_id'),
                    ).first()
                if transactions.cancel_time == 0:
                    transactions.cancel_time = int(time.time() * 1000)
                if transactions.perform_time == 0:
                    transactions.state = -1
                if transactions.perform_time != 0:
                    transactions.state = -2
                transactions.reason = clean_data.get("reason")
                transactions.save()

                subscription = SubscriptionService(transactions)
                subscription.cancel_subscription()

        except PerformTransactionDoesNotExist:
            raise PerformTransactionDoesNotExist()

        response: dict = {
            "result": {
                "state": transactions.state,
                "cancel_time": transactions.cancel_time,
                "transaction": transactions.transaction_id,
                "reason": int(transactions.reason),
            }
        }

        return response