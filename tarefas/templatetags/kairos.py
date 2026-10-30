from datetime import timedelta

from django import template

register = template.Library()


@register.filter
def add_days(data, dias):
    """{{ data|add_days:6 }} → data + 6 dias."""
    return data + timedelta(days=int(dias))


@register.filter
def ha_quanto(momento):
    """'agora', 'há 5 min', 'há 2 h' ou 'há 3 dias' (o timesince do Django diria 'há 0 minuto')."""
    from django.utils import timezone

    if not momento:
        return ""
    segundos = (timezone.now() - momento).total_seconds()
    if segundos < 60:
        return "agora"
    if segundos < 3600:
        return f"há {int(segundos // 60)} min"
    if segundos < 86400:
        return f"há {int(segundos // 3600)} h"
    dias = int(segundos // 86400)
    return f"há {dias} dia{'s' if dias > 1 else ''}"
