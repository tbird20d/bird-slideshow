README for bird-slideshow.py program

This program shows a sequence of images, specified by a config file
(or on the command line).

Features:
 - the window may be resized
 - pictures are loaded asynchronously from the display
   - ie. the next image is loaded while the current image is being displayed
 - a cache is created for recently used images (so they can cycle without
   loading them multiple times
 - pictures may be loaded from local directories, or web pages
 - multiple picture sources may be specified

Config File
-----------
Here are the allowed fields in the config file (which is in a simple name=value
text file format):

source= specifies the directory or website to read pictures from
  This option can be specified multiple times in the config file.

wait_time= specified the amount of time to wait between displaying pictures

start_full= can be 0 or 1 (or True or False) to indicate starting the window
  in full-screen mode.

default_resolution= expressed as numbers separated by an 'x' (e.g. 640x480)

max_grow= specifies the maximum amount a picture may be enlarged
  This is an integer (e.g. 5).  The value '2' would limit the enlargment
  to 200%.  This is to keep small pictures from becoming
  too pixelated when upscaling them.  Image are automaticaly downscaled
  if they are too big for the current window, and upscaled (up to
  a factor of 'max_grow') when they are smaller then the current window.

cache_dir= specifies the directory to be used for caching images

