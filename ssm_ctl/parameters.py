from __future__ import absolute_import, print_function

import six
import re

class SSMClient(object):
    CLIENT_FACTORY = None
    _CLIENT = None
    
    @classmethod
    def get_client(cls, refresh=False):
        if cls._CLIENT and not refresh:
            return cls._CLIENT
        if cls.CLIENT_FACTORY:
            cls._CLIENT = cls.CLIENT_FACTORY()
        else:
            import boto3
            cls._CLIENT = boto3.client('ssm')
        return cls._CLIENT
    
    @classmethod
    def batch_put(cls, *args):
        client = cls.get_client()
        responses = []
        for parameters in _batch(args, 10):
            for parameter in args:
                if parameter.disable:
                    continue
                kwargs = {
                    'Name': parameter.name,
                    'Type': parameter.type,
                    'Value': parameter.value,
                }
                
                if parameter.allowed_pattern:
                    kwargs['AllowedPattern'] = parameter.allowed_pattern
                
                if parameter.description:
                    kwargs['Description'] = parameter.description
                
                if parameter.key_id:
                    kwargs['KeyId'] = parameter.key_id
                
                if parameter.overwrite:
                    kwargs['Overwrite'] = parameter.overwrite
                
                response = client.put_parameter(
                    **kwargs
                    )
                responses.append(response)
        
    @classmethod
    def get(cls, *args, **kwargs):
        invalid_parameter_names = []
        parameters = []
        
        if kwargs.get('full', False):
            #TODO: catch exceptions, store as invalid
            for name in args:
                parameter_versions = cls.get_versions(name, with_decryption=kwargs.get('with_decryption'))
                parameters.append(parameter_versions[0])
        else:
            client = cls.get_client()
            for names in _batch(args, n=10):
                response = client.get_parameters(
                    names = names,
                    with_decryption=kwargs.get('with_decryption'),
                    )
                invalid_parameter_names.extend(response['InvalidParameters'])
                parameters.extend(SSMParameter.load(p) for p in response['Parameters'])
        
        if invalid_parameter_names:
            raise KeyError("Invalid parameter names {}".format(', '.join(invalid_parameter_names)))
        return parameters
    
    @classmethod
    def get_versions(cls, name, with_decryption=None):
        client = cls.get_client()
        paginator = client.get_paginator('get_parameter_history')
        parameter_versions = []
        
        for response in paginator.paginate(
                Name=name,
                WithDecryption=bool(with_decryption)):
            for item in response['Parameters']:
                parameter = SSMParameter.load(item)
                parameter_versions.append(parameter)
        
        parameter_versions.sort(key=lambda p: p.version, reverse=True)
        return parameter_versions
    
    @classmethod
    def get_path(cls, path, names_only=False, full=False, with_decryption=None, recursive=True, parameter_filters=[]):
        if names_only and full:
            raise ValueError("Can't specify both names_only and full")
        client = cls.get_client()
        paginator = client.get_paginator('get_parameters_by_path')
        names = []
        parameters = []
        
        for response in paginator.paginate(
                Path=path,
                Recursive=recursive,
                ParameterFilters=parameter_filters,
                WithDecryption=bool(with_decryption)):
            if names_only or full:
                names.extend(item['Name'] for item in response['Parameters'])
            else:
                parameters.extend(SSMParameter.load(item) for item in response['Parameters'])
        
        if names_only:
            return names
        elif full:
            return cls.get(*names, full=True, with_decryption=with_decryption)
        else:
            return parameters
    
    @classmethod
    def delete(cls, *args):
        client = cls.get_client()
        responses = []
        for names in _batch(args, 10):
            response = client.delete_parameters(Names=names)
            responses.append(response)
    
    @classmethod
    def delete_path(cls, path, recursive=True, parameter_filters=[]):
        names = cls.get_path(path, recursive=recursive, parameter_filters=parameter_filters)
        return cls.delete(*names)

class SSMParameter(object):
    NAME_PATTERN = r'^(/[a-zA-Z0-9.-_]+)+$'
    
    OVERWRITE_DEFAULT = False
    
    @classmethod
    def load(cls, obj):
        type = obj.get('Type')
        if not type:
            if 'KeyId' in obj:
                type = 'SecureString'
            elif not isinstance(obj['Value'], six.string_types):
                type = 'StringList'
            else:
                type = 'String'
            type = 'SecureString' if 'KeyId' in obj else 'String'
        
        parameter = cls(obj['Name'], type, obj['Value'],
            allowed_pattern=obj.get('AllowedPattern'),
            description=obj.get('Description'),
            key_id=obj.get('KeyId'),
            overwrite=obj.get('Overwrite'),
            disable=obj.get('Disable'))
        parameter.version = obj.get('Version')
        parameter.last_modified_date = obj.get('LastModifiedDate')
        parameter.last_modified_user = obj.get('LastModifiedUser')
        return parameter
    
    def dump(self):
        data = {
            'Name': self.name,
            'Type': self.type,
            'Value': self.value,
        }
        
        if self.allowed_pattern:
            data['AllowedPattern'] = self.allowed_pattern
        
        if self.description:
            data['Description'] = self.description
        
        if self.key_id:
            data['KeyId'] = self.key_id
        
        return data
        
    def __init__(self, name, type, value,
                 allowed_pattern=None,
                 description=None,
                 key_id=None,
                 overwrite=None,
                 disable=None):
        
        if not re.match(self.NAME_PATTERN, name):
            raise ValueError("Invalid name: {}".format(name))
        
        self.name = name
        self.type = type
        self._value = value 
        
        self.allowed_pattern = allowed_pattern
        self.description = description
        self.key_id = key_id
        self._overwrite = overwrite
        
        self.disable = disable if disable is not None else False
        
        self.version = None
        self.last_modified_date = None
        self.last_modified_user = None
        
        if (self.key_id and not self.type == 'SecureString') or (self.type == 'SecureString' and not self.key_id):
            raise ValueError('Mismatched secure inputs')
    
    def __str__(self):
        return repr(self)
    
    def __repr__(self):
        kwargs=[
            'name={!r}'.format(self.name),
            'type={!r}'.format(self.type),
            'value={!r}'.format(self.value),
        ]
        for name in ['allowed_pattern', 'description', 'key_id', 'overwrite', 'disable']:
            if getattr(self, name):
                kwargs.append('{}={!r}'.format(name, getattr(self, name)))
        return 'SSMParameter({})'.format(
            ','.join(kwargs))
    
    @property
    def value(self):
        return self._value if isinstance(self._value, six.string_types) else ','.join(self._value)
    
    @property
    def secure(self):
        return self.type == 'SecureString'
    
    @property
    def overwrite(self):
        if self._overwrite is not None:
            return bool(self._overwrite)
        else:
            return self.OVERWRITE_DEFAULT
    
    def put(self):
        SSMClient.batch_put(self)

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
        if self.name and not re.search(self.name, parameter.name):
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

def _batch(iterable, n=1):
    l = len(iterable)
    for ndx in range(0, l, n):
        yield iterable[ndx:min(ndx + n, l)]