from __future__ import absolute_import, print_function

from .config import unittest
from . import config

from . import util

import ssm_ctl

"""
.INPUTS:
  StringInput:
    Type: String
  SecureStringInput:
    Type: SecureString
  EncryptedValueInput:
    Type: String
 
/Test/Secure/Stored:
  EncryptedValue: <value encrypted with config.SSMCTL_TEST_KEY_ID_1>
  KeyId: <config.SSMCTL_TEST_KEY_ID_1>

/Test/Secure/StoredWithSeparateKey:
  EncryptedValue: <value encrypted with config.SSMCTL_TEST_KEY_ID_2>
  KeyId: <config.SSMCTL_TEST_KEY_ID_1>

/Test/Secure/Input/SecureString:
  Type: SecureString
  Input: SecureStringInput
  KeyId: <config.SSMCTL_TEST_KEY_ID_1>

/Test/Secure/Input/String:
  Type: SecureString
  Input: StringInput
  KeyId: <config.SSMCTL_TEST_KEY_ID_1>

/Test/Secure/Input/EV:
  Type: SecureString
  EncryptedValue: $(EncryptedValueInput)
  KeyId: <config.SSMCTL_TEST_KEY_ID_1>

# test download + re-encrypt with same key
# test download + re-encrypt with config.config.SSMCTL_TEST_KEY_ID_2
"""