import os
import sys
import sqlite3
from traceback import print_tb
from contextlib import closing

DBFILE = "tagger.db"
_debug = False


def dprint(*args, **kwargs):
    """Debug print wrapper."""
    if _debug:
        colored_debug: str = "\u001b[38;5;208mDEBUG:\u001b[0m  "
        if "sep" not in kwargs:
            kwargs["sep"] = f"\n{colored_debug}"
        print(f"{colored_debug}" + str(*args[:1]), *args[1:], **kwargs)


def eprint(*args, **kwargs):
    """Error print wrapper."""
    if "end" not in kwargs:
        kwargs["end"] = "\n\n"
    colored_error: str = "\u001b[31;1mERROR:\u001b[0m  "
    if "sep" not in kwargs:
        kwargs["sep"] = f"\n{colored_error}"
    print(f"\n{colored_error}" + str(*args[:1]), *args[1:], **kwargs)


def display_usage():  # TODO: Update to conform to new design doc
    """Displays top-level usage doc."""
    print(
        """
Usage:
  tagger {command} [options] [filenames] [tags]

Commands:
  help {cmd}  . Show help for command <cmd> (Cur only this usage doc)
  init  . . . . Initialize tagger database at default location
  tag . . . . . Attach one or multiple tags to the specified file(s).
                  'tagger tag {tag1} [{tag2} ...] [-f | --files | --]
                    {file1} [{dir1} ...]'
                  ex. 'tagger tag sparrow.png bird trees sky png'
  list-tags . . List the tags of the specifed file(s).
                  'tagger list-tags {file1} [{dir1} ...]'
                  ex. 'tagger list-tags sparrow.png'
  list-files  . List the files tagged with the specified tag(s).
                Logical operators can be used - and:'&&', or:'||', not:'!'.
                Default operator for multiple tags is ||.
                  'tagger list-files {tag1} [<operators>] [{tag2} ...]'
                  ex. 'tagger list-files bird sky' -> (bird || sky)
                  ex. 'tagger list-files bird && sky'
                  ex. 'tagger list-files (bird || sky) && !trees'

Features planned to be added later:
  replace-tag . Delete first specified tag and replace with second
                specified tag.
                  'tagger raplace-tag {delete-tag} {create-tag}'
                  ex. 'tagger replace-tag brid bird'

General Options:
  -h, --help  . Display this usage menu.
        """
    )


def find_db_path() -> str | None:
    """Checks whether a database file exists and returns it if it does."""

    # dprint("Finding database path...")

    # Check windows user directory
    if sys.platform == "win32":
        file_path = os.path.expandvars("%LOCALAPPDATA%\\" + DBFILE)
        if os.path.exists(file_path):
            # dprint(f"File found: {file_path=}")
            return file_path

    # Check linux user config and system-wide directory
    if sys.platform.startswith("linux"):
        file_path = os.path.expandvars("$HOME/.config/" + DBFILE)
        if os.path.exists(file_path):
            # dprint(f"File found: {file_path=}")
            return file_path
        file_path = "/etc/" + DBFILE
        if os.path.exists(file_path):
            # dprint(f"File found: {file_path=}")
            return file_path

    # Didn't find it
    return None


def gen_db_path(is_system: bool = False) -> str:
    """Gets the path to the .db file."""
    dprint(f"Generating db file path...")

    file_path = None

    # Check windows user directory
    if sys.platform == "win32":
        file_path = os.path.expandvars("%LOCALAPPDATA%\\" + DBFILE)

    # Check linux user config and system-wide directory
    if sys.platform.startswith("linux"):
        if is_system:
            file_path = "/etc/" + DBFILE
        else:
            file_path = os.path.expandvars("$HOME/.config/" + DBFILE)
    dprint(f"{file_path=}")
    return file_path


def init_database(is_system=False) -> None:
    """Initialize the tagger.db database if one doesn't already exist on
    current device.
    """
    dprint("Verifying db does not already exist...")
    if find_db_path():
        eprint("Cannot initialize database when one already exists.")
        sys.exit(1)
    path = gen_db_path(is_system)
    had_error = False

    with closing(sqlite3.connect(path)) as con:
        cur = con.cursor()
        try:
            cur.executescript(
                """
BEGIN TRANSACTION;
CREATE TABLE IF NOT EXISTS tags(
    tag_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS files(
    file_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    directory TEXT NOT NULL,
    fingerprint TEXT,
    mod_time DATETIME,
    size INTEGER,
    is_dir BOOLEAN
);
CREATE TABLE IF NOT EXISTS fileTag(
    file_id INTEGER,
    tag_id INTEGER,
    PRIMARY KEY(file_id, tag_id)
);
COMMIT;
                """
            )
        except Exception as err:
            eprint(err, "Traceback:")
            print_tb(err.__traceback__)
            eprint("Faulty database initialized.")
            had_error = True

    if not had_error:
        print("Database created successfully")
        sys.exit(0)
    else:
        try:
            dprint(f"Removing {path=}...")  # TODO
            os.remove(path)
            print("Removed faulty database.")
        except Exception as err:
            eprint(err, "Traceback:")
            print_tb(err.__traceback__)
            eprint("Faulty database not removed.")
        sys.exit(1)


