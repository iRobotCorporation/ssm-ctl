"""Utility functions

Copyright 2018 iRobot Corporation

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import six
import re

class VarString(object):
    _VAR_NAME_PATTERN_STR = r'\w+'
    _VAR_NAME_PATTERN = re.compile(_VAR_NAME_PATTERN_STR)
    _REFERENCE_PATTERN_STR = r'\$\(({})\)'.format(_VAR_NAME_PATTERN_STR)
    _REFERENCE_PATTERN = re.compile(_REFERENCE_PATTERN_STR)
    
    NAMES = set()
    _VAR_VALUES = {}
    
    @classmethod
    def get_reference_pattern(cls, name=None):
        if name is None:
            return cls._REFERENCE_PATTERN
        pattern = re.escape('$({})'.format(name))
        return re.compile(pattern)
    
    @classmethod
    def single_reference(cls, s):
        match = cls._REFERENCE_PATTERN.match(s)
        if match and match.group() == s:
            return s
        match = cls._VAR_NAME_PATTERN.match(s)
        if match and match.group() == s:
            return '$({})'.format(s)
        raise ValueError("{} is not a valid single reference".format(s))
    
    @classmethod
    def resolve(cls, resolver):
        for name in sorted(cls.NAMES):
            cls._VAR_VALUES[name] = resolver(name)
    
    @classmethod
    def load(cls, obj, encrypted=None):
        if not isinstance(obj, six.string_types):
            return obj
        return cls(obj, encrypted)
    
    @classmethod
    def dump(cls, obj, decrypt=True):
        if isinstance(obj, cls):
            return obj.get_value(decrypt=decrypt)
        else:
            return obj
    
    @classmethod
    def _extract_value(cls, obj):
        if not isinstance(obj, cls):
            return obj
        return obj._value if obj._value is not None else obj.string
    
    @classmethod
    def startswith(cls, s, sub):
        return cls._extract_value(s).startswith(cls._extract_value(sub))
    
    @classmethod
    def endswith(cls, s, sub):
        return cls._extract_value(s).endswith(cls._extract_value(sub))
    
    @classmethod
    def concat(cls, *args):
        s = ''
        for arg in args:
            if isinstance(arg, cls):
                if arg.encrypted:
                    raise TypeError("Cannot concatenate encrypted values")
                s += arg.string
                
            else:
                s += arg
        return cls(s, False)
    
    def __init__(self, s, encrypted):
        self.string = s
        
        self.names = self.get_reference_pattern().findall(s)
        self.NAMES.update(self.names)
        
        self._encrypted = encrypted
        
        self._value = None if self.names else self.string
    
    def get_value(self, decrypt=True):
        if not self._value:
            value = self.string
            for name in self.names:
                pattern = self.get_reference_pattern(name)
                encrypted = self._encrypted if decrypt else False
                var_value = self._VAR_VALUES[name].get_value(encrypted=encrypted)
                value = pattern.sub(var_value, value)
            self._value = value
        return self._value
    
    def __eq__(self, other):
        if isinstance(other, six.string_types):
            return self.string == other
        else:
            return self.string == other.string
    
    def __hash__(self):
        return hash(self.string)
    
    def __str__(self):
        if self._value:
            return self._value
        else:
            return self.string
    
    def __repr__(self):
        value_str = ',value={!r}'.format(self._value) if self._value else ''
        return 'varstring({}{})'.format(self.string, value_str)

def batch(iterable, n):
    l = len(iterable)
    for ndx in range(0, l, n):
        yield iterable[ndx:min(ndx + n, l)]