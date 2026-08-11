from django.contrib import admin

from .models import (
    NotificationLog, Notification, Announcement, MessageThread, Message,
)

admin.site.register(NotificationLog)
admin.site.register(Notification)
admin.site.register(Announcement)
admin.site.register(MessageThread)
admin.site.register(Message)
