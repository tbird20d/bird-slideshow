#! /usr/bin/python3

import os
import sys
import sqlite3
import hashlib
import datetime as dt
import traceback
import contextlib
import PIL.Image
import PIL.ExifTags

import geopy.geocoders as geocoders

DB_DIR = None
DBFILE = "tagger.db"
_debug = False
MONTHS = {
    "01": "january",
    "02": "february",
    "03": "march",
    "04": "april",
    "05": "may",
    "06": "june",
    "07": "july",
    "08": "august",
    "09": "september",
    "10": "october",
    "11": "november",
    "12": "december",
}


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
    print(f"Usage: {sys.argv[0]} <command> [options]")
    print(f"tagger --help for more information.")
    sys.exit(rcode)


def display_usage():  # TODO: Update to conform to new design doc
    """Displays top-level usage doc."""
    print(
        r"""Usage:
  tagger <command> [options]

Commands:
  help <cmd>    Show help for command <cmd> (Cur only this usage doc)
  init          Initialize tagger database at default location
                  Syntax:
                    tagger init
  tag           Attach one or multiple tags to the specified file(s).
                  Syntax:
                    tagger tag {tag1} [{tag2} ...] [-f | --files | --]
                      {file1} [{dir1} ...]
                  Examples:
                    tagger tag bird trees sky png -- sparrow.png
  list-tags     List all the tags in the database, or of the specifed
                  file(s). Option -u lists all tags that are unassociated
                  with any file.
                  Syntax:
                    tagger list-tags [{file1} ...]
                  Examples:
                    tagger list-tags sparrow.png
                    tagger list-tags -u
  list-files    List the files tagged with the specified tag(s).
                  Logical operators can be used - and, or, not.
                  Default operator for multiple tags is or.
                  Order of operations from left to right. (?)
                  Syntax:
                    tagger list-files [{tag1} [<operators>] {tag2} ...]
                  Examples:
                    tagger list-files
                    tagger list-files bird sky (-> bird or sky)
                    tagger list-files bird and sky  # TODO
                    tagger list-files bird or sky and not japan  # TODO
  auto-tag      Tags specified files according to automatically deduced image
                  metadata (exif).
                  Syntax:
                    tagger auto-tag --dry-run {type} -- {file1} [{file2} ...]
                  `type`:
                    One of 'exif-date', 'exif-loc', 'exif'
                  Examples:
                    tagger auto-tag exif-loc -- europe2023.jpg


Features planned to be added later:
  replace-tag   Delete first specified tag and replace with second
                  specified tag. Reassigns the new tag to all files
                  previously associated with the old tag.
                  Syntax:
                    'tagger raplace-tag {delete-tag} {create-tag}'
                  Example:
                    'tagger replace-tag brid bird'

General Options:
  -h, --help    Display this usage menu.
      --debug   Run program in debug mode.
  --global      With <init>: If using linux, generate db in /etc/
                  (i.e. system-wide).
  -u            With <list-tags>: Lists unused tags stored in the database."""
    )


def find_db_path() -> str | None:
    """Checks whether a database file exists and returns it if it does."""
    global DB_DIR

    if DB_DIR:
        db_path = DB_DIR + "/" + DBFILE
        if os.path.exists(db_path):
            return db_path
        else:
            return None

    # dprint("Finding database path...")

    # Check windows user directory
    if sys.platform == "win32":
        file_path = os.path.expandvars("%LOCALAPPDATA%\\tagger\\" + DBFILE)
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
        file_path = os.path.expandvars("%LOCALAPPDATA%\\tagger\\" + DBFILE)

    # Check linux user config and system-wide directory
    if sys.platform.startswith("linux"):
        if is_system:
            file_path = "/etc/" + DBFILE
        else:
            file_path = os.path.expandvars("$HOME/.config/" + DBFILE)
    dprint(f"{file_path=}")
    return file_path


def init_database(is_system=False, db_path=None) -> None:
    """Initialize the tagger.db database if one doesn't already exist on
    current device.
    """
    dprint("Verifying db does not already exist...")
    if db_path:
        error_out(1, "Cannot initialize database when one already exists.")
    path = gen_db_path(is_system)
    dprint(f"DB path is {path}")
    had_error = False

    with contextlib.closing(sqlite3.connect(path)) as con:
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
    size INTEGER,
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
            traceback.print_tb(err.__traceback__)
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
            traceback.print_tb(err.__traceback__)
            eprint("Faulty database not removed.")
        sys.exit(1)


