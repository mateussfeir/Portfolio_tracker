from django.http import HttpResponseForbidden


class DemoReadOnlyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.session.get("is_demo") and request.method not in ("GET", "HEAD", "OPTIONS"):
            return HttpResponseForbidden("Demo mode: changes are disabled.")
        return self.get_response(request)
