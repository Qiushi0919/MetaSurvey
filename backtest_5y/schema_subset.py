"""Enforce the declared subset of the six candidate schemas, recursively.

This is deliberately not a general JSON Schema implementation. Unknown schema
keywords or nonlocal refs fail closed. Candidate constants additionally require
the exact JSON representation type: an integer counter cannot be bool or float.
No rules are invented for fields whose contracts remain unspecified.
"""
import math
import re

_KEYWORDS = frozenset(('$schema', '$id', '$defs', '$ref', 'type', 'required',
    'properties', 'const', 'enum', 'items', 'contains', 'minItems', 'maxItems',
    'allOf', 'if', 'then', 'pattern', 'additionalProperties'))


def json_value(value):
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float and math.isfinite(value):
        return
    if type(value) is list:
        for item in value: json_value(item)
        return
    if type(value) is dict and all(type(k) is str for k in value):
        for item in value.values(): json_value(item)
        return
    raise ValueError('DTO_JSON_TYPE_OR_NONFINITE')


def equal(value, expected):
    if type(value) is not type(expected): return False
    if type(value) is dict:
        return value.keys() == expected.keys() and all(equal(value[k], v) for k, v in expected.items())
    if type(value) is list:
        return len(value) == len(expected) and all(equal(a, b) for a, b in zip(value, expected))
    return value == expected


def supported(schema):
    if type(schema) is not dict: raise ValueError('DTO_UNSUPPORTED_SCHEMA_SHAPE')
    unknown = set(schema) - _KEYWORDS
    if unknown: raise ValueError('DTO_UNSUPPORTED_SCHEMA_KEYWORD:' + ','.join(sorted(unknown)))
    if '$ref' in schema and not schema['$ref'].startswith('#/$defs/'):
        raise ValueError('DTO_UNSUPPORTED_SCHEMA_REF')
    for key in ('$defs', 'properties'):
        for rule in schema.get(key, {}).values(): supported(rule)
    for key in ('items', 'contains', 'if', 'then', 'additionalProperties'):
        if key in schema and type(schema[key]) is dict: supported(schema[key])
    for rule in schema.get('allOf', []): supported(rule)


def validate(value, schema, *, root=None, path='$'):
    if root is None:
        supported(schema)
        root = schema
    unknown = set(schema) - _KEYWORDS
    if unknown: raise ValueError('DTO_UNSUPPORTED_SCHEMA_KEYWORD:' + ','.join(sorted(unknown)))
    if '$ref' in schema:
        ref = schema['$ref']
        if not ref.startswith('#/$defs/'): raise ValueError('DTO_UNSUPPORTED_SCHEMA_REF')
        if ref[8:] not in root.get('$defs', {}): raise ValueError('DTO_UNRESOLVED_SCHEMA_REF')
        validate(value, root['$defs'][ref[8:]], root=root, path=path)
    if 'const' in schema and not equal(value, schema['const']):
        raise ValueError('DTO_CONST:' + path)
    if 'enum' in schema and not any(equal(value, v) for v in schema['enum']):
        raise ValueError('DTO_ENUM:' + path)
    if 'type' in schema:
        types = schema['type'] if type(schema['type']) is list else [schema['type']]
        allowed = {'null': lambda: value is None, 'boolean': lambda: type(value) is bool,
            'integer': lambda: type(value) is int, 'number': lambda: type(value) in (int, float),
            'string': lambda: type(value) is str, 'array': lambda: type(value) is list,
            'object': lambda: type(value) is dict}
        if not all(t in allowed for t in types): raise ValueError('DTO_UNSUPPORTED_SCHEMA_TYPE')
        if not any(allowed[t]() for t in types): raise ValueError('DTO_TYPE:' + path)
    if type(value) is dict:
        for key in schema.get('required', []):
            if key not in value: raise ValueError('DTO_REQUIRED:' + path + '.' + key)
        properties = schema.get('properties', {})
        for key, item in value.items():
            if key in properties:
                validate(item, properties[key], root=root, path=path + '.' + key)
            elif 'additionalProperties' in schema:
                extra = schema['additionalProperties']
                if extra is False: raise ValueError('DTO_ADDITIONAL_PROPERTY:' + path)
                if type(extra) is dict: validate(item, extra, root=root, path=path + '.' + key)
    if type(value) is list:
        if len(value) < schema.get('minItems', 0) or len(value) > schema.get('maxItems', len(value)):
            raise ValueError('DTO_ARRAY_LENGTH:' + path)
        for index, item in enumerate(value):
            if 'items' in schema: validate(item, schema['items'], root=root, path=f'{path}[{index}]')
        if 'contains' in schema:
            found = False
            for item in value:
                try: validate(item, schema['contains'], root=root, path=path)
                except ValueError: continue
                found = True; break
            if not found: raise ValueError('DTO_ARRAY_CONTAINS:' + path)
    if type(value) is str and 'pattern' in schema and re.search(schema['pattern'], value) is None:
        raise ValueError('DTO_PATTERN:' + path)
    for rule in schema.get('allOf', []): validate(value, rule, root=root, path=path)
    if 'if' in schema:
        try: validate(value, schema['if'], root=root, path=path)
        except ValueError: pass
        else:
            if 'then' in schema: validate(value, schema['then'], root=root, path=path)
