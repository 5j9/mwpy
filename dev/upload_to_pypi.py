from subprocess import check_call

from path import Path


root = Path(__file__).parent.parent
(root / 'dist').rmtree_p()
root.cd()

check_call(('python', 'setup.py', 'sdist', 'bdist_wheel'))
check_call(('twine', 'upload', 'dist/*'))
