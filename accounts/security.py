"""Admin sudo-mode: require password re-entry for sensitive actions.

After successful verification, the ORIGINAL request is replayed automatically
so the admin doesn't have to redo the action they were performing.
"""
import time

from django import forms
from django.conf import settings
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View


SUDO_TIMEOUT = getattr(settings, "ADMIN_SUDO_TIMEOUT", 300)
SUDO_KEY = "admin_sudo_expires_at"
PENDING_KEY = "admin_sudo_pending"


def _sudo_valid(request) -> bool:
    exp = request.session.get(SUDO_KEY)
    return bool(exp and float(exp) > time.time())


class SudoRequiredMixin:
    """Mix-in for admin CBVs that mutate data.

    On mutating methods (POST/PUT/PATCH/DELETE) without a fresh sudo grant,
    the mixin stashes the submitted form fields in the session and redirects
    to the confirm-password view. After successful re-auth the original POST
    is replayed against the same URL, so the pending action completes.
    """

    sudo_methods = ("POST", "PUT", "PATCH", "DELETE")

    def dispatch(self, request, *args, **kwargs):
        if (
            request.method in self.sudo_methods
            and request.user.is_authenticated
            and not _sudo_valid(request)
        ):
            # Serialize POST as a plain dict of lists (skip csrf; files unsupported).
            data = {
                k: request.POST.getlist(k)
                for k in request.POST.keys()
                if k != "csrfmiddlewaretoken"
            }
            request.session[PENDING_KEY] = {
                "path": request.get_full_path(),
                "data": data,
            }
            request.session.modified = True
            url = reverse("accounts:sudo_confirm")
            return redirect(f"{url}?next={request.get_full_path()}")
        return super().dispatch(request, *args, **kwargs)


class SudoConfirmForm(forms.Form):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control", "autofocus": "autofocus"}),
        label="Confirm your password",
    )


class SudoConfirmView(View):
    template_name = "accounts/sudo_confirm.html"
    replay_template = "accounts/sudo_replay.html"

    def get(self, request):
        pending = request.session.get(PENDING_KEY)
        return render(
            request,
            self.template_name,
            {"form": SudoConfirmForm(), "pending_path": pending.get("path") if pending else None},
        )

    def post(self, request):
        form = SudoConfirmForm(request.POST)
        if not form.is_valid() or not request.user.check_password(form.cleaned_data["password"]):
            form.add_error("password", "Incorrect password. Please try again.")
            return render(
                request,
                self.template_name,
                {"form": form, "pending_path": (request.session.get(PENDING_KEY) or {}).get("path")},
                status=400,
            )

        request.session[SUDO_KEY] = time.time() + SUDO_TIMEOUT
        pending = request.session.pop(PENDING_KEY, None)
        request.session.modified = True

        if pending and pending.get("path"):
            # Auto-submit a form back to the original URL to complete the action.
            fields = []
            for key, values in (pending.get("data") or {}).items():
                for v in values:
                    fields.append((key, v))
            return render(
                request,
                self.replay_template,
                {"path": pending["path"], "fields": fields},
            )

        next_url = request.GET.get("next") or reverse("accounts:admin_dashboard")
        return redirect(next_url)
