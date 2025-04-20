#!/bin/sh
#
#
TAGGER_HOME=/home/tbird/work/ambienceTV/bird-slideshow/tagger

/usr/bin/python3 $TAGGER_HOME/tagger.py -c --db-dir $TAGGER_HOME --base-url http://localhost/ --img-url http://localhost/sample-pics --files-base $TAGGER_HOME/sample-pics/
