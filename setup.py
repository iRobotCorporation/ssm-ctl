from setuptools import setup

setup(
    name='ssm-ctl',
    version='0.1.0',
    description='Manage your AWS SSM parameters',
    packages=["ssm_ctl"],
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
        'License :: OSI Approved :: Apache Software License',
    ),
    keywords='aws ssm',
)