def get_fingerprint(file):
    """Gets the fingerprint for the passed file.

    Fingerprint is the sha1 hash of bytes from beginning, end, and middle of file.
    """

    h = hashlib.sha1()
    f = open(file, "rb")
    h.update(f.read(64000))
    pos = f.seek(-64000, 2)
    h.update(f.read(64000))
    f.seek(pos // 2, 0)
    h.update(f.read(64000))
    f.close()
    return h.hexdigest()


def add_tags_to_files(db_path: str, tags: list, files: list):
    """Add the specified tags to the specified files in the database."""

    assert db_path, "Should have caught if there is no db path in `tag()`"

    dprint(f"Adding {tags=} to {files=}...")

    with sqlite3.connect(db_path) as con:
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
                if not cur.execute(
                    "SELECT name FROM files WHERE name = (?) AND directory = (?)",
                    (file_basename, file_dirname),
                ).fetchone():
                    cur.execute(
                        "INSERT INTO files(name, directory, fingerprint, mod_time, size, is_dir) VALUES(?, ?, ?, ?, ?, ?)",
                        (
                            file_basename,
                            file_dirname,
                            get_fingerprint(file_abspath),
                            dt.datetime.now(),
                            os.stat(file_abspath).st_size,
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
            if "UNIQUE constraint failed" in str(err):
                print(f"File {file_basename} already has one of {tags}.")
                # TODO: More descriptive error message.
                return
            
            eprint(err, "Traceback:")

            traceback.print_tb(err.__traceback__)
            eprint("SQLite syntax may be incorrect.")


def tag(db_path: str | None) -> None:
    """Parse the tag(s) and file(s) in argv and add them to the database."""
    if not db_path:
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

    add_tags_to_files(db_path, tags, files)


def list_tags(db_path: str):
    u_option = False

    if "-u" in sys.argv:
        u_option = True
        sys.argv.remove("-u")

    if not u_option:
        files = []
        in_files = False
        for arg in sys.argv:
            if arg == "list-tags":
                in_files = True
                continue
            if in_files:
                files.append(arg)

        dprint(f"{files = }")

    with sqlite3.connect(db_path) as con:
        cur = con.cursor()
        try:
            # List all unused tags in the database
            if u_option:
                cur.execute(
                    "SELECT name FROM tags WHERE tag_id NOT IN (SELECT tag_id FROM tag_files);"
                )
                tags = [tag for (tag,) in cur.fetchall()]
                for tag in tags:
                    print(tag)
                return

            # List all tags in the database
            if not files:
                cur.execute("SELECT name FROM tags;")
                tags = [tag for (tag,) in cur.fetchall()]
                for tag in tags:
                    print(tag)
                return

            tags = dict()
            for file in files:
                fpath = os.path.abspath(file)
                fname = os.path.basename(fpath)
                fdir = os.path.dirname(fpath)

                tags[fname] = []

                cur.execute(
                    """
SELECT DISTINCT t.name
FROM tags t
  JOIN tag_files tf
    ON t.tag_id = tf.tag_id
  JOIN files f
    ON tf.file_id = f.file_id
WHERE f.name = (?) AND f.directory = (?)
ORDER BY f.name;
                    """,
                    (str(fname), str(fdir)),
                )
                found_tags = [tag for (tag,) in cur.fetchall()]
                dprint(f"{found_tags = }")
                for found_tag in found_tags:
                    tags[fname].append(found_tag)

            for fname, tags in tags.items():
                print(f"{fname}: {tags}")

        except Exception as err:
            eprint(err, "Traceback:")

            traceback.print_tb(err.__traceback__)
            eprint("SQLite syntax incorrect.")


def list_files(db_path: str):
    tags = []
    in_tags = False
    for arg in sys.argv:
        if arg == "list-files":
            in_tags = True
            continue
        if in_tags:
            tags.append(arg)

    dprint(f"{tags = }")

    with sqlite3.connect(db_path) as con:
        cur = con.cursor()
        try:
            # List all the files in the database
            if not tags:
                cur.execute("SELECT directory, name FROM files;")
                dir_files = cur.fetchall()  # Formatted [(dir, file), (dir, file), ...]
                paths = [dir + os.sep + fname for dir, fname in dir_files]
                for file in paths:
                    print(file)
                return

            files = []
            for tag in tags:
                cur.execute(
                    """
SELECT DISTINCT f.directory, f.name
FROM files f
    JOIN tag_files tf
        ON f.file_id = tf.file_id
    JOIN tags t
        ON tf.tag_id = t.tag_id
WHERE t.name = (?)
ORDER BY f.name;
                    """,
                    (str(tag),),
                )
                dir_files = cur.fetchall()  # Formatted [(dir, file), (dir, file), ...]
                paths = [dir + os.sep + fname for dir, fname in dir_files]
                dprint(f"{paths = }")
                for path in paths:
                    if path not in files:
                        files.append(path)

            dprint(f"Files associated with tag(s) {tags}:")
            for file in files:
                print(file)

        except Exception as err:
            eprint(err, "Traceback:")

            traceback.print_tb(err.__traceback__)
            eprint("SQLite syntax incorrect.")


def get_date_from_exif(file):
    """Reads exif data and returns datetime."""
    try:
        PIL_image = PIL.Image.open(os.path.abspath(file))
        datetime = PIL_image.getexif()[0x0132]  # 'DateTime'
        dprint(f"Exif DateTime: {datetime}")
        return datetime
    except Exception as err:
        # dprint(traceback.print_tb(err.__traceback__))
        return None


def tag_exif_date(db_path: str, files: list, dry_run: bool = False):
    """Automatically reads date data for each file and tags year and month."""
    for file in files:
        date_str: str = get_date_from_exif(file)

        if not date_str:
            dprint(f"No date found for {file}.")
            continue

        # Parses the month and year from datetime str
        date_year, date_month, _ = date_str.split(":", 2)
        dprint(f"{date_year = }, {date_month = }")

        month = MONTHS[date_month]
        tags = [date_year, month]
        if not dry_run:
            add_tags_to_files(db_path, tags, [file])
        else:
            print(f"Would have [DATE] tagged {file} with {tags}.")


def get_gps_from_exif(file):
    """Reads exif data and returns gps dict if exists, otherwise return None."""
    try:
        PIL_image = PIL.Image.open(os.path.abspath(file))
        gps_dict = PIL_image.getexif().get_ifd(0x8825)  # 'GPSInfo'
        dprint(f"Exif GPSInfo: {gps_dict}")
        return gps_dict if gps_dict else None
    except Exception as err:
        # dprint(traceback.print_tb(err.__traceback__))
        return None


def convert_dms_to_degrees(lat_ref, lat: tuple, lng_ref, lng: tuple):
    """Convert GPS data from Degree Minutes Seconds to Decimal Degrees."""
    lat_deg = lat[0] + lat[1] / 60 + lat[2] / 3600
    lng_deg = lng[0] + lng[1] / 60 + lng[2] / 3600
    if lat_ref == "S":
        lat_deg = -lat_deg
    if lng_ref == "W":
        lng_deg = -lng_deg
    return lat_deg, lng_deg


def tag_exif_loc(db_path: str, files: list, dry_run: bool = False):
    """Automatically reads gps data for each file and tags the country."""  # TODO
    for file in files:
        gps_data = get_gps_from_exif(file)

        if not gps_data:
            dprint(f"No gps data found for {file}.")
            continue

        lat, lng = convert_dms_to_degrees(
            gps_data[1], gps_data[2], gps_data[3], gps_data[4]
        )  # 1: Lat Ref 2: Lat 3: Lng Ref 4: Lng

        dprint(f"{lat = }, {lng = }")

        locator = geocoders.Nominatim(user_agent="taggercli")
        loc = locator.reverse((lat, lng), zoom=11, language="en-US")

        dprint(f"{loc = }")

        data: dict = loc.raw
        
        dprint(f"{data = }")

        address: dict = data.get("address", {})

        if not address:
            eprint(f"No address found for {file}.")
            continue

        leisure: str = address.get("leisure", "")
        city: str = address.get("city", "")
        state: str = address.get("state", "")
        country: str = address.get("country", "")
        country_code: str = address.get("country_code", "")

        fields = [leisure, city, state, country, country_code]
        tags = []

        for field in fields:
            if field:
                tags.append(field)

        dprint(f"{tags = }")

        if not dry_run:
            add_tags_to_files(db_path, tags, [file])
        else:
            print(f"Would have [LOCATION] tagged {file} with {tags}.")


def auto_tag(db_path: str):
    """Tag specified files using the spcified type of exif data."""

    dry_run = False

    if "--dry-run" in sys.argv:
        dry_run = True
        sys.argv.remove("--dry-run")

    subcommand = sys.argv[2]

    if subcommand not in ["exif-date", "exif-loc", "exif"]:
        error_out(1, f"Unrecognized argument: {subcommand}")

    files = []
    in_files = False
    for arg in sys.argv:
        if arg == "--":
            in_files = True
            continue
        if in_files:
            files.append(arg)

    if subcommand in ["exif-date", "exif"]:
        tag_exif_date(db_path, files, dry_run)

    if subcommand in ["exif-loc", "exif"]:
        tag_exif_loc(db_path, files, dry_run)

def show_top_html():
    """Handle CGI requests."""
    
    print("Content-Type: text/html\n")
    print("""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Tagger</title>
</head>

<body>
  <h1>Tagger Photo Manager</h1>
  <section>
    <h2>Query</h2>
    <form action="/cgi-bin/tagger.cgi" method="get">
      <input type="text" name="query" placeholder="Query values...">
      <button type="submit">Query</button>
    </form>
  </section>
  <hr>
  <section>
    <h2>Tag Photos</h2>
    <pre>TODO</pre>
  </section>
  <hr>
  <section>
    <h2>Browse Photos</h2>
    <pre>TODO</pre>
  </section>
  
</body>
</html>
""")

def show_query_html(query: str):
    """Handle CGI requests."""
    
    print("Content-Type: text/html\n")
    print(f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Tagger</title>
</head>

<body>
  <h1>Tagger Photo Manager</h1>
  <section>
    <h2>Results</h2>
    <pre>{query}</pre>
  </section>
  
</body>
</html>
""")

def main():
    global _debug
    global DB_DIR
    use_system_config = False
    cgi = False

    # Debug option handling
    if "--debug" in sys.argv:
        sys.argv.remove("--debug")
        _debug = True

    # System mode option handling
    if "--global" in sys.argv:
        sys.argv.remove("--global")
        use_system_config = True

    # Help option handling
    if (
        "-h" in sys.argv
        or "--help" in sys.argv
        or "help" in sys.argv
        or len(sys.argv) == 1
    ):
        if len(sys.argv) == 1:
            eprint("Missing arguments.")

        display_usage()
        sys.exit(0)

    if "-c" in sys.argv:
        sys.argv.remove("-c")
        cgi = True

    if "--base-url" in sys.argv:
        base_url = sys.argv[sys.argv.index("--base-url") + 1]
        sys.argv.remove("--base-url")
        sys.argv.remove(base_url)

    if "--img-url" in sys.argv:
        img_url = sys.argv[sys.argv.index("--img-url") + 1]
        sys.argv.remove("--img-url")
        sys.argv.remove(img_url)

    if "--db-dir" in sys.argv:
        DB_DIR = sys.argv[sys.argv.index("--db-dir") + 1]
        sys.argv.remove("--db-dir")
        sys.argv.remove(DB_DIR)

    if cgi:
        query = os.environ.get("QUERY_STRING", "")
        dprint(f"{query = }")
        if not query:
            show_top_html()
        else:
            show_query_html(query)
        sys.exit(0)

    db_path = find_db_path()
    dprint(f"DB path is {db_path}")

    # Command handling
    if sys.argv[1] == "init":
        dprint("Initiating tagger database...")
        init_database(db_path, use_system_config)

    elif sys.argv[1] == "remove-database":
        dprint("Removing tagger database from...")
        if db_path:
            dprint(f"DB is {db_path}")
            os.remove(db_path)
            print("Tagger database successfully removed.")
            sys.exit(0)
        else:
            error_out(1, "Database was not found.")

    elif sys.argv[1] == "tag":
        dprint("Tagging files...")
        tag(db_path)

    elif sys.argv[1] == "list-tags":
        dprint("Querying database for tags...")
        list_tags(db_path)

    elif sys.argv[1] == "list-files":
        dprint("Querying database for files...")
        list_files(db_path)

    elif sys.argv[1] == "auto-tag":
        dprint("Auto-tagging...")
        auto_tag(db_path)

    elif sys.argv[1] == "replace-tag":
        ...



    else:
        dprint(f"Printing usage because invalid command syntax...")
        error_out(1, f"Invalid command: `{sys.argv[1]}`")

    sys.exit(0)


if __name__ == "__main__":
    main()
