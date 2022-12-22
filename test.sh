#!/bin/sh
#
# Run some tests on bird-slideshow.py
#
# For pylint-related info, see:
#    https://jeffknupp.com/blog/2016/12/09/how-python-linters-will-save-your-large-python-project/

BOARD=bbb
if [ -n "$1" ] ; then
    if [ "$1" = "-h" ] ; then
        echo "Usage: test.sh [options]"
        echo " -h          Show this usage help"
        echo " -f          Do 'flake8' test of grabserial syntax"
        echo " -l          Do 'pylint' test of grabserial source"
        echo ""
        exit 0
    fi
    if [ "$1" = "-f" ] ; then
        echo "Running flake8 to analyze bird-slideshow.py source"
        # specifically tell flake8 that FileNotFoundError is a builtin
        #   exception name
        flake8 --max-line-length=100 --builtins=FileNotFoundError \
            --count bird-slideshow.py
        exit $?
    fi
    if [ "$1" = "-l" ] ; then
        echo "Running pylint to analyze bird-slideshow.py source"
        # C0103: invalid name (incorrect case for name class, etc.)
        # W0603: using the global statement
        # R0903: Too few public methods
        pylint --disable=C0103,W0603,R0903 --good-names=sf bird-slideshow.py
        exit $?
    fi
fi

if [ -n "$1" ] ; then
    echo "Unrecognized option '$1'"
    echo "Use -h for help"
    exit 0
fi

echo "No tests performed. Use -h for usage."

echo "Done in test.sh"
