# ssm-ctl

## Quickstart

### Install

```
git clone https://github.com/iRobotCorporation/ssm-ctl
pip install ./ssm-ctl
```

### Download your existing parameters

`ssm-ctl download -o ssm.yaml /`

### Push changes

`ssm-ctl push [--overwrite] ssm.yaml`

If there are existing parameters, they won't be overwritten (this is a feature of SSM's API).
To overwrite any existing parameters, use the `--overwrite` flag. 

## The SSM parameters file

The parameters file contains parameter names with their associated values and settings, as well
as configurations for deleting parameters in advance of pushing, and for prompting for user input.

### Parameters

An entry in the parameter file looks like:

```yaml
/My/Parameter/Name:
  Value: my_parameter_value
  Type: String | StringList | SecureString
  KeyId: kms-key-id
  AllowedPattern: regex
  Description: The description of the parameter
  Disable: False
```

`Value` is required, all other fields are optional.

`Type` is inferred if not specified. If `Value` is a list, `Type` is `StringList`.
If `KeyId` is specified, `Type` is `SecureString`.
Otherwise `Type` is `String`.

`AllowedPattern` is the SSM API input; it is not used client-side.

If `Disable` is present and set to `True`, `ssm-ctl` will ignore the parameter.

Only `Value` is required. If only `Value` would be specified, it can be given inline:

```yaml
/My/OtherParameter: my_other_parameter_value
/My/ListParameter:
- value_1
- value_2
```

### Paths to flush

You can define paths to remove in advance of setting your parameters.
This is often the common prefix of your parameters. These paths are set with the `.FLUSH` key, either a string or a list of strings

```yaml
.FLUSH: /My

/My/Parameter/Name: ...
/My/OtherParameter: ...
```

A existing parameter `/My/SeparateParameter`, whether from a previous `ssm-ctl push` or another source, would get deleted.

Note that you need to specify `--delete` for `ssm-ctl push` to use this functionality. `ssm-ctl delete` will use it always.

### Variables and inputs

A parameter file can use variables to become a template. Variables are used like `$(VarName)`.
Variables can be present in any string. There are two ways to provide values for variables.

On the command line, inputs can be specified as `--input name value`.

In the parameters file, under `.INPUTS`, definitions can be provided to prompt the user for input (if they are not provided on the command line).

```yaml
.INPUTS:
  Prefix:
    Description: The parameter name prefix
    AllowedPattern: ^/\w+$
  Value:
    Type: StringList

$(Prefix)/Name:
  Value: $(Value)
```

## The ssm-ctl tool

### ssm-ctl download

`ssm-ctl download [--output FILE] PATH [PATH]...`

Produce a parameter file from the parameters at the given paths, saved to the given file or stdout.

### ssm-ctl push

`ssm-ctl push [--overwrite] [--delete] [--input NAME VALUE]... PARAMETER_FILE...`

Load the given parameter files and push the parameters to SSM.
* `--overwrite` Default to overwriting existing parameters
* `--delete` Flush the paths given in the parameter files before pushing
* `--input NAME VALUE` Set the variable `NAME` to `VALUE`

### ssm-ctl delete

`ssm-ctl delete [--input NAME VALUE]... PARAMETER_FILE...`

Load the given parameter files, flush the defined paths, and delete the parameters.