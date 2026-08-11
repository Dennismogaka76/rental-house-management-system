from django.contrib import messages as flash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import ListView, DetailView, View, CreateView, TemplateView, FormView
from django import forms

from accounts.mixins import AdminRequiredMixin
from accounts.models import User
from apartments.models import Apartment

from .models import (
    Announcement, AnnouncementAudience, Message, MessageThread, Notification,
)
from . import services


# ------------------------- Notifications (bell) --------------------------- #

class NotificationListView(LoginRequiredMixin, ListView):
    template_name = "notifications/notification_list.html"
    context_object_name = "notifications"
    paginate_by = 30

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)


class MarkNotificationReadView(LoginRequiredMixin, View):
    def post(self, request, pk):
        n = get_object_or_404(Notification, pk=pk, user=request.user)
        n.is_read = True
        n.save(update_fields=["is_read"])
        if n.url:
            return redirect(n.url)
        return redirect("notifications:list")


class MarkAllReadView(LoginRequiredMixin, View):
    def post(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return redirect(request.META.get("HTTP_REFERER") or reverse("notifications:list"))


# ------------------------- Messaging -------------------------------------- #

class MessageForm(forms.Form):
    body = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3,
                                     "placeholder": "Write your message..."}),
        max_length=2000,
    )


class InboxView(LoginRequiredMixin, ListView):
    template_name = "notifications/inbox.html"
    context_object_name = "threads"

    def get_queryset(self):
        user = self.request.user
        if user.is_admin_user:
            return MessageThread.objects.select_related("tenant").all()
        MessageThread.objects.get_or_create(tenant=user)
        return MessageThread.objects.filter(tenant=user)


class ThreadDetailView(LoginRequiredMixin, DetailView):
    model = MessageThread
    template_name = "notifications/thread.html"
    context_object_name = "thread"

    def get_object(self, queryset=None):
        thread = super().get_object(queryset)
        user = self.request.user
        if not user.is_admin_user and thread.tenant_id != user.id:
            raise PermissionDenied
        # mark unread messages from the other party as read
        thread.messages.exclude(sender=user).filter(is_read=False).update(is_read=True)
        return thread

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["form"] = MessageForm()
        return ctx

    def post(self, request, *args, **kwargs):
        thread = self.get_object()
        form = MessageForm(request.POST)
        if form.is_valid():
            Message.objects.create(
                thread=thread, sender=request.user,
                body=form.cleaned_data["body"],
            )
            thread.save(update_fields=["updated_at"])
            # notify the other party
            other = None
            if request.user.is_admin_user:
                other = thread.tenant
                services.push_notification(
                    other, "New message from admin",
                    form.cleaned_data["body"][:120],
                    category=Notification.Category.SYSTEM,
                    url=reverse("notifications:thread", args=[thread.pk]),
                )
            else:
                for admin in services._admins():
                    services.push_notification(
                        admin, f"New message from {request.user.full_name}",
                        form.cleaned_data["body"][:120],
                        category=Notification.Category.SYSTEM,
                        url=reverse("notifications:thread", args=[thread.pk]),
                    )
        return redirect("notifications:thread", pk=thread.pk)


class TenantNewMessageView(LoginRequiredMixin, View):
    """Tenant shortcut: open (or create) my thread."""
    def get(self, request):
        if request.user.is_admin_user:
            return redirect("notifications:inbox")
        thread, _ = MessageThread.objects.get_or_create(tenant=request.user)
        return redirect("notifications:thread", pk=thread.pk)


# ------------------------- Admin: broadcast announcement ------------------ #

class AnnouncementForm(forms.Form):
    audience = forms.ChoiceField(
        choices=AnnouncementAudience.choices,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    apartment = forms.ModelChoiceField(
        queryset=Apartment.objects.all(), required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    tenant = forms.ModelChoiceField(
        queryset=User.objects.filter(role=User.Role.TENANT), required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    body = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 4}),
    )

    def clean(self):
        cleaned = super().clean()
        aud = cleaned.get("audience")
        if aud == AnnouncementAudience.APARTMENT and not cleaned.get("apartment"):
            raise forms.ValidationError("Please pick an apartment.")
        if aud == AnnouncementAudience.TENANT and not cleaned.get("tenant"):
            raise forms.ValidationError("Please pick a tenant.")
        return cleaned


class AnnouncementCreateView(AdminRequiredMixin, FormView):
    template_name = "notifications/announcement_form.html"
    form_class = AnnouncementForm
    success_url = reverse_lazy("notifications:announcement_new")

    def form_valid(self, form):
        n = services.broadcast_announcement(
            sender=self.request.user,
            audience=form.cleaned_data["audience"],
            title=form.cleaned_data["title"],
            body=form.cleaned_data["body"],
            apartment=form.cleaned_data.get("apartment"),
            tenant=form.cleaned_data.get("tenant"),
        )
        flash.success(self.request, f"Announcement sent to {n} tenant(s).")
        return super().form_valid(form)
