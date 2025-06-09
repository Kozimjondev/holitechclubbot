import time

from order.utils.get_params import get_params

from order.models import Transaction
from order.serializers import MerchatTransactionsModelSerializer
from order.services import SubscriptionService

class PerformTransaction:
    def __call__(self, params: dict) -> dict:
        serializer = MerchatTransactionsModelSerializer(
            data=get_params(params)
        )
        serializer.is_valid(raise_exception=True)
        clean_data: dict = serializer.validated_data
        response: dict = None
        try:
            transaction = \
                Transaction.objects.get(
                    _id=clean_data.get("_id"),
                )

            transaction.state = 2
            if transaction.perform_time == 0:
                transaction.perform_time = int(time.time() * 1000)

            transaction.save()

            subscription_service = SubscriptionService(transaction)
            subscription_service.create_subscription()


            response: dict = {
                "result": {
                    "perform_time": int(transaction.perform_time),
                    "transaction": transaction.transaction_id,
                    "state": int(transaction.state),
                }
            }
        except Exception as e:
            print(e)

        return response