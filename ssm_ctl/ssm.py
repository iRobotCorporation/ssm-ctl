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
import base64
import collections

from . import util

PathDiff = collections.namedtuple('PathDiff', ['add', 'overwrite', 'remove'])

class SSMClient(object):
    """Client for SSM Parameter store, and crypto"""
    
    @classmethod
    def _default_session_factory(cls):
        """Default session factory that creates a boto3 session."""
        import boto3
        return boto3.session.Session()

    @classmethod
    def _default_client_factory(cls, session, name):
        """Default client factory that creates a client from the provided session."""
        return session.client(name)

    SESSION_FACTORY = _default_session_factory
    CLIENT_FACTORY = _default_client_factory

    _SESSION = None
    _CLIENT = None

    @classmethod
    def _session(cls):
        """Use the defined session factory to create an object that acts like a boto3 session.
        Defaults to boto3.session.Session(); set SESSION_FACTORY to inject a different session
        factory.
        You should not need to call this method yourself; it is meant for internal use."""
        if cls._SESSION is None:
            if cls.SESSION_FACTORY:
                cls._SESSION = cls.SESSION_FACTORY()
            else:
                cls._SESSION = cls._default_session_factory()
        return cls._SESSION

    @classmethod
    def _client(cls):
        """Use the defined client factory to create an object that acts like a boto3 client.
        Defaults to _session().client("ssm"); set CLIENT_FACTORY to inject a different client
        factory."""
        if cls._CLIENT is None:
            if cls.CLIENT_FACTORY:
                client = cls.CLIENT_FACTORY(cls._session(), "ssm")
            else:
                client = cls._default_client_factory(cls._session(), "ssm")
            cls._CLIENT = client
        return cls._CLIENT
    
    _REGION = None
    _ACCOUNT = None
    
    @classmethod
    def get_region(cls):
        """Get the region from the session"""
        if not cls._REGION:
            cls._REGION = cls._session().region_name
        return cls._REGION
    
    @classmethod
    def get_account(cls):
        """Call STS.GetCallerIdentity (using the session) to get the current account"""
        if not cls._ACCOUNT:
            cls._ACCOUNT = cls._session().client('sts').get_caller_identity()['Account']
        return cls._ACCOUNT   
    
    @classmethod
    def batch_put(cls, parameters, dumper=None):
        """Store the given parameters in SSM"""
        if not dumper:
            dumper = lambda o: o
        client = cls._client()
        responses = []
        for parameter_batch in util.batch(parameters, 10):
            for parameter in parameter_batch:
                kwargs = dumper(parameter)
                if not kwargs:
                    continue
                
                response = client.put_parameter(
                    **kwargs
                    )
                responses.append(response)
    
    @classmethod
    def _load_parameters_from_response(cls, response, loader, reencrypt, limit=None, base_path=None):
        if not loader:
            loader = lambda o: o
        parameters = []
        for i, item in enumerate(response['Parameters']):
            if limit is not None and i > limit:
                break
            # Encrypted SecureStrings aren't in AWS Encryption SDK format, so reencrypt them with it
            if reencrypt and item['Type'] == 'SecureString':
                key_id = cls._get_reencrypt_key(item['Name'], item['KeyId'])
                item['EncryptedValue'] = SSMClient.encrypt(item.pop('Value'), key_id)
            parameter = loader(item, base_path)
            parameters.append(parameter)
        return parameters
    
    @classmethod
    def get(cls, names, full=False, reencrypt=True, loader=None, base_path=None):
        """Get the specified parameter(s).
        :param full: When False, get only the name, type, and value.
        """
        if isinstance(names, six.string_types):
            names = [names]
        
        invalid_parameter_names = []
        parameters = []
        
        if full:
            #TODO: catch exceptions, store as invalid
            for name in names:
                try:
                    parameter_versions = cls.get_versions(name, reencrypt=reencrypt, limit=1, loader=loader, base_path=base_path)
                except Exception as e:
                    invalid_parameter_names.append(name)
                parameters.append(parameter_versions[0])
        else:
            client = cls._client()
            for name_batch in util.batch(names, 10):
                response = client.get_parameters(
                    Names=name_batch,
                    WithDecryption=reencrypt)
                invalid_parameter_names.extend(response['InvalidParameters'])
                parameters.extend(cls._load_parameters_from_response(response, loader, reencrypt=reencrypt, base_path=base_path))
        
        if invalid_parameter_names:
            raise KeyError("Invalid parameter names {}".format(', '.join(invalid_parameter_names)))
        return parameters
    
    @classmethod
    def get_versions(cls, name, reencrypt=True, limit=None, loader=None, base_path=None):
        client = cls._client()
        paginator = client.get_paginator('get_parameter_history')
        parameter_versions = []
        
        for response in paginator.paginate(
                Name=name,
                WithDecryption=reencrypt):
            load_limit = None
            if limit is not None:
                load_limit = limit - len(parameter_versions)
            
            parameter_versions.extend(cls._load_parameters_from_response(response, loader, reencrypt=reencrypt, limit=load_limit, base_path=base_path))
        
        parameter_versions.sort(key=lambda p: p.version, reverse=True)
        return parameter_versions
    
    @classmethod
    def get_path(cls, path, names_only=False, full=False, reencrypt=True, loader=None, recursive=True, parameter_filters=[]):
        if names_only and full:
            raise ValueError("Can't specify both names_only and full")
        client = cls._client()
        paginator = client.get_paginator('get_parameters_by_path')
        names = []
        parameters = []
        
        for response in paginator.paginate(
                Path=path,
                Recursive=recursive,
                ParameterFilters=parameter_filters,
                WithDecryption=reencrypt):
            if names_only or full:
                names.extend(item['Name'] for item in response['Parameters'])
            else:
                parameters.extend(cls._load_parameters_from_response(response, loader, reencrypt=reencrypt, base_path=path))
        
        if names_only:
            return names
        elif full:
            return cls.get(names, full=True, reencrypt=reencrypt, loader=loader, base_path=path)
        else:
            return parameters
    
    @classmethod
    def diff_path(cls, path, names):
        names_on_path = set(name for name in names if name.startswith(path))
        path_names = set(cls.get_path(path, names_only=True))
        add = names_on_path - path_names
        overwrite = names_on_path & path_names
        remove = path_names - names_on_path
        return PathDiff(sorted(add), sorted(overwrite), sorted(remove))
    
    @classmethod
    def diff_paths(cls, paths, names):
        names = set(names)
        add = set()
        overwrite = set()
        remove = set()
        for path in paths:
            names_on_path = set(name for name in names if name.startswith(path))
            path_names = set(cls.get_path(path, names_only=True))
            add |= (names_on_path - path_names)
            overwrite |= (names_on_path & path_names)
            remove |= (path_names - names_on_path)
        add |= (names - overwrite - remove)
        return PathDiff(sorted(add), sorted(overwrite), sorted(remove))
    
    @classmethod
    def delete(cls, names):
        if isinstance(names, six.string_types):
            names = [names]
        
        client = cls._client()
        responses = []
        for name_batch in util.batch(names, 10):
            response = client.delete_parameters(Names=name_batch)
            responses.append(response)
    
    @classmethod
    def delete_path(cls, path, recursive=True, parameter_filters=[]):
        names = cls.get_path(path, names_only=True, recursive=recursive, parameter_filters=parameter_filters)
        return cls.delete(names)
    
    _MASTER_KEY_PROVIDER = None
    _MASTER_KEYS = set()
    
    @classmethod
    def get_master_key_provider(cls, key_id=None):
        if not cls._MASTER_KEY_PROVIDER:
            import aws_encryption_sdk
            cls._MASTER_KEY_PROVIDER = aws_encryption_sdk.KMSMasterKeyProvider()
        if key_id and key_id not in cls._MASTER_KEYS:
            cls._MASTER_KEY_PROVIDER.add_master_key(key_id)
            cls._MASTER_KEYS.add(key_id)
        return cls._MASTER_KEY_PROVIDER
    
    @classmethod
    def _default_encrypter(cls, plaintext, key_id):
        import aws_encryption_sdk
        ciphertext, _ = aws_encryption_sdk.encrypt(
                source=plaintext,
                key_provider=cls.get_master_key_provider(key_id))
        return base64.b64encode(ciphertext)
    
    @classmethod
    def _default_decrypter(cls, ciphertext):
        import aws_encryption_sdk
        plaintext, _ = aws_encryption_sdk.decrypt(
                source=base64.b64decode(ciphertext),
                key_provider=cls.get_master_key_provider())
        return plaintext
    
    @classmethod
    def _fake_decrypter(cls, ciphertext):
        return '[decrypted]{}'.format(ciphertext)
    
    _ENCRYPTER = _default_encrypter
    _DECRYPTER = _default_decrypter
    
    @classmethod
    def encrypt(cls, plaintext, key_id):
        return cls._ENCRYPTER(plaintext, key_id) 
    
    @classmethod
    def decrypt(cls, ciphertext):
        return cls._DECRYPTER(ciphertext)
    
    _REENCRYPT_KEYS = []
    @classmethod
    def set_reencrypt_key(cls, key_id, name_matcher=None):
        if not name_matcher:
            cls._REENCRYPT_KEYS = []
            if key_id:
                cls._REENCRYPT_KEYS = [(lambda name: True, key_id)]
        elif key_id:
            cls._REENCRYPT_KEYS.append((name_matcher, key_id))
        else:
            cls._REENCRYPT_KEYS.insert(0, (name_matcher, key_id))
    
    @classmethod
    def _get_reencrypt_key(cls, name, default_key_id):
        for matcher, key_id in cls._REENCRYPT_KEYS:
            if matcher(name):
                return key_id
        return default_key_id
    
    @classmethod
    def format_key_id(cls, key_id):
        if not key_id.startswith('arn'):
            key_id = 'arn:aws:kms:{}:{}:{}'.format(
                SSMClient.get_region(),
                SSMClient.get_account(),
                key_id)
        return key_id