# TODO Milestone 2
def add_tag_to_file(tag: str, file: str) -> None:
    dprint(f"Adding {tag=} to {file=}...")
    with sqlite3.connect(find_db_path()) as con:
        cur = con.cursor()
        try:
            # Insert tag into database:
            dprint("Checking if tag is already in database...")
            if not cur.execute(
                "SELECT name FROM tags WHERE name = (?)", (tag,)
            ).fetchone():
                cur.execute("INSERT INTO tags(name) VALUES(?)", (tag,))
                dprint(f"{tag} inserted into table tags.")
            else:
                dprint(
                    "Tag was already found in database:",
                    "Tags{}".format(
                        cur.execute(
                            "SELECT * FROM tags WHERE name = (?)", (tag,)
                        ).fetchone()
                    ),
                    sep=" ",
                )
            # Insert file into database:
            dprint()

        except Exception as err:
            eprint(err, "Traceback:")
            print_tb(err.__traceback__)
            eprint("SQLite syntax incorrect.")


# TODO Milestone 5
def add_tags_to_file(tags: list[str], file: str) -> None:
    ...


# TODO Milestone 6
def add_tag_to_files(tag: str, files: list[str]) -> None:
    ...


# TODO Milestone 7
def add_tags_to_files(tags: list[str], files: list[str]) -> None:
    ...


def tag() -> None:
    """Parse the tag(s) and file(s) in argv and call
    the appropriate function.
    """
    if not find_db_path():
        eprint("Cannot add tags to an uninitialized database.")
        sys.exit(1)

    arg_str = ""
    for arg in sys.argv:
        if "tag" not in arg:
            arg_str += arg + " "
    arg_str = arg_str.strip()
    # dprint(f"{arg_str=}")

    tags_str = ""
    files_str = ""
    if " -f " in arg_str:
        tags_str, files_str = arg_str.split(" -f ")
        dprint(f"{tags_str=}, sep='-f', {files_str=}")
    elif " --files " in arg_str:
        tags_str, files_str = arg_str.split(" --files ")
        dprint(f"{tags_str=}, sep='--files', {files_str=}")
    elif " -- " in arg_str:
        tags_str, files_str = arg_str.split(" -- ")
        dprint(f"{tags_str=}, sep='--', {files_str=}")

    tags = [tag for tag in tags_str.split()]
    files = [file for file in files_str.split()]
    dprint(f"{tags=}, {files=}")

    if len(tags) == 1 and len(files) == 1:
        add_tag_to_file(tags[0], files[0])
    elif len(tags) > 1 and len(files) == 1:
        add_tags_to_file(tags, files[0])
    elif len(tags) == 1 and len(files) > 1:
        add_tag_to_files(tags[0], files)
    else:
        add_tags_to_files(tags, files)


def main():
    global _debug
    use_system_config = False

    # Debug option handling
    if "--debug" in sys.argv:
        sys.argv.remove("--debug")
        _debug = True

    # Help option handling
    if (
        "-h" in sys.argv
        or "--help" in sys.argv
        or len(sys.argv) == 1
        or "help" in sys.argv
    ):
        if "-h" in sys.argv:
            dprint(f"Printing usage because {'-h' in sys.argv=}...")
            sys.argv.remove("-h")
        if "--help" in sys.argv:
            dprint(f"Printing usage because {'--help' in sys.argv=}...")
            sys.argv.remove("--help")
        if len(sys.argv) == 1:
            dprint(f"Printing usage because {(len(sys.argv) == 1)=}...")
        if "help" in sys.argv:
            dprint(f"Printing usage because {'help' in sys.argv=}...")
        display_usage()
        sys.exit(0)

    # Command handling
    if sys.argv[1] == "init":
        dprint("Initiating tagger database...")
        if "-s" in sys.argv:
            use_system_config = True
        init_database(use_system_config)

    elif sys.argv[1] == "tag":
        dprint("Adding tags to files...")
        tag()

    elif sys.argv[1] == "list-tags":
        ...
    elif sys.argv[1] == "list-files":
        ...
    elif sys.argv[1] == "replace-tag":
        ...
    else:
        dprint(f"Printing usage because invalid command syntax...")
        display_usage()

    sys.exit(0)


if __name__ == "__main__":
    main()
