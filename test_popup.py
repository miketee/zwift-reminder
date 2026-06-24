import subprocess, sys 
from pathlib import Path 
popup_script = Path('src/popup.py').resolve() 
p = subprocess.Popen([sys.executable, str(popup_script)], cwd=str(popup_script.parent)) 
print('PID:', p.pid) 
