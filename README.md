README for bird-slideshow.py program

This program shows a sequence of images, specified by a config file
(or on the command line).

Features:
 - the window may be resized
 - pictures are loaded asynchronously from the display
   - ie. the next image is loaded while the current image is being displayed
 - a cache is created for recently used images (so they can cycle without
   loading them multiple times)
 - pictures may be loaded from local directories, web pages, a remote
   machine via ssh, or based on a listing from the 'tagger' app.
 - multiple picture sources may be specified

Config File
-----------
Here are the allowed fields in the config file (which is in a simple name=value
text file format):

source= specifies the directory, website, ssh path, or tagger query to read
  pictures from. This option can be specified multiple times in the config file.

wait_time= specified the amount of time to wait between displaying pictures

start_full= can be 0 or 1 (or True or False) to indicate starting the window
  in full-screen mode.

default_resolution= expressed as numbers separated by an 'x' (e.g. 640x480)

max_resize= specifies the maximum size a picture can be as a percentage of its
  original size
  This is a float (e.g. 2.3, 1.0, etc.).  The value '2.0' would limit the
  enlargment to 200%.  This is generally used to keep small pictures from
  becoming too pixelated when upscaling them, although technically one could
  set this to a percentage smaller than 100% (with a value less than 1.0).
  Images are automaticaly downscaled if they are too big for the current
  window, and upscaled ([or resized] to a factor of 'max_resize') when they
  are smaller then the current window.

cache_dir= specifies the directory to be used for caching images

max_preload= maximum number of images to preload

small_memory= can be 0 or 1 (True or False).  if set, bird-slideshow will
  try to use less memory.  It will keep less pictures in physical memory,
  which may cause delays as images are re-read from the disk cache.

Operation
---------
While the slideshow is running, you may type the follow keys:
 - left arrow = go back one image
 - right arrow = go forward one image
 - F11 = toggle fullscreen mode
 - p = toggle pause
 - ESC or q = quit the program

