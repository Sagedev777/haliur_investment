from django import template
register = template.Library()

@register.filter
def filter_by_status(queryset, statuses):
    if not queryset:
        return queryset
    status_list = [s.strip() for s in statuses.split(',')]
    return queryset.filter(status__in=status_list)

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.simple_tag
def multiply(value, arg):
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def format_currency(value):
    try:
        return f'UGX {float(value):,.0f}'
    except (ValueError, TypeError):
        return f'UGX 0'
    

@register.filter(name='has_group')
def has_group(user, group_name):
    """Check if user belongs to a specific group"""
    return user.groups.filter(name=group_name).exists()