from __future__ import absolute_import, print_function

import six
import sys
import argparse

import yaml

from .parameters import SSMParameter, SSMClient, VarString
from .files import parse_parameter_file, Input, InputError, FLUSH_KEY

def push_main(args=None):
    parser = argparse.ArgumentParser()
    
    parser.add_argument('parameter_file', type=argparse.FileType('r'), nargs='+')
    parser.add_argument('--overwrite', action='store_true', default=False, help='Allow overwrites by default')
    parser.add_argument('--delete', action='store_true')
    parser.add_argument('--input', nargs=2, action='append', default=[])
    parser.add_argument('--secure-input', nargs=2, action='append', default=[])
    parser.add_argument('--echo', action='store_true')
    parser.add_argument('--no-echo', action='store_false', dest='echo')
    parser.add_argument('--no-prompt', action='store_false', dest='prompt')
    parser.set_defaults(prompt=True, echo=None)
    
    args = parser.parse_args(args=args)
    
    SSMParameter.OVERWRITE_DEFAULT = args.overwrite
    
    inputs = {}
    for input_name, input_value in args.input:
        input = Input(input_name, 'String')
        input.set_value(input_value)
        inputs[input_name] = input
    
    for input_name, input_value in args.secure_input:
        input = Input(input_name, 'SecureString')
        input.set_value(input_value, encrypted=True)
        inputs[input_name] = input
    
    parameters = {}
    flush = []
    for parameter_file in args.parameter_file:
        six.print_("Processing {}...".format(parameter_file.name))
        data = parse_parameter_file(yaml.load(parameter_file))
        Input.merge_inputs(inputs, data.inputs)
        parameters.update(data.parameters)
        flush.extend(data.flush)
    
    six.print_("Processing inputs...")
    try:
        resolver = Input.get_resolver(inputs, prompt=args.prompt, echo=args.echo)
        VarString.resolve(resolver)
    except InputError as e:
        parser.exit(1, '{}\n'.format(e))
    
    if args.delete and flush:
        six.print_("Flushing existing parameters...")
        for path in flush:
            six.print_("Flushing {}...".format(path))
            SSMClient.delete_path(path)
    
    six.print_("Putting parameters")
    SSMClient.batch_put(*six.itervalues(parameters))

def delete_main(args=None):
    parser = argparse.ArgumentParser()
    
    parser.add_argument('parameter_file', type=argparse.FileType('r'), nargs='+')
    parser.add_argument('--input', nargs=2, action='append', default=[])
    
    args = parser.parse_args(args=args)
    
    input_values = dict(args.input)
    
    parameters = {}
    flush = []
    try:
        for parameter_file in args.parameter_file:
            six.print_("Processing {}...".format(parameter_file.name))
            data = parse_parameter_file(yaml.load(parameter_file), input_values)
            parameters.update(data.parameters)
            flush.extend(data.flush)
    except InputError as e:
        parser.exit(1, '{}\n'.format(e))
    
    for path in flush:
        six.print_("Flushing {}...".format(path))
        SSMClient.delete_path(path)
    
    six.print_("Deleting parameters")
    SSMClient.delete(*[p.name for p in six.itervalues(parameters)])

def download_main(args=None):
    parser = argparse.ArgumentParser()
    
    parser.add_argument('path', nargs='+')
    parser.add_argument('--output', '-o', type=argparse.FileType('w'))
    
    args = parser.parse_args(args=args)
    
    ssm_param_file_data = {}
    
    flush = args.path
    if len(flush) == 1:
        flush = flush[0]
    
    ssm_param_file_data[FLUSH_KEY] = flush
    
    for path in args.path:
        parameters = SSMClient.get_path(path, full=True)
        for parameter in parameters:
            data = parameter.dump()
            name = data.pop('Name')
            ssm_param_file_data[name] = data
    
    if not args.output:
        args.output = sys.stdout
    
    yaml.dump(ssm_param_file_data, args.output, default_flow_style=False)

def main(args=None):
    if args is None:
        args = sys.argv[1:]
    
    commands = ['push', 'delete', 'download']
    
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=commands)
    
    if (not args
        or (len(args) == 1 and args[0] in ['--help', '-h'])
        or args[0] not in commands):
        parser.print_help()
        sys.exit(1)
    
    command = args[0]
    return globals()['{}_main'.format(command)](args[1:])