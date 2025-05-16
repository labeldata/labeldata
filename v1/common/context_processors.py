from django.conf import settings

def static_build_date(request):
    return {'STATIC_BUILD_DATE': getattr(settings, 'STATIC_BUILD_DATE', '')}
