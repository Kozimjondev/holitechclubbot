from django.conf import settings

from rest_framework import serializers

from order.models import Order
from order.errors.exceptions import IncorrectAmount, PerformTransactionDoesNotExist


class MerchatTransactionsModelSerializer(serializers.ModelSerializer):

    class Meta:
        model: Order = Order
        fields: str = "__all__"

    def validate(self, data):
        """
        Validate the data given to the MerchatTransactionsModel.
        """
        if data.get("order_id") is not None:
            try:
                order = Order.objects.get(
                    id=data['order_id']
                )
                if order.amount != int(data['amount']):
                    raise IncorrectAmount()

            except IncorrectAmount:
                raise IncorrectAmount()

        return data

    def validate_amount(self, amount) -> int:
        """
        Validator for Transactions Amount
        """
        if amount is not None:
            if int(amount) <= settings.PAYME.get("PAYME_MIN_AMOUNT"):
                raise IncorrectAmount()

        return amount

    def validate_order_id(self, order_id) -> int:
        """
        Use this method to check if a transaction is allowed to be executed.
        :param order_id: string -> Order Indentation.
        """
        try:
            Order.objects.get(
                id=order_id,
            )
        except Order.DoesNotExist:
            raise PerformTransactionDoesNotExist()

        return order_id


class ClickRequestSerializer(serializers.Serializer):
    """Base serializer for Click Shop API requests"""
    click_trans_id = serializers.CharField(max_length=255, required=False, allow_blank=True)
    service_id = serializers.CharField(max_length=50, required=True)
    click_paydoc_id = serializers.CharField(max_length=255, required=False, allow_blank=True)
    merchant_trans_id = serializers.CharField(max_length=255, required=True)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)
    action = serializers.IntegerField(required=True)
    error = serializers.IntegerField(required=False, default=0)
    error_note = serializers.CharField(max_length=255, required=False, allow_blank=True)
    sign_time = serializers.CharField(max_length=255, required=True)
    sign_string = serializers.CharField(max_length=255, required=True)

    def validate_action(self, value):
        """Validate action parameter"""
        if value not in [0, 1]:
            raise serializers.ValidationError("Action must be 0 (prepare) or 1 (complete)")
        return value

    def validate_service_id(self, value):
        """Validate service ID"""
        if str(value) != str(settings.CLICK_SERVICE_ID):
            raise serializers.ValidationError("Invalid service ID")
        return value


class ClickPrepareRequestSerializer(ClickRequestSerializer):
    """Serializer for Prepare requests (action=0)"""
    click_trans_id = serializers.CharField(required=False, allow_null=True)
    click_paydoc_id = serializers.CharField(required=False, allow_null=True)


class ClickCompleteRequestSerializer(ClickRequestSerializer):
    """Serializer for Complete requests (action=1)"""
    click_trans_id = serializers.CharField(max_length=255, required=True)
    click_paydoc_id = serializers.CharField(max_length=255, required=True)


class ClickResponseSerializer(serializers.Serializer):
    """Serializer for Click API responses"""
    click_trans_id = serializers.CharField(max_length=255, required=False, allow_null=True)
    merchant_trans_id = serializers.CharField(max_length=255, required=True)
    merchant_prepare_id = serializers.IntegerField(required=False, allow_null=True)
    merchant_confirm_id = serializers.IntegerField(required=False, allow_null=True)
    error = serializers.IntegerField(required=True)
    error_note = serializers.CharField(max_length=255, required=True)
