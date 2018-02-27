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
ssm-ctl deploy [--overwrite] [--delete] ssm.yaml
```

If there are existing parameters, they won't be overwritten (this is a feature of SSM's API).
To overwrite any existing parameters, use the `--overwrite` flag.
To delete any parameters that you have removed, use the `--delete` flag (with care!)

## The SSM parameters file

The parameters file contains parameter names with their associated values and settings, as well
as configurations for deleting parameters in advance of deploying, and for prompting for user input.

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

### Base paths

```yaml
.BASEPATH: /My

Parameter/Name: ... # /My/Parameter/Name
OtherParameter: ... # /My/OtherParameter
/Separate/Path: ... # /Separate/Path
```

If all (or most) of your parameters share a common prefix, you can use `.BASEPATH` to specify that prefix. This path will added to all parameters whose names *do not start with a slash*.

This also enables diff-ing functionality, which also allows you to delete parameters you've removed from the file (see below).

### Variables and inputs

A parameter file can use inputs to become a template. Input references are used like `$(InputName)`.
Input references can be present in the name (including `.BASEPATH`), and the `Value`, `AllowedPattern`, `KeyId`, and `Disable` fields.
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

The inputs `Account` and `Region` are available by default, corresponding to the configured AWS account and region. If the `Account` input is referenced and it is not overridden on the command line, `ssm-ctl` will make a call to STS.GetCallerIdentity to retrieve the account number.

## The ssm-ctl tool

### ssm-ctl download

```
ssm-ctl download [--output FILE] PATH [PATH]...
```

Produce a parameter file from the parameters at the given paths, saved to the given file or stdout.

### ssm-ctl deploy

```
ssm-ctl deploy [--overwrite] [--delete] [--dry-run] [--input NAME VALUE]... [--secure-input NAME]... PARAMETER_FILE...
```

Load the given parameter files and deploy the parameters to SSM.
* `--overwrite` Default to overwriting existing parameters
* `--delete` Delete parameters as found by the diff (see below).
* `--input NAME VALUE` Set the variable `NAME` to `VALUE`
* `--dry-run` Print out the parameter configuration that would be deployed, but do not deploy it.
* `--diff` Print out the diff (see below).
 * Note this may still make KMS calls to decrypt encrypted `SecureString` parameter values.

### ssm-ctl diff

```
ssm-ctl diff [--input NAME VALUE]... [--secure-input NAME]... PARAMETER_FILE...
```

Diff the parameters against the existing parameters in SSM. Any `.BASEPATH`s specified in the files will be searched for existing parameters, allowing parameters not present in the files to be identified as removed. This mechanism is used for the `--delete` flag in `ssm-ctl deploy`. 

### ssm-ctl delete

```
ssm-ctl delete [--input NAME VALUE]... [--secure-input NAME]... PARAMETER_FILE...
```

Load the given parameter files, flush the defined paths, and delete the parameters.

## SecureString parameters

In a `SecureString` parameter, the value can only be stored encrypted, base64 encoded, under the `EncryptedValue` field. Alternatively, the value can be required to be an input, by putting the name of an input under the `Input` key:

```yaml
.Inputs:
  SecureValue:
    Type: SecureString

/My/Secure/Param:
  Type: SecureString
  Input: SecureValue
```

If the given input is a `String` input, it must be an encrypted value. If it is a `SecureString` input, the user will be prompted for the unencrypted value. Similarly, to specify the encrypted value on the command line, use `--input NAME ENCRYPTED_VALUE`. To prompt the user for the unecrypted value, use `--secure-input NAME`. `SecureString` and `--secure-input` prompts will normally not echo the user input. To change this, use the `--echo` flag.

Encrypted values must be encrypted using KMS or the [AWS Encryption SDK](https://docs.aws.amazon.com/encryption-sdk/latest/developer-guide/programming-languages.html). They don't need to use the same key that is specified for the parameter.

To encrypt a value to put in a parameter file, you can use the [AWS Encryption SDK CLI tool](https://docs.aws.amazon.com/encryption-sdk/latest/developer-guide/crypto-cli-how-to.html#crypto-cli-e-d-intro) and put the base64-encoded value into your parameter file, or you can use the `ssm-ctl encrypt` utility:

```
ssm-ctl encrypt PARAMETER_FILE KEY_ID NAME PLAINTEXT_VALUE [NAME PLAINTEXT_VALUE]...
```
or
```
ssm-ctl encrypt --prompt [--echo] PARAMETER_FILE KEY_ID NAME [NAME]...
```
If the parameter file already exists, use the literal paths, including any variable references. This will store the encrypted values back in the parameter file.

The key id can be provided as an ARN or as `key/{key-id}` or `alias/{alias-name}`, which will use the current account and region from boto3.

To decrypt the values in a parameter file and print them to stdout, use

```
ssm-ctl decrypt PARAMETER_FILE
```

### Permissions

For `ssm-ctl deploy`, you need `kms:Encrypt` permission for the `KeyId`s you have specified. For any encrypted value in the parameter file or input on the command line, you must have `kms:Decrypt` permissions for the associated key.

For `ssm-ctl download`, you currently need both `kms:Decrypt` and `kms:Encrypt` permission for the keys associated with the parameters you are accessing. This is because the encrypted format returned by SSM is not in AWS Encryption SDK format, so `ssm-ctl` converts it to plaintext and reencrypts it.

For `ssm-ctl encrypt` and `ssm-ctl decrypt`, you must have the relevant `kms:Encrypt` or `kms:Decrypt` permissions for the keys involved.
