from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    model = User
    list_display = (
        'telegram_id', 'first_name', 'last_name', 'username',
        'is_staff', 'is_active', 'is_subscribed', 'language'
    )
    list_filter = (
        'is_staff', 'is_active', 'is_subscribed', 'language', 'is_foreigner'
    )
    search_fields = (
        'telegram_id', 'first_name', 'last_name', 'username', 'phone'
    )
    ordering = ('created_at',)

    # ✅ make timestamps readonly
    readonly_fields = ('created_at', 'updated_at', 'last_login')

    fieldsets = (
        (None, {'fields': ('telegram_id', 'password')}),
        (_('Personal info'), {
            'fields': (
                'first_name', 'last_name', 'username', 'phone', 'language',
                'is_foreigner', 'agreed_to_terms'
            )
        }),
        (_('Subscription info'), {
            'fields': (
                'is_subscribed', 'subscription_start_date', 'subscription_end_date',
                'is_auto_subscribe'
            )
        }),
        (_('Permissions'), {
            'fields': (
                'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'
            )
        }),
        (_('Important dates'), {'fields': ('last_login', 'created_at', 'updated_at')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'telegram_id', 'first_name', 'last_name', 'username', 'phone',
                'password1', 'password2', 'is_active', 'is_staff',
                'is_subscribed', 'language', 'is_foreigner', 'agreed_to_terms'
            ),
        }),
    )