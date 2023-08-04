import os
import sys
import sqlite3
import datetime as dt
from traceback import print_tb
from contextlib import closing

DBFILE = "tagger.db"
_debug = False


def dprint(*args, **kwargs):
    """Debug print wrapper."""
    if _debug:
        colored_debug = "\u001b[38;5;208mDEBUG:\u001b[0m  "
        if "sep" not in kwargs:
            kwargs["sep"] = f"\n{colored_debug}"
        print(f"{colored_debug}" + str(*args[:1]), *args[1:], **kwargs)


def eprint(*args, **kwargs):
    """Error print wrapper."""
    if "end" not in kwargs:
        kwargs["end"] = "\n\n"
    colored_error = "\u001b[31;1mERROR:\u001b[0m  "
    if "sep" not in kwargs:
        kwargs["sep"] = f"\n{colored_error}"
    print(f"\n{colored_error}" + str(*args[:1]), *args[1:], **kwargs)


def error_out(rcode, *args, **kwargs):
    eprint(*args, **kwargs)
    sys.exit(rcode)


def display_usage():  # TODO: Update to conform to new design doc
    """Displays top-level usage doc."""
    print(
        """
Usage:
  tagger <command> [options] [filenames] [tags]

Commands:
  help <cmd>  . Show help for command <cmd> (Cur only this usage doc)
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
      --debug . Run program in debug mode.
  -s  . . . . . If using linux, run db path generation in system mode.
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


def gen_db_path(is_system=False) -> str:
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
        error_out(1, "Cannot initialize database when one already exists.")
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
    mod_time TIMESTAMP,
    size REAL,
    is_dir BOOLEAN
);
CREATE TABLE IF NOT EXISTS tag_files(
    tag_id INTEGER NOT NULL,
    file_id INTEGER NOT NULL,
    PRIMARY KEY(tag_id, file_id),
    FOREIGN KEY (tag_id) REFERENCES tags (tag_id)
        ON DELETE CASCADE ON UPDATE NO ACTION,
    FOREIGN KEY (file_id) REFERENCES files (file_id)
        ON DELETE CASCADE ON UPDATE NO ACTION
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
        print("Database created successfully.")
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
def add_tags_to_files(tags, files: list) -> None:
    """Add the specified tags to the specified files in the database."""

    assert find_db_path(), "Should have caught if there is no db path in `tag()`"

    dprint(f"Adding {tags=} to {files=}...")

    with sqlite3.connect(find_db_path()) as con:
        cur = con.cursor()
        try:
            tag_ids = []
            file_ids = []

            # Insert tags into database:
            for tag in tags:
                dprint(f"Checking if {tag} is already in database...")
                if not cur.execute(
                    "SELECT name FROM tags WHERE name = (?)", (tag,)
                ).fetchone():
                    cur.execute("INSERT INTO tags(name) VALUES (?)", (tag,))
                    dprint(f"{tag} inserted into table tags.")
                    tag_ids.append(cur.lastrowid)
                else:
                    dprint(
                        f"Tag {tag} was already found in database:",
                        "Tags{}".format(
                            cur.execute(
                                "SELECT * FROM tags WHERE name = (?)", (tag,)
                            ).fetchone()
                        ),
                        sep=" ",
                    )
                    tag_ids.append(
                        *cur.execute(
                            "SELECT tag_id FROM tags WHERE name = (?)", (tag,)
                        ).fetchone()
                    )

            # Insert files into database:
            for file in files:
                # Check that the file exists:
                if not os.path.exists(file):
                    print(f"Could not find {file}.")
                    files.remove(file)
                    continue

                file_abspath = os.path.abspath(file)
                file_basename = os.path.basename(file_abspath)
                file_dirname = os.path.dirname(file_abspath)

                dprint(
                    f"{file_abspath = }",
                    f"{file_basename = }",
                    f"{file_dirname = }",
                    sep="\n\t",
                )

                dprint(f"Checking if {file_abspath} is already in database...")
                # TODO Check basename as well as directory
                if not cur.execute(
                    "SELECT name FROM files WHERE name = (?)", (file_basename,)
                ).fetchone():
                    cur.execute(
                        "INSERT INTO files(name, directory, fingerprint, mod_time, size, is_dir) VALUES(?, ?, ?, ?, ?, ?)",
                        (
                            file_basename,
                            file_dirname,
                            "0",  # TODO
                            dt.datetime.now(),
                            os.stat(file_abspath).st_size / (1024**2),
                            os.path.isdir(file_abspath),
                        ),
                    )
                    dprint(f"{file_basename} inserted into table files.")
                    file_ids.append(cur.lastrowid)
                else:
                    dprint(
                        f"File {file_basename} was already found in database:",
                        "Files{}".format(
                            cur.execute(
                                "SELECT * FROM files WHERE name = (?)", (file_basename,)
                            ).fetchone()
                        ),
                        sep=" ",
                    )
                    file_ids.append(
                        *cur.execute(
                            "SELECT file_id FROM files WHERE name = (?)",
                            (file_basename,),
                        ).fetchone()
                    )

            dprint(f"{tag_ids = }, {file_ids = }")

            # Connect files to tags in fileTags table in database:
            for tag_id in tag_ids:
                for file_id in file_ids:
                    cur.execute(
                        "INSERT INTO tag_files(tag_id, file_id) VALUES (?, ?)",
                        (tag_id, file_id),
                    )

        except Exception as err:
            eprint(err, "Traceback:")

            print_tb(err.__traceback__)
            eprint("SQLite syntax incorrect.")


def tag() -> None:
    """Parse the tag(s) and file(s) in argv and add them to the database."""
    if not find_db_path():
        error_out(1, "Cannot add tags to an uninitialized database.")

    # Separates the args after 'tagger tag' ([tags] [--, -f, --files] [files])
    tags = []
    files = []
    in_tags = False
    in_files = False
    for arg in sys.argv:
        if arg == "tag":
            in_tags = True
            continue
        if arg in ["--", "-f", "--files"]:
            in_tags = False
            in_files = True
            continue
        if in_tags:
            tags.append(arg)
        if in_files:
            files.append(arg)

    if not tags:
        error_out(1, "No tags specified.")
    if not files:
        error_out(1, "No files specified.")

    add_tags_to_files(tags, files)


def main():
    global _debug
    use_system_config = False

    # Debug option handling
    if "--debug" in sys.argv:
        sys.argv.remove("--debug")
        _debug = True

    # System mode option handling
    if "-s" in sys.argv:
        sys.argv.remove("-s")
        use_system_config = True

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
        init_database(use_system_config)

    elif sys.argv[1] == "remove-database":
        dprint("Removing tagger database...")
        if db := find_db_path():
            os.remove(db)
            print("Tagger database successfully removed.")
        else:
            error_out(1, "Database was not found.")

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
