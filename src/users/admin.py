from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    model = User
    list_display = ('telegram_id', 'first_name', 'last_name', 'username', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_active')
    search_fields = ('telegram_id', 'first_name', 'last_name', 'username')
    ordering = ('created_at',)

    fieldsets = (
        (None, {'fields': ('telegram_id', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'username', 'phone')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('telegram_id', 'first_name', 'last_name', 'username', 'phone', 'password1', 'password2',
                       'is_active', 'is_staff'),
        }),
    )
