from os import getcwd
from unittest import defaultTestLoader, TextTestResult, TextTestRunner
from warnings import resetwarnings, simplefilter


resetwarnings()
simplefilter('error')
print(getcwd())
test_suite = defaultTestLoader.discover(
    '.' if getcwd().endswith('test') else 'test')
raise SystemExit(not TextTestRunner(
    resultclass=TextTestResult, verbosity=1).run(test_suite).wasSuccessful())
