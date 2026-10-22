"""python -m crystalsight {fetch|taskgen|run|score|report|e2e} ..."""

import subprocess
import sys

CMDS = {"taskgen": "crystalsight.taskgen", "run": "crystalsight.runner", "score": "crystalsight.score",
        "report": "crystalsight.report", "smoke": "crystalsight.smoke", "prepare": "crystalsight.prepare"}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        print("usage: python -m crystalsight {" + "|".join(CMDS) + "} [args]")
        sys.exit(2)
    sys.exit(subprocess.call([sys.executable, "-m", CMDS[sys.argv[1]], *sys.argv[2:]]))


if __name__ == "__main__":
    main()