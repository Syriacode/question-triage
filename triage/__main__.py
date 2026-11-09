import sys

from triage.cli import main

sys.exit(main(sys.argv[1:], sys.stdout, sys.stderr))
