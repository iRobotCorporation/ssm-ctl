from __future__ import absolute_import, print_function

from .config import unittest
from . import config

from . import util

import ssm_ctl
from ssm_ctl.files import load_parameters

"""
.INPUTS:
  StringInput:
    Type: String
  StringInputWithPattern:
    Type: String
    Pattern: ^value$
  StringListInput:
    Type: StringList
  StringInputWithDescription:
    Type: String
    Description: The description
  SecureStringInput:
    Type: SecureString
  StringInputWithInlineType: String

.BASEPATH: /Test

StringParam/ReferenceValue:
  Type: String
  Value: $(StringInput)

StringParam/WithoutType:
  Value: string_value

StringListParam/AsString:
  Type: StringList
  Value: value_1,value_2

DisabledParam:
  Type: InvalidType
  Disable: True

Param/WithDescription:
  Value: string_value
  Description: The description

Param/WithPattern:
  Value: string_value
  AllowedPattern: ^\w+$

Param/WithPattern/Invalid:
  Disable: True
  Value: string_value
  AllowedPattern: 0+

Secure/Input/SecureString:
  Type: SecureString
  Input: $(SecureStringInput)
  KeyId: arn:aws:kms:$(Region):$(Account):alias/test

Secure/Input/SecureString/BareReference:
  Type: SecureString
  Input: SecureStringInput
  KeyId: arn:aws:kms:$(Region):$(Account):alias/test

Secure/Input/String:
  Disable: True
  Type: SecureString
  Input: $(StringInput)
  KeyId: arn:aws:kms:$(Region):$(Account):alias/test

/Outside/BasePath:
  Type: String
  Value: string_value
"""

class TestLoading(unittest.TestCase):
    def setUp(self):
        pass
    
    def tearDown(self):
        pass
    
    def test_load_string(self):
        obj = util.load("""
        /Test/StringParam:
            Type: String
            Value: string_value
        """)
        
        names, parameters, base_paths = load_parameters({'ssm.yaml': obj})
        
        self.assertIn('/Test/StringParam', names)
        self.assertEqual(len(parameters), 1)
        self.assertEqual(len(base_paths), 0)
    
    def test_load_stringlist(self):
        obj = util.load("""
        /Test/StringListParam:
            Type: StringList
            Value:
            - value1
            - value2
        """)
        
        names, parameters, base_paths = load_parameters({'ssm.yaml': obj})
        param = parameters['/Test/StringListParam']
        
        self.assertEqual(param._value, ['value1', 'value2'])
        self.assertEqual(param.get_value(), 'value1,value2')
    
    def test_load_inline(self):
        obj = util.load("""
        /Test/StringParam/Inline: string_value
        
        /Test/StringListParam/Inline:
        - value_1
        - value_2
        """)
        
        names, parameters, base_paths = load_parameters({'ssm.yaml': obj})
        
        string_param = parameters['/Test/StringParam/Inline']
        self.assertEqual(string_param.type, 'String')
        
        stringlist_param = parameters['/Test/StringListParam/Inline']
        self.assertEqual(stringlist_param.type, 'StringList')

if __name__ == '__main__':
    unittest.main()