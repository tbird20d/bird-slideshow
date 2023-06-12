import os
import sys
import sqlite3


DBFILE = "tagger.db"
_debug = False


def dprint(*args, **kwargs):
    """Debug print wrapper."""
    if _debug:
        colored_debug: str = "\u001b[38;5;208mDEBUG:\u001b[0m"
        if "sep" not in kwargs:
            kwargs["sep"] = f"\n{colored_debug}  "
        print(f"{colored_debug}  " + str(*args[:1]), *args[1:], **kwargs)


def eprint(*args, **kwargs):
    """Error print wrapper."""
    if "end" not in kwargs:
        kwargs["end"] = "\n\n"
    print("\n\u001b[31;1mERROR:\u001b[0m", *args, **kwargs)


def find_db_path():
    """Checks whether a database file exists."""
    dprint("Verifying db does not already exist...")

    # Check windows user directory
    if sys.platform == "win32":
        file_path = os.path.expandvars("%LOCALAPPDATA%\\" + DBFILE)
        if os.path.exists(file_path):
            dprint(f"File found: {file_path=}")
            return file_path

    # Check linux user config and system-wide directory
    if sys.platform.startswith("linux"):
        file_path = os.path.expandvars("$HOME/.config/" + DBFILE)
        if os.path.exists(file_path):
            dprint(f"File found: {file_path=}")
            return file_path
        file_path = "/etc/" + DBFILE
        if os.path.exists(file_path):
            dprint(f"File found: {file_path=}")
            return file_path

    # Didn't find it
    return None


def gen_db_path(is_system: bool = False):
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


def init_database(is_system=False):
    if find_db_path():
        eprint("Cannot initialize database when one already exists.")
        sys.exit(1)
    path = gen_db_path(is_system)
    had_error = False

    con = sqlite3.connect(path)
    cur = con.cursor()
    try:
        cur.executescript(
            "BEGIN TRANSACTION;\n"
            "CREATE TABLE IF NOT EXISTS tags(\n"
            "    tag_id INTEGER,\n"
            "    name TEXT,\n"
            "    PRIMARY KEY(tag_id)\n"
            ");\n"
            "CREATE TABLE IF NOT EXISTS files(\n"
            "    file_id INTEGER,\n"
            "    name TEXT,\n"
            "    directory TEXT,\n"
            "    fingerprint TEXT\n"
            "    mod_time DATETIME\n"
            "    size INTEGER\n"
            "    is_dir BOOLEAN,\n"
            "    PRIMARY KEY(file_id)\n"
            ");\n"
            "CREATE TABLE IF NOT EXISTS fileTag(\n"
            "    file_id INTEGER,\n"
            "    tag_id INTEGER,\n"
            "    PRIMARY KEY(file_id, tag_id)\n"
            ");\n"
            "COMMIT;\n"
        )
        cur.close()
        con.close()
    except Exception as exc:
        eprint(exc)
        had_error = True
    if not had_error:
        print("Database created successfully")
    else:
        try:
            dprint(f"Trying to remove {path=}")  # TODO
            os.remove(path)
        except Exception as exc:
            eprint(exc, "Database not removed")


def display_usage():  # TODO: Update to conform to new design doc
    """Displays top-level usage doc."""
    print(
        "Usage:\n"
        "  tagger <command> [options] [filenames] [tags]\n"
        "\n"
        "Commands:\n"
        "  help <cmd> Show help for command <cmd>\n"
        "  init       Initialize tagger database at default location\n"
        "  tag ...    Add one or multiple tags to the specified file(s).\n"
        "               ex. 'tagger tag sparrow.png bird trees sky png'\n"
        "  list-tags  List the tags of the specifed file(s).\n"
        "               ex. 'tagger list-tags sparrow.png'\n"
        "  list-files List the files tagged with the specified tag(s).\n"
        "               ex. 'tagger list-files bird sky'\n"
        "               ex. 'tagger list-files bird and sky'\n"
        "               ex. 'tagger list-files (bird or sky) and not trees'\n"
        "\n"
        "Features planned to be added later:\n"
        "  replace-tag  Delete first specified tag and replace with second specified tag.\n"
        "               ex. 'tagger merge brid bird'\n"
        "\n"
        "General Options:\n"
        "  -h, --help      Display this usage menu.\n"
        "\n"
    )


def main():
    global _debug
    use_system_config = False

    if "--debug" in sys.argv:
        sys.argv.remove("--debug")
        _debug = True

    if (
        "-h" in sys.argv
        or "--help" in sys.argv
        or "help" in sys.argv
        or len(sys.argv) == 1
    ):
        dprint(
            f"{'-h' in sys.argv=}",
            f"{'--help' in sys.argv=}",
            f"{'help' in sys.argv=}",
            f"{len(sys.argv) == 1=}",
        )
        display_usage()
        sys.exit(0)

    if sys.argv[1] == "init":
        dprint("Initiating tagger database...")
        if "-s" in sys.argv:
            use_system_config = True
        init_database(use_system_config)
    elif sys.argv[1] == "tag":
        ...
    elif sys.argv[1] == "tags":
        ...
    elif sys.argv[1] == "merge":
        ...
    elif sys.argv[1] == "files":
        ...
    else:
        display_usage()

    sys.exit(0)


if __name__ == "__main__":
    main()
