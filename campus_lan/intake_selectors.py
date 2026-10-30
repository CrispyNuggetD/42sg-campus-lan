"""Unambiguous intake selectors; cN is reserved for physical clusters."""
import re


def intake_number(value):
    match=re.fullmatch(r'(?:cohort|intake|i)(\d+)',value,re.I)
    if not match:return None
    number=int(match.group(1))
    if number<1:raise ValueError('Intakes start at I1; use I4, intake4 or cohort4.')
    return number


def cluster_selector(value):
    return bool(re.fullmatch(r'(?:c|cluster)\d+',value,re.I))
