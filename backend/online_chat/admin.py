from django.contrib import admin

from online_chat.models import Dialog, DialogMessage


class DialogMessageInline(admin.TabularInline):
    model = DialogMessage
    extra = 0
    readonly_fields = ("id", "speaker", "text", "created_at")


@admin.register(Dialog)
class DialogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "client_first_name",
        "client_last_name",
        "status",
        "channel",
        "updated_at",
    )
    list_filter = ("status", "channel")
    search_fields = ("client_first_name", "client_last_name", "client_phone", "preview")
    inlines = [DialogMessageInline]


@admin.register(DialogMessage)
class DialogMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "dialog", "speaker", "created_at")
    list_filter = ("speaker",)
