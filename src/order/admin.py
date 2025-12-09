from django.contrib import admin
from django.utils.html import format_html
from .models import UserCourseSubscription, Course, Order, PrivateChannel, Transaction


@admin.register(UserCourseSubscription)
class UserCourseSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'order', 'start_date', 'status')
    list_filter = ('status', 'start_date',)
    search_fields = ('user__telegram_id', 'order__id')
    ordering = ('-start_date',)
    readonly_fields = ('start_date',)

    def get_user_telegram_id(self, obj):
        return obj.user.telegram_id

    get_user_telegram_id.short_description = 'Telegram ID'


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('user', 'course', 'amount', 'created_at', 'status')
    list_filter = ('status', 'created_at',)
    search_fields = ('user__telegram_id',)
    list_display_links = ('amount', 'user')


@admin.register(Transaction)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'transaction_id', 'user', 'amount', 'get_state_display',
                    'payment_method', 'perform_time', 'cancel_time', 'created_at')
    list_filter = ('state', 'payment_method', 'created_at',)
    search_fields = ('transaction_id', 'user__telegram_id', 'user__first_name', 'user__last_name')
    readonly_fields = ('transaction_id', 'created_at', 'updated_at')
    fieldsets = (
        ('Payment Information', {
            'fields': ('transaction_id', 'user', 'amount', 'state', 'payment_method')
        }),
        ('Status Information', {
            'fields': ('perform_time', 'cancel_time', 'cancel_reason')
        }),
        ('Additional Data', {
            'fields': ('fiscal_data',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_state_display(self, obj):
        """Display state with color coding"""
        state_colors = {
            Transaction.CREATED: 'blue',
            Transaction.INITIATING: 'orange',
            Transaction.SUCCESSFULLY: 'green',
            Transaction.CANCELED: 'red',
            Transaction.CANCELED_DURING_INIT: 'darkred',
        }
        color = state_colors.get(obj.state, 'black')
        state_display = dict(Transaction.STATE).get(obj.state)
        return format_html('<span style="color: {};">{}</span>', color, state_display)

    get_state_display.short_description = 'Status'


@admin.register(Course)
class CourseAmountAdmin(admin.ModelAdmin):
    list_display = ('id', 'amount', 'name', 'description')
    list_display_links = ('id', 'amount')
    search_fields = ('name', 'description')
    list_filter = ('created_at', 'updated_at')
    ordering = ('-created_at',)


@admin.register(PrivateChannel)
class PrivateChannelAdmin(admin.ModelAdmin):
    list_display = ('id', 'private_channel_id', 'course', 'course_name', 'period')
    list_display_links = ('id', 'private_channel_id')
    search_fields = ('private_channel_id',)
    ordering = ('-created_at',)

    def period(self, obj):
        return obj.course.period

    def course_name(self, obj):
        return obj.course.name
