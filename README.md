# ssm-ctl

## Quickstart

### Install

```
git clone https://github.com/iRobotCorporation/ssm-ctl
pip install ./ssm-ctl
```

### Download your existing parameters

```
ssm-ctl download -o ssm.yaml /
```

### Push changes

```
ssm-ctl push [--overwrite] ssm.yaml
```

If there are existing parameters, they won't be overwritten (this is a feature of SSM's API).
To overwrite any existing parameters, use the `--overwrite` flag. 

## The SSM parameters file

The parameters file contains parameter names with their associated values and settings, as well
as configurations for deleting parameters in advance of pushing, and for prompting for user input.

### Parameters

An entry in the parameter file looks like:

```yaml
/My/Parameter/Name:
  Type: String | StringList | SecureString
  Value: my_parameter_value
  KeyId: kms-key-id
  AllowedPattern: regex
  Description: The description of the parameter
  Disable: False
```

`Type` is inferred if not specified. If `Value` is a list, `Type` is `StringList`.
If `KeyId` is specified, `Type` is `SecureString`.
Otherwise `Type` is `String`.

`Value` is required for `String` and `StringList`. For `SecureString` parameters,
see below.

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

A parameter file can use inputs to become a template. Input references are used like `$(InputName)`.
Input references can be present in the name, and the `Value`, `AllowedPattern`, `KeyId`, and `Disable` fields.
There are two ways to provide values for inputs.

On the command line, inputs can be specified as `--input NAME VALUE`, or `SecureString` inputs can be specified as `--secure-input NAME` (see below).

Any input references that do not have corresponding inputs on the command line will prompt the user for values, unless the `--no-prompt` flag is given.

The inputs in a file can be defined under the `.INPUTS` section. A `Type`, `AllowedPattern`, and `Description` can be provided. `Default` can be provided for `String` and `StringList` types.

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

The `Type` is `String` by default. If only the type is to be given, it can be provided inline:

```yaml
.INPUTS:
  Prefix: String
  Value: StringList

$(Prefix)/Name:
  Value: $(Value)
```

## The ssm-ctl tool

### ssm-ctl download

```
ssm-ctl download [--output FILE] PATH [PATH]...
```

Produce a parameter file from the parameters at the given paths, saved to the given file or stdout.

### ssm-ctl push

```
ssm-ctl push [--overwrite] [--delete] [--dry-run] [--input NAME VALUE]... PARAMETER_FILE...
```

Load the given parameter files and push the parameters to SSM.
* `--overwrite` Default to overwriting existing parameters
* `--delete` Flush the paths given in the parameter files before pushing
* `--input NAME VALUE` Set the variable `NAME` to `VALUE`
* `--dry-run` Print out the parameter configuration that would be pushed, but do not push it.
 * Note this may still make KMS calls to decrypt encrypted `SecureString` parameter values.

### ssm-ctl delete

```
ssm-ctl delete [--input NAME VALUE]... PARAMETER_FILE...
```

Load the given parameter files, flush the defined paths, and delete the parameters.

## SecureString parameters

In a `SecureString` parameter, the value can only be stored encrypted, under the `EncryptedValue` field, using the specified `KeyId` (which will also be used for the parameter in SSM). Alternatively, the value can be required to be an input, by putting the name of an input under the `Input` key:

```yaml
.Inputs:
  SecureValue:
    Type: SecureString

/My/Secure/Param:
  Type: SecureString
  Input: SecureValue
```

If the given input is a `String` input, it must be the encrypted value. If it is a `SecureString` input, the user will be prompted for the unencrypted value. Similarly, to specify the encrypted value on the command line, use `--input NAME ENCRYPTED_VALUE`. To prompt the user for the unecrypted value, use `--secure-input NAME`.

`SecureString` input prompts will normally not echo the user input. To change this, use the `--echo` flag.

** The below is not implemented yet **

To encrypt a value for storage, use

```
ssm-ctl encrypt PARAMETER_FILE PATH VALUE [PATH VALUE]...
```
or
```
ssm-ctl encrypt --prompt [--echo] PARAMETER_FILE PATH [PATH]...
```
Use the literal path, including any variable references. This will store the encrypted values back in the parameter file.
To leave the file as-is and simply print out the encrypted values, use the `--print` flag.


