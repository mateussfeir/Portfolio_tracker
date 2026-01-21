from django.http import HttpResponseForbidden


class DemoReadOnlyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.session.get("is_demo") and request.method not in ("GET", "HEAD", "OPTIONS"):
            allowed_paths = {"/login/", "/logout/", "/signup/", "/demo/exit/"}
            if request.path in allowed_paths:
                if request.path in {"/login/", "/signup/"} and request.method == "POST":
                    request.session.pop("is_demo", None)
                return self.get_response(request)
            return HttpResponseForbidden("Demo mode: changes are disabled.")
        return self.get_response(request)
