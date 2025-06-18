from datetime import date, timedelta
from django.utils import timezone
from core.utils.constants import CONSTANTS
from .models import UserCourseSubscription, Transaction, Order


class SubscriptionService:
    def __init__(self, transaction: Transaction):
        self.transaction = transaction

    def create_subscription(self):
        order = self.get_order()
        order.status = CONSTANTS.PaymentStatus.SUCCESS
        order.save()

        UserCourseSubscription.objects.create(
            user=self.transaction.user,
            order=order,
            course=order.course,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=order.course.period),
        )

    def get_order(self):
        return Order.objects.get(id=self.transaction.order_id)

    def cancel_subscription(self):
        user_subscription = UserCourseSubscription.objects.filter(order_id=self.transaction.order_id).first()
        if not user_subscription:
            return
        user_subscription.status = CONSTANTS.MembershipStatus.REFUND
        user_subscription.save()

        order = self.get_order()
        order.status = CONSTANTS.PaymentStatus.CANCELED
        order.save()

        self.transaction.state = Transaction.CANCELED
        self.transaction.cancel_time = timezone.now()
        self.transaction.save()
