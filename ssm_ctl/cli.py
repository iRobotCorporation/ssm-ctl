"""Command line functions

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
from six.moves import input, range
import sys
import argparse
import getpass
import os.path

import yaml

from .ssm import SSMClient
from .parameters import SSMParameter, VarString
from .files import parse_parameter_file, Input, InputError, ParameterFileData, compile_parameter_file

def add_common_args(parser, defaults):
    verbose_group = parser.add_mutually_exclusive_group()
    verbose_group.add_argument('--quiet', '-q', action='store_const', const=-1, dest='verbose')
    verbose_group.add_argument('--verbose', '-v', action='count')

def add_input_args(parser, defaults, secure=True):
    input_group = parser.add_argument_group()
    input_group.add_argument('--input', nargs=2, action='append', default=[])
    if secure:
        input_group.add_argument('--secure-input', nargs=2, action='append', default=[])

def load_inputs_from_args(args):
    inputs = {}
    for input_name, input_value in args.input:
        input = Input(input_name, 'String')
        input.set_value(input_value)
        inputs[input_name] = input
    
    for input_name, input_value in args.secure_input:
        input = Input(input_name, 'SecureString')
        input.set_value(input_value, encrypted=True)
        inputs[input_name] = input
    
    return inputs

def add_echo_args(parser, defaults):
    echo_group = parser.add_mutually_exclusive_group()
    echo_group.add_argument('--echo', action='store_true')
    echo_group.add_argument('--no-echo', action='store_false', dest='echo')
    defaults['echo'] = None

def add_prompt_args(parser, defaults):
    prompt_group = parser.add_mutually_exclusive_group()
    prompt_group.add_argument('--prompt', action='store_true')
    prompt_group.add_argument('--no-prompt', action='store_false', dest='prompt')
    defaults['prompt'] = True

def load_parameter_files(parameter_files, inputs=None, var_mode='all', args=None):
    if inputs is None:
        inputs = {}
    parameters = {}
    base_paths = []
    for parameter_file in parameter_files:
        six.print_("Loading {}...".format(parameter_file.name))
        data = parse_parameter_file(yaml.safe_load(parameter_file), var_mode=var_mode)
        Input.merge_inputs(inputs, data.inputs)
        parameters.update(data.parameters)
        base_paths.extend(data.base_paths)
    return ParameterFileData(inputs, parameters, base_paths)

def process_inputs(inputs, prompt, echo, args=None):
    try:
        six.print_("Processing inputs...")
        resolver = Input.get_resolver(inputs, prompt=prompt, echo=echo)
        VarString.resolve(resolver)
    except InputError as e:
        sys.stderr.write('{}\n'.format(e))
        sys.exit(1)

def flush(paths, names, args=None):
    for path in paths:
        six.print_("Flushing base path {}...".format(path))
        diff = SSMClient.diff_path(path, names)
        SSMClient.delete(diff.remove)

def print_diff(diff, args=None):
    lines = []
        
    lines.append('*** PARAMETERS TO ADD ***')
    lines.extend(diff.add)
    lines.append('')
    
    lines.append('*** PARAMETERS TO OVERWRITE ***')
    lines.extend(diff.overwrite)
    lines.append('')
    
    lines.append('*** PARAMETERS TO REMOVE ***')
    lines.extend(diff.remove)
    six.print_('\n'.join(lines))

def _load_files_main_helper(parser, args, add_parser_args=None, load_parameter_files_kwargs={}):
    parser.add_argument('parameter_file', type=argparse.FileType('r'), nargs='+')
    
    if add_parser_args:
        add_parser_args(parser)
    
    defaults = {}
    
    add_input_args(parser, defaults)
    add_echo_args(parser, defaults)
    add_prompt_args(parser, defaults)
    
    parser.set_defaults(**defaults)
    args = parser.parse_args(args=args)
    
    inputs = load_inputs_from_args(args)
    
    inputs, parameters, base_paths = load_parameter_files(args.parameter_file, inputs=inputs, args=args, **load_parameter_files_kwargs)
    
    process_inputs(inputs, prompt=args.prompt, echo=args.echo, args=args)
    
    names = SSMParameter.get_names(six.itervalues(parameters))
    
    base_paths = [VarString.dump(p) for p in base_paths]
    
    return args, names, parameters, base_paths

def push_main(args=None):
    def add_parser_args(parser):
        parser.add_argument('--overwrite', action='store_true', default=False, help='Allow overwrites by default')
        parser.add_argument('--delete', action='store_true')
        
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--diff', action='store_true')
    
    parser = argparse.ArgumentParser()
    
    args, names, parameters, base_paths = _load_files_main_helper(parser, args, add_parser_args=add_parser_args)
    
    if args.diff:
        diff = SSMClient.diff_paths(base_paths, names)

    if args.dry_run:
        kwargs = {
            'ignore_disabled': True
        }
        data = compile_parameter_file(six.itervalues(parameters), **kwargs)
        
        six.print_('*** PARAMETERS TO PUSH ***')
        six.print_(yaml.dump(data, default_flow_style=False))

        if args.diff:
            print_diff(diff, args=args)
        return
    
    if args.diff:
        print_diff(diff, args=args)
    
    if args.delete:
        six.print_("Processing removed parameters...")
        flush(base_paths, names, args=args)
    
    six.print_("Putting parameters")
    SSMParameter.OVERWRITE_DEFAULT = args.overwrite
    SSMClient.batch_put(list(six.itervalues(parameters)), dumper=SSMParameter.ssm_client_dumper)

def diff_main(args=None):
    parser = argparse.ArgumentParser()
    
    load_parameter_files_kwargs = {
        'var_mode': 'reduced'
    }
    
    args, names, parameters, base_paths = _load_files_main_helper(parser, args, load_parameter_files_kwargs=load_parameter_files_kwargs)
    
    diff = SSMClient.diff_paths(base_paths, names)
    
    print_diff(diff, args=args)

def delete_main(args=None):
    parser = argparse.ArgumentParser()
    
    load_parameter_files_kwargs = {
        'var_mode': 'reduced'
    }
    
    args, names, parameters, base_paths = _load_files_main_helper(parser, args, load_parameter_files_kwargs=load_parameter_files_kwargs)
    
    flush(base_paths, names, args=args)
    
    six.print_("Deleting parameters")
    SSMClient.delete(names)

def download_main(args=None):
    parser = argparse.ArgumentParser()
    
    parser.add_argument('path', nargs='+')
    parser.add_argument('--output', '-o', type=argparse.FileType('w'))
    parser.add_argument('--reencrypt-key-id')
    
    args = parser.parse_args(args=args)
    
    if args.reencrypt_key_id:
        SSMClient.set_reencrypt_key(args.reencrypt_key_id)
    
    base_paths = args.path
    if len(base_paths) == 1:
        base_paths = base_paths[0]
    
    parameters = []
    for path in args.path:
        parameters.extend(SSMClient.get_path(path, full=True, loader=SSMParameter.ssm_client_loader))
    
    ssm_param_file_data = compile_parameter_file(parameters, base_paths)
    
    if not args.output:
        args.output = sys.stdout
    
    yaml.safe_dump(ssm_param_file_data, args.output, default_flow_style=False)

def encrypt_main(args=None):
    """
    ssm-ctl encrypt PARAMETER_FILE PATH VALUE [PATH VALUE]...
    ssm-ctl encrypt --prompt [--echo] PARAMETER_FILE PATH [PATH]...
    """
    
    parser = argparse.ArgumentParser()
    
    parser.add_argument('parameter_file')
    parser.add_argument('key_id')
    parser.add_argument('args', nargs='+')
    prompt_group = parser.add_argument_group()
    prompt_group.add_argument('--prompt', action='store_true')
    prompt_group.add_argument('--echo', action='store_true')
    
    args = parser.parse_args(args=args)
    
    input_fn = getpass.getpass if not args.echo else input
    
    if os.path.exists(args.parameter_file):
        with open(args.parameter_file, 'r') as fp:
            parameter_file = yaml.safe_load(fp)
    else:
        parameter_file = {}
    
    args.key_id = SSMClient.format_key_id(args.key_id)
    
    data = {}
    if not args.prompt:
        if not len(args.args) % 2 == 0:
            parser.error("Provide a value for every path")
        for i in range(0, len(args.args), 2):
            data[args.args[i]] = SSMClient.encrypt(args.args[i+1], args.key_id)
    else:
        for path in args.args:
            value = input_fn('{}: '.format(path))
            data[path] = SSMClient.encrypt(value, args.key_id)
    
    for path, value in six.iteritems(data):
        data = {
            'EncryptedValue': value,
            'KeyId': args.key_id,
        }
        if path not in parameter_file:
            parameter_file[path] = data
        if path in parameter_file:
            if not isinstance(parameter_file[path], dict):
                parameter_file[path] = {}
            parameter_file[path].update(data)
    
    with open(args.parameter_file, 'w') as fp:
        yaml.safe_dump(parameter_file, fp, default_flow_style=False)
    
def decrypt_main(args=None):
    parser = argparse.ArgumentParser()
    
    parser.add_argument('parameter_file', type=argparse.FileType('r'))
    
    args = parser.parse_args(args=args)
    
    parameter_file = yaml.safe_load(args.parameter_file)
    
    for path, data in six.iteritems(parameter_file):
        if isinstance(data, dict) and 'EncryptedValue' in data:
            ciphertext = data['EncryptedValue']
            key_id = data.get('KeyId')
            plaintext = SSMClient.decrypt(ciphertext, key_id)
            six.print_('{}: {}'.format(path, plaintext))
    

def main(args=None):
    if args is None:
        args = sys.argv[1:]
    
    commands = ['push', 'diff', 'delete', 'download', 'encrypt', 'decrypt']
    
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=commands)
    
    if (not args
        or (len(args) == 1 and args[0] in ['--help', '-h'])
        or args[0] not in commands):
        parser.print_help()
        sys.exit(1)
    
    command = args[0]
    return globals()['{}_main'.format(command)](args[1:])