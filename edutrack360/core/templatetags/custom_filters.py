from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

# templatetags/custom_filters.py

@register.filter
def replace(value, arg):
    old, new = arg.split(',')
    return value.replace(old, new)
