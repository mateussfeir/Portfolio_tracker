def demo_flags(request):
    return {
        "is_demo": request.session.get("is_demo", False),
    }
