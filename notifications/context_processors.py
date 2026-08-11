from django.urls import reverse

def notification_flags(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"unread_notifications": 0, "unread_messages": 0}
    try:
        from .models import Notification, Message, MessageThread
        unread_notifs = Notification.objects.filter(user=user, is_read=False).count()
        if user.is_admin_user:
            unread_msgs = Message.objects.filter(is_read=False)\
                .exclude(sender=user).count()
        else:
            unread_msgs = Message.objects.filter(
                thread__tenant=user, is_read=False,
            ).exclude(sender=user).count()
    except Exception:
        unread_notifs = 0
        unread_msgs = 0
    return {
        "unread_notifications": unread_notifs,
        "unread_messages": unread_msgs,
    }
