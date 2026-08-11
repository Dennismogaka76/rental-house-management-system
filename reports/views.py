from django.http import Http404
from django.views.generic import TemplateView, View

from accounts.mixins import AdminRequiredMixin
from . import services


class ReportsIndexView(AdminRequiredMixin, TemplateView):
    template_name = "reports/index.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["reports"] = services.REPORTS
        return ctx


class ReportDownloadView(AdminRequiredMixin, View):
    def get(self, request, kind, fmt):
        if kind not in services.REPORTS:
            raise Http404("Unknown report")
        if fmt == "csv":
            return services.as_csv(kind)
        if fmt == "xlsx":
            return services.as_xlsx(kind)
        if fmt == "pdf":
            return services.as_pdf(kind)
        raise Http404("Unknown format")
