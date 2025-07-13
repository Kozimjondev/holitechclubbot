class CONSTANTS:
    class PaymentStatus:
        DRAFT = "draft"
        SUCCESS = "success"
        PENDING = "pending"
        PAID = "paid"
        FAILED = "failed"
        CANCELED = "canceled"
        CHOICES = (
            (PENDING, PENDING),
            (PAID, PAID),
            (FAILED, FAILED),
            (SUCCESS, SUCCESS),
            (DRAFT, DRAFT),
            (CANCELED, CANCELED),
        )

    class PaymentMethod:
        CLICK = "click_up"
        PAYME = "payme"
        TRIBUTE = "tribute"

        CHOICES = (
            (CLICK, 'Click'),
            (PAYME, 'Payme'),
            (TRIBUTE, 'Tribute'),
        )

    class MembershipStatus:
        PENDING = "pending"
        ACTIVE = "active"
        EXPIRED = "expired"
        VOID = "void"
        REFUND = "refund"
        FREEZE = "freeze"

        NOT_ACTUAL = [VOID, REFUND, EXPIRED, PENDING]
        ACTUAL = [ACTIVE, FREEZE]
        IN_PROGRESS = [ACTIVE, FREEZE, PENDING]
        CHOICES = (
            (PENDING, 'Pending'),
            (ACTIVE, 'Active'),
            (EXPIRED, 'Expired'),
            (VOID, 'Void'),
            (REFUND, 'Refund'),
            (FREEZE, 'Freeze'),
        )

    class LANGUAGES:
        UZ = 'uz'
        RU = 'ru'

        CHOICES = (
        (UZ, 'UZ'),
        (RU, 'RU'),
        )
