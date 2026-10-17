"""One complete JSON value, with optional whole-value Markdown fencing.

Fences are presentation only. Extra prose, multiple packets and trailing
receipts still fail JSON parsing and cannot escape a typed reply contract.
"""
import json
import re


def loads(raw):
    fenced=re.fullmatch(r'\s*```(?:json)?\s*\n(.*?)\n```\s*',raw,re.S)
    return json.loads(fenced[1] if fenced else raw)
