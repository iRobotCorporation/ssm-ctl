from __future__ import absolute_import, print_function

import six
from six.moves import input

import re
import argparse
import collections
import sys

import yaml

from .parameters import SSMParameter

class InputError(Exception):
    pass

class Input(object):
    
    @classmethod
    def _apply(cls, obj, values, path):
        if isinstance(obj, list):
            return [cls._apply(o, values, path=path+[i]) for i, o in enumerate(obj)]
        elif isinstance(obj, dict):
            return {cls._apply(k, values, path=path+['key:'+k]): cls._apply(v, values, path=path+[v]) for k, v in six.iteritems(obj)}
        elif isinstance(obj, six.string_types):
            for pattern, value in six.iteritems(values):
                obj = pattern.sub(value, obj)
            return obj
        else:
            return obj
    
    @classmethod
    def _get_names(cls, obj, names, path):
        if isinstance(obj, list):
            return [cls._get_names(o, names, path=path+[i]) for i, o in enumerate(obj)]
        elif isinstance(obj, dict):
            return {cls._get_names(k, names, path=path+['key:'+k]): cls._get_names(v, names, path=path+[v]) for k, v in six.iteritems(obj)}
        elif isinstance(obj, six.string_types):
            pattern = cls.get_reference_pattern()
            names.update(pattern.findall(obj))
        return obj
    
    _REFERENCE_PATTERN = re.compile(r'(?<=[^\$])\$\((\w+)\)')
    @classmethod
    def get_reference_pattern(cls, name=None):
        if name is None:
            return cls._REFERENCE_PATTERN
        pattern = r'(?<=[^\$])' + re.escape('$({})'.format(name))
        return re.compile(pattern)     
    
    @classmethod
    def apply(cls, obj, values, validate=True):
        values = {cls.get_reference_pattern(name): value for name, value in six.iteritems(values)}
        obj = cls._apply(obj, values, path=[])
        if validate:
            names = set()
            cls._get_names(obj, names, path=[])
            if names:
                raise InputError('Missing inputs: {}'.format(', '.join(names)))
        return obj
    
    @classmethod
    def load(cls, obj):
        inputs = {}
        for name, data in six.iteritems(obj):
            inputs[name] = cls(
                name,
                data.get('Type', 'String'),
                pattern=data.get('Pattern'),
                description=data.get('Description'),
            )
        return inputs
    
    def __init__(self, name, type, pattern=None, description=None):
        self.name = name
        self.type = type
        self.pattern = pattern
        self.description = description
        
        self._usage_pattern = re.escape('$({})'.format(self.name))
    
    def prompt(self):
        value = input('Enter {} ({}): '.format(self.name, self.type))
        if self.pattern and not re.search(self.pattern, value):
            raise InputError("Invalid input")
        return value
    
    def __str__(self):
        return repr(self)
    
    def __repr__(self):
        kwargs=[
            'name={!r}'.format(self.name),
            'type={!r}'.format(self.type),
        ]
        for name in ['pattern', 'description']:
            if getattr(self, name):
                kwargs.append('{}={!r}'.format(name, getattr(self, name)))
        return 'Input({})'.format(
            ','.join(kwargs))

ParameterFileData = collections.namedtuple('ParameterFileData', ['parameters', 'flush'])

INPUT_KEY = '.INPUT'
COMMON_KEY = '.COMMON'
FLUSH_KEY = '.FLUSH'

def parse_parameter_file(obj, input_values=None, prompt=True):
    input_values = input_values or {}
    
    input_definitions = Input.load(obj.pop(INPUT_KEY, {}))
    
    if prompt:
        for name, input_definition in six.iteritems(input_definitions):
            if name in input_values:
                continue
            input_values[name] = input_definition.prompt()
    
    obj = Input.apply(obj, input_values)
    
    common_data = obj.get(COMMON_KEY, {})
    
    flush = obj.get(FLUSH_KEY, [])
    if isinstance(flush, six.string_types):
        flush = [flush]
    
    parameters = {}
    for name, data in obj.items():
        if name.startswith('.'):
            continue
        
        param_data = {
            'Name': name,
        }
        
        if isinstance(data, six.string_types):
            data = {
                'Type': 'String',
                'Value': data,
            }
        elif isinstance(data, list):
            data = {
                'Type': 'StringList',
                'Value': data,
            }
        
        param_data.update(common_data)
        param_data.update(data)
        
        parameters[name] = SSMParameter.load(param_data)
    
    return ParameterFileData(parameters, flush)
