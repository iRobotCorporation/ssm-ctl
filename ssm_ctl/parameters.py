"""Classes to manipulate SSM parameters

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

from __future__ import absolute_import, print_function

import six
import re
import base64

from .ssm import SSMClient
from .util import VarString

class SSMParameter(object):
    NAME_PATTERN = r'^(/[a-zA-Z0-9.-_]+)+$'
    
    OVERWRITE_DEFAULT = False
    
    @classmethod
    def ssm_client_loader(cls, item, base_path):
        return cls.load(item, var_mode='off', allow_secure_string_value=True, base_path=base_path, strip_base_path=True)
    
    @classmethod
    def load(cls, obj, var_mode='all', allow_secure_string_value=False, base_path=None, strip_base_path=False):
        def _load_varstring_off(o, **kwargs):
            return o
        load_varstring1 = _load_varstring_off if var_mode in ['off'] else VarString.load
        load_varstring2 = _load_varstring_off if var_mode in ['off', 'reduced'] else VarString.load
        
        name = obj['Name']
        if strip_base_path and base_path and VarString.startswith(name, VarString.concat(base_path, '/')):
            name = name[len(base_path)+1:]
        name = load_varstring1(name)
        
        param_type = obj.get('Type')
        if not param_type:
            if 'KeyId' in obj:
                param_type = 'SecureString'
            elif not isinstance(obj['Value'], six.string_types):
                param_type = 'StringList'
            else:
                param_type = 'String'
            param_type = 'SecureString' if 'KeyId' in obj else 'String'
        
        key_id = load_varstring2(obj.get('KeyId'))
        
        value = None
        encrypted = False
        if param_type == 'SecureString':
            if not key_id:
                raise ValueError("SecureString requires KeyId")
            if 'EncryptedValue' in obj:
                value = load_varstring2(obj['EncryptedValue'])
                encrypted = True
            elif 'Input' in obj:
                value = load_varstring2(VarString.single_reference(obj['Input']), encrypted=True)
            elif 'Value' in obj:
                if allow_secure_string_value:
                    value = obj['Value']
                else:
                    raise ValueError("Value cannot be used with SecureString")
        elif isinstance(obj.get('Value'), list):
            value = [load_varstring2(s) for s in obj['Value']]
        else:
            value = load_varstring2(obj.get('Value'))
        
        allowed_pattern = load_varstring2(obj.get('AllowedPattern'))
        
        description = obj.get('Description')
        
        overwrite = obj.get('Overwrite')
        
        disable = load_varstring1(obj.get('Disable', obj.get('Disabled')))
        
        parameter = cls(name, param_type, value,
            allowed_pattern=allowed_pattern,
            description=description,
            key_id=key_id,
            overwrite=overwrite,
            disable=disable,
            encrypted=encrypted,
            base_path=base_path)
        
        parameter.version = obj.get('Version')
        parameter.last_modified_date = obj.get('LastModifiedDate')
        parameter.last_modified_user = obj.get('LastModifiedUser')
        
        return parameter
    
    def dump(self, full_name=True):
        name = self.get_name(full=full_name)
        
        data = {
            'Name': name,
            'Type': self.type,
        }
        if self.type == 'SecureString' and self._encrypted:
            data['EncryptedValue'] = self.get_value(decrypt=False)
        else:
            data['Value'] = self.get_value()
        
        if self.allowed_pattern:
            data['AllowedPattern'] = self.allowed_pattern
        
        if self.description:
            data['Description'] = self.description
        
        if self.key_id:
            data['KeyId'] = self.key_id
        
        return data
    
    @classmethod
    def ssm_client_dumper(cls, parameter):
        if parameter.disable:
            return None
        item = {
            'Name': parameter.get_name(),
            'Type': parameter.type,
            'Value': parameter.get_value(),
        }
        
        if parameter.allowed_pattern:
            item['AllowedPattern'] = parameter.allowed_pattern
        
        if parameter.description:
            item['Description'] = parameter.description
        
        if parameter.key_id:
            item['KeyId'] = parameter.key_id
        
        if parameter.overwrite:
            item['Overwrite'] = parameter.overwrite
        return item
    
    @classmethod
    def get_names(cls, parameters):
        return [p.get_name() for p in parameters if not p.disable]
    
    def __init__(self, name, type, value,
                 allowed_pattern=None,
                 description=None,
                 key_id=None,
                 overwrite=None,
                 disable=None,
                 encrypted=None,
                 base_path=None):
        
        self._name = name
        self._type = type
        self._value = value
        self._resolved_value = None
        
        self._allowed_pattern = allowed_pattern
        self._description = description
        self._key_id = key_id
        self._overwrite = overwrite
        
        self._disable = disable
        
        self._encrypted = encrypted
        
        self._base_path = base_path
        
        self.version = None
        self.last_modified_date = None
        self.last_modified_user = None
        
        if (self._key_id and not self._type == 'SecureString') or (self._type == 'SecureString' and not self._key_id):
            raise ValueError('Mismatched secure inputs on parameter {}'.format(name))
    
    def __str__(self):
        return repr(self)
    
    def __repr__(self):
        kwargs=[
            'name={!r}'.format(self.get_name()),
            'type={!r}'.format(self.type),
            'value={!r}'.format(self.get_value(decrypt=False)),
        ]
        for name in ['allowed_pattern', 'description', 'key_id', 'overwrite', 'disable']:
            if getattr(self, name):
                kwargs.append('{}={!r}'.format(name, getattr(self, name)))
        return 'SSMParameter({})'.format(
            ','.join(kwargs))
    
    @property
    def base_path(self):
        return VarString.dump(self._base_path)
    
    def get_name(self, full=True):
        name = VarString.dump(self._name)
        if not full or name.startswith('/'):
            return name
        return '{}{}{}'.format(self.base_path, '/', name)
    
#     @property
#     def name(self):
#         name = VarString.dump(self._name)
# #         if not re.match(self.NAME_PATTERN, name):
# #             raise ValueError("Invalid name: {}".format(name))
#         return name
    
    @property
    def type(self):
        return self._type
    
    def get_value(self, decrypt=True):
        if not self._resolved_value:
            if self._value is None:
                if self.disable:
                    return self._value
                raise ValueError("Value missing for parameter {}".format(self.get_name()))
            value = VarString.dump(self._value, decrypt=decrypt)
            if not isinstance(value, six.string_types):
                value = ','.join(VarString.dump(v, decrypt=decrypt) for v in self._value)
            if self._encrypted and decrypt:
                value = SSMClient.decrypt(value)
            self._resolved_value = value
        return self._resolved_value
    
    @property
    def allowed_pattern(self):
        return VarString.dump(self._allowed_pattern)
    
    @property
    def description(self):
        return self._description
    
    @property
    def key_id(self):
        return VarString.dump(self._key_id)
    
    @property
    def secure(self):
        return self.type == 'SecureString'
    
    @property
    def overwrite(self):
        if self._overwrite is not None:
            return bool(self._overwrite)
        else:
            return self.OVERWRITE_DEFAULT
    
    @property
    def disable(self):
        if self._disable is None:
            return False
        else:
            return bool(VarString.dump(self._disable))
    
    def put(self):
        SSMClient.batch_put([self], dumper=self.ssm_client_dumper)

class SSMParameterRequirement(object):
    def __init__(self):
        self.name = None #regex
        self.allowed = None #bool
        self.type = None #string
        self.value = None #regex
        self.secure = None #bool
        self.key_id = None #regex
        self.allowed_pattern = None #string
        self.description = None
    
    def validate(self, parameter):
        if self.name and not re.search(self.name, parameter.get_name()):
            return True, []
        errors = []
        if self.type and parameter.type != self.type:
            errors.append("type is {} not {}".format(parameter.type, self.type))
        if self.value and not re.search(self.value, parameter.value):
            errors.append("value {} is invalid", parameter.value)
        if self.secure and not parameter.secure:
            errors.append("is not secure")
        if self.key_id and not re.search(self.key_id, parameter.key_id):
            errors.append("key id {} is invalid".format(parameter.key_id))
        if self.allowed_pattern and self.allowed_pattern != parameter.allowed_pattern:
            errors.append("allowed pattern {} is invalid".format(parameter.allowed_pattern))
        return not bool(errors), errors