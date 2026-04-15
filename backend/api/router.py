
from django.urls import path, include

urlpatterns = [
    path("admin/", include("backend.api.admin_urls")),
    path("ai/", include("backend.api.ai.urls")),
    path("entities/", include("backend.api.entities.urls")),
    path("activity/", include("backend.api.activity.urls")),
    path("auth/", include("backend.api.auth.urls")),
    path("billing/", include("backend.api.billing.urls")),
    path("contracts/", include("backend.api.contracts.urls")),
    path("documents/", include("backend.api.documents.urls")),
    path("notifications/", include("backend.api.notifications.urls")),
    path("obligations/", include("backend.api.obligations.urls")),
    path("payments/", include("backend.api.payments.urls")),
    path("prep/", include("backend.api.prep.urls")),
    path("search/", include("backend.api.search.urls")),
    path("sessions/", include("backend.api.sessions.urls")),
    path("sol/", include("backend.api.sol.urls")),
    path("obligation-templates/", include("backend.api.obligation_templates.urls")),
    path("payment-templates/", include("backend.api.payment_templates.urls")),
    path("templates/", include("backend.api.templates.urls")),
    path("tools/", include("backend.api.tools.urls")),
    path("uploads/", include("backend.api.uploads.urls")),
    path("users/", include("backend.api.users.urls")),
    path("workspace/", include("backend.api.workspace.urls")),
]


