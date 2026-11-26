from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render

from apps.organizations.permissions import has_organization_permission
from apps.parties.models import Customer, Farmer


@login_required
def app_home(request):
    """Role-aware DairyNexus mobile application shell."""
    if Farmer.objects.filter(user=request.user, is_active=True, deleted_at__isnull=True).exists():
        return redirect("farmer_portal:home")
    if Customer.objects.filter(user=request.user, is_active=True, deleted_at__isnull=True).exists():
        return redirect("customer_portal:home")

    memberships = (
        request.user.memberships.filter(
            status="active",
            organization__status__in=["trial", "active"],
        )
        .select_related("organization")
        .order_by("organization__name")
    )
    workspaces = []
    for membership in memberships:
        workspaces.append(
            {
                "organization": membership.organization,
                "membership": membership,
                "dashboard": has_organization_permission(membership, "dashboard.view"),
                "parties": has_organization_permission(membership, "parties.view"),
                "collections": has_organization_permission(membership, "collections.view"),
                "collection_create": has_organization_permission(membership, "collections.create"),
                "finance": has_organization_permission(membership, "finance.view"),
                "inventory": has_organization_permission(membership, "inventory.view"),
                "exports": has_organization_permission(membership, "exports.create"),
                "reports": has_organization_permission(membership, "reports.view"),
                "configuration": membership.role in {"owner", "admin"},
            }
        )
    return render(request, "mobile/home.html", {"mobile_workspaces": workspaces})


def mobile_manifest(request):
    return JsonResponse(
        {
            "id": "/app/",
            "name": "Dairy Nepal Milk Management",
            "short_name": "Dairy Nepal",
            "description": "Nepal dairy operations, milk collections and farmer accounts.",
            "start_url": "/app/",
            "scope": "/",
            "display": "standalone",
            "background_color": "#f3f7fc",
            "theme_color": "#17365d",
            "orientation": "portrait-primary",
            "icons": [
                {
                    "src": "/static/pwa/icon-192.svg",
                    "sizes": "192x192",
                    "type": "image/svg+xml",
                    "purpose": "any",
                },
                {
                    "src": "/static/pwa/icon-512.svg",
                    "sizes": "512x512",
                    "type": "image/svg+xml",
                    "purpose": "any maskable",
                },
            ],
            "categories": ["business", "productivity"],
        },
        content_type="application/manifest+json",
    )


def mobile_service_worker(request):
    """Cache the app shell/assets only; never cache private business responses."""
    source = """const CACHE='dairynexus-shell-v1';
const SHELL=['/app/offline/'];
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE).then(c=>c.addAll(SHELL)).then(()=>self.skipWaiting()))});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()))});
self.addEventListener('fetch', event => {
    const url = new URL(event.request.url);
    if (event.request.method !== 'GET' || url.origin !== location.origin) return;
    const privatePrefixes = ['/accounts/', '/admin/', '/business/',
        '/farmer/', '/portal/', '/api/'];
    if (privatePrefixes.some(prefix => url.pathname.startsWith(prefix))) return;
    if (url.pathname.startsWith('/static/')) {
        event.respondWith(
            fetch(event.request)
                .then(response => {
                    if (response.ok) {
                        const copy = response.clone();
                        caches.open(CACHE).then(cache => cache.put(event.request, copy));
                    }
                    return response;
                })
                .catch(() => caches.match(event.request))
        );
        return;
    }
    if (event.request.mode === 'navigate') {
        event.respondWith(fetch(event.request).catch(() => caches.match('/app/offline/')));
    }
});
"""
    response = HttpResponse(source, content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache"
    return response


def mobile_offline(request):
    return render(request, "mobile/offline.html")
