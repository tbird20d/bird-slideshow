import os
import sys
import sqlite3


def display_usage():
    print(
"""
Usage:
  tagging <command> [options] [filenames] [tags]

Commands:
  tag                       Add one or multiple tags to the specified file(s).
                              ex. 'tagging tag sparrow.png bird trees sky png'
  tags                      List the tags of the specifed file(s).
                              ex. 'tagging tags sparrow.png'
  merge                     Delete first specified tag and merge into second specified tag.
                              ex. 'tagging merge brid bird'
  files                     List the files tagged with the specified tag(s).
                              ex. 'tagging files bird sky'
                              ex. 'tagging files bird and sky'
                              ex. 'tagging files (bird or sky) and not trees'

General Options:
  -h, --help                Display this help menu.
  --tags="[tags]"           Used when tagging multiple files with the same tag(s).
                              ex. 'tagging tag --tags="no-transparency jpg" *.jpg'
"""
    )


def main():
    try:
        if "-h" in sys.argv or "--help" in sys.argv:
            display_usage()
        elif sys.argv[1] == "tag":
            ...
        elif sys.argv[1] == "tags":
            ...
        elif sys.argv[1] == "merge":
            ...
        elif sys.argv[1] == "files":
            ...
    except:
        display_usage()


if __name__ == "__main__":
    main()