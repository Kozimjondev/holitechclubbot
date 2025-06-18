from django.db import models

from core.models import TimestampedModel
from core.utils.constants import CONSTANTS


class Transaction(TimestampedModel):
    CREATED = 0
    INITIATING = 1
    SUCCESSFULLY = 2
    CANCELED = -2
    CANCELED_DURING_INIT = -1

    STATE = [
        (CREATED, "Created"),
        (INITIATING, "Initiating"),
        (SUCCESSFULLY, "Successfully"),
        (CANCELED, "Canceled after successful performed"),
        (CANCELED_DURING_INIT, "Canceled during initiation"),
    ]
    _id = models.CharField(max_length=255, null=True, blank=True)
    transaction_id = models.CharField(max_length=50)
    order_id = models.BigIntegerField(null=True, blank=True)
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='user_transactions', null=True,
                             blank=True)
    amount = models.PositiveIntegerField()

    state = models.IntegerField(choices=STATE, default=CREATED)
    fiscal_data = models.JSONField(default=dict)
    payment_method = models.CharField(
        max_length=20, choices=CONSTANTS.PaymentMethod.CHOICES
    )
    cancel_reason = models.IntegerField(null=True, blank=True)
    perform_time = models.DateTimeField(null=True, blank=True)
    cancel_time = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.transaction_id} - {self.pk}"

    def get_state_display(self):
        """
        Return the state of the transaction as a string
        """
        return self.STATE[self.state][1]

    @classmethod
    def get_or_create(
        cls,
        order_id,
        transaction_id,
        amount,
        state=None
    ) -> "Transaction":
        """
        Get an existing transaction or create a new one
        """
        # pylint: disable=E1101
        transaction, _ = Transaction.objects.get_or_create(
            order_id=order_id,
            amount=amount,
            transaction_id=transaction_id,
            defaults={"state": cls.INITIATING, "payment_method": CONSTANTS.PaymentMethod.CLICK},
        )
        if state is not None:
            transaction.state = state
            transaction.save()

        return transaction

    @classmethod
    def update_or_create(
        cls,
        order_id,
        transaction_id,
        amount,
        state=None
    ) -> "Transaction":
        """
        Update an existing transaction or create a new one if it doesn't exist
        """
        # pylint: disable=E1101
        transaction, _ = Transaction.objects.update_or_create(
            order_id=order_id,
            amount=amount,
            transaction_id=transaction_id,
            defaults={"state": cls.INITIATING, "payment_method": CONSTANTS.PaymentMethod.CLICK},
        )
        if state is not None:
            transaction.state = state
            transaction.save()

        return transaction


class Course(TimestampedModel):
    amount = models.PositiveIntegerField()
    description = models.TextField(null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    period = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return str(self.amount)


class Order(TimestampedModel):
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='user_orders',)
    course = models.ForeignKey('Course', on_delete=models.CASCADE, related_name='order_payments',)
    amount = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=CONSTANTS.PaymentStatus.CHOICES, default=CONSTANTS.PaymentStatus.PENDING)

    def __str__(self):
        return f"{self.pk}"


class UserCourseSubscription(TimestampedModel):
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='course_subscriptions')
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='subscriptions')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='subscriptions')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=30,
        choices=CONSTANTS.MembershipStatus.CHOICES,
        default=CONSTANTS.MembershipStatus.ACTIVE
    )

    def __str__(self):
        return f"{self.user.telegram_id} - {self.start_date}"

    class Meta:
        verbose_name = 'User Course Subscription'
        verbose_name_plural = 'User Course Subscriptions'


class PrivateChannel(TimestampedModel):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='private_channels')
    private_channel_id = models.CharField(max_length=255, unique=True)
    private_channel_link = models.URLField()

    def __str__(self):
        return f"{self.course} - {self.private_channel_id}"
