# run coverage and open the html result
from subprocess import run
from webbrowser import open_new_tab

from path import Path

root = Path(__file__).parent.parent
root.cd()
run(('coverage', 'run', 'tests/test.py'))
run(('coverage', 'html'))
index = root / "htmlcov/index.html"
open_new_tab(f'file://{index}')
