from __future__ import absolute_import, print_function

import sys
import six
import os

if sys.version_info[:2] == (2, 6):
    import unittest2 as unittest
else:
    import unittest

TEST_KEY_ID_1 = os.environ.get('SSMCTL_TEST_KEY_ID_1')
TEST_KEY_ID_2 = os.environ.get('SSMCTL_TEST_KEY_ID_2')

if TEST_KEY_ID_1:
    import aws_encryption_sdk
    import boto3
    TEST_ENCRYPTION = True
else:
    TEST_ENCRYPTION = False

if TEST_ENCRYPTION and TEST_KEY_ID_2:
    TEST_ENCRYPTION_WITH_SEPARATE_KEY = True
    TEST_REENCRYPT = True
else:
    TEST_ENCRYPTION_WITH_SEPARATE_KEY = False
    TEST_REENCRYPT = False

