from datetime import timedelta

from django import template

register = template.Library()


@register.filter
def add_days(data, dias):
    """{{ data|add_days:6 }} → data + 6 dias."""
    return data + timedelta(days=int(dias))
