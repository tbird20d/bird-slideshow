#!/bin/bash
# populate-sample-db.sh [user] [--debug]
#  Create a tagger database in the current directory, and populate
#  it with tags for photo files in sample-pics.
#
#  By default, use a tagger db in the tagger home directory.
#  But you can use 'populate-sample-db.sh user' to use the
#  default location for the database ($HOME/.config/tagger.db)
#  This will OVERWRITE that file, so if you have any existing
#  data, be very careful.

# uncomment the following to debug this script
#set -x

TAGGER_HOME=/home/tbird/work/ambienceTV/bird-slideshow/tagger
TAGGER=tagger.py

if [ "$1" = "user" ] ; then
    shift
    ARGS="$@"
    if [ -f "$HOME/.config/tagger.db" ] ; then
        echo "WARNING: about to remove $HOME/.config/tagger.db"
        read -p "Really proceed? [Y/N]" yes_no
        if [ $yes_no != "Y" ] ; then
            echo "Aborting."
            exit 1
        fi
    fi
    HELP_ARGS=""
else
    ARGS="--db-dir $TAGGER_HOME $1"
    HELP_ARGS="--db-dir $TAGGER_HOME"
fi

pushd $TAGGER_HOME >/dev/null

# remove pre-existing tagger.db if present
if [ -f "$TAGGER_HOME/tagger.db" ] ; then
    ./$TAGGER $ARGS remove-database
fi
./$TAGGER $ARGS init

pushd ./sample-pics >/dev/null

../$TAGGER $ARGS tag sample -- dessert-swans.JPG ropes-zipline-course.JPG Tori-gate-japan.jpg skyscraper.jpg
../$TAGGER $ARGS tag outside -- ropes-zipline-course.JPG Tori-gate-japan.jpg skyscraper.jpg
../$TAGGER $ARGS tag tree -- ropes-zipline-course.JPG Tori-gate-japan.jpg
../$TAGGER $ARGS tag building -- skyscraper.jpg
../$TAGGER $ARGS tag japan -- Tori-gate-japan.jpg
../$TAGGER $ARGS tag food -- dessert-swans.JPG

popd >/dev/null

echo "######## Here is the current sqlite3 database: #########"
sqlite3 tagger.db .dump

cat <<HERE

Done.
Try ./$TAGGER $HELP_ARGS list-files <tag>
or  ./$TAGGER $HELP_ARGS list-tags
or  ./$TAGGER $HELP_ARGS tag <tag> -- <file>
HERE

popd >/dev/null
