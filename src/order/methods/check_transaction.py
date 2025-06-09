from order.utils.get_params import get_params

from order.models import Transaction
from order.serializers import MerchatTransactionsModelSerializer


class CheckTransaction:
    def __call__(self, params: dict):
        response: dict = None
        serializer = MerchatTransactionsModelSerializer(
            data=get_params(params)
        )
        serializer.is_valid(raise_exception=True)
        clean_data: dict = serializer.validated_data

        try:
            logged_message = "started check transaction in db"
            transaction = \
                Transaction.objects.get(
                    _id=clean_data.get("_id"),
                )

            response = {
                "result": {
                    "create_time": int(transaction.created_at_ms),
                    "perform_time": transaction.perform_time,
                    "cancel_time": transaction.cancel_time,
                    "transaction": transaction.transaction_id,
                    "state": transaction.state,
                    "reason": None,
                }
            }
            if transaction.reason is not None:
                response["result"]["reason"] = int(transaction.reason)

        except Exception as e:
            print(e)

        return response
