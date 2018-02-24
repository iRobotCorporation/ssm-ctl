from setuptools import setup

def get_version(name):
    import os.path
    path = os.path.join(name, '_version')
    if not os.path.exists(path):
        return "0.0.0"
    with open(path) as f:
        return f.read().strip()

setup(
    name='ssm-ctl',
    version=get_version('ssm_ctl'),
    description='Manage your AWS SSM parameters',
    packages=["ssm_ctl"],
    package_data={
        "ssm_ctl": ["_version"]
    },
    entry_points={
        'console_scripts': [
            'ssm-ctl = ssm_ctl.cli:main'
        ],
    },
    install_requires=[
        'pyyaml'
    ],
    author='Ben Kehoe',
    author_email='bkehoe@irobot.com',
    project_urls={
        "Source code": "https://github.com/iRobotCorporation/ssm-ctl",
    },
    license='Apache Software License 2.0',
    classifiers=(
        'Development Status :: 2 - Beta',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'License :: OSI Approved :: Apache Software License',
    ),
    keywords='aws ssm',
)