#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
#
# bird-slideshow.py - a slideshow app, with network support and async
#     image loading
#

import os
import sys
from urllib.parse import urlparse
import tkinter
import requests
import PIL
from PIL import Image, ImageTk
from bs4 import BeautifulSoup

debug = False
CONFIG_FILE = "bird-slideshow.cfg"

TRUTH_TABLE = {"True": True, "False": False,
               "1": True, "0": False,
               "Yes": True, "No": False}


# have pylint ignore too many instance attributes in this class
class Config:  # pylint: disable=R0902
    def __init__(self, config_file=None):
        """Responsible for handling all configurable-related items and actions.
        Defines configurable items as attributes of an instance of the Config object.

        :param config_file: str - The name of the config file if there is one in the same
        directory as the sildeshow script. Default is None
        """

        # Default values
        self.sources = []
        self.wait_time = 5
        self.start_full = False
        self.win_start_res = "958x720"
        self.win_start_width = 958
        self.win_start_height = 720
        self.max_grow = 4.0
        self.cache_dir = "cache"

        self.config_file = config_file

        if self.config_file:
            self.read_config()
        else:
            self.input_config()

        self.convert_win_res()

    def read_config(self):
        """Read from config file (such as 'options.txt') and assign all the
        config items in the file to the attributes.
        """
        with open(self.config_file) as options_file:
            for line in options_file:
                if not line or line.startswith("#"):
                    continue
                name, value = line.strip().split("=", 1)

                if name == "source":
                    source = value
                    self.sources.append(source)
                elif name == "wait_time":
                    self.wait_time = int(float(value) * 1000)
                elif name == "start_full":
                    self.start_full = TRUTH_TABLE[value.capitalize()]
                elif name == "default_resolution":
                    self.win_start_res = value
                elif name == "max_grow":
                    self.max_grow = float(value)
                elif name == "cache_dir":
                    self.cache_dir = value
                else:
                    print("Unknown config option: '%s'" % name)

    def input_config(self):
        """Ask user to input all values for config items and assign them to attributes."""
        num_sources = int(input("Number of image sources (from directories or webpages): "))
        for _ in range(num_sources):
            source = input("Source of images (directory or url): ")
            self.sources.append(source)
        self.wait_time = int(float(input("Wait time in seconds: ")) * 1000)
        value = input("Start in fullscreen mode (True/False): ")
        self.start_full = TRUTH_TABLE[value.capitalize()]
        self.win_start_res = input("Window resolution (in the form '{width}x{height}'): ")
        self.max_grow = float(input("Max growth factor for image resizing (2 = 200%): "))
        self.cache_dir = input("Directory for cache: ")

    def convert_win_res(self):
        """Converts the win_res string into win_width and win_height ints."""
        width, height = self.win_start_res.split('x')
        self.win_start_width = int(width)
        self.win_start_height = int(height)


class SlideshowImage:
    def __init__(self, img_path=None):
        """Stores each image type in one object."""
        self.img_path = img_path
        self.pil_img = None
        self.tk_img = None

    def load_pil_from_path(self):
        """Takes an image path and turns it into a PIL image. If path is a remote
        (web) image, it will be downloaded into the cache directory from the config
        object.
        """

        global config

        # print("loading image: " + path)
        if self.img_path.startswith("http"):
            filepath = download_img(config.cache_dir, self.img_path)
            if filepath:
                try:
                    img = Image.open(filepath)
                except FileNotFoundError:
                    print("Error: image for path %s did not download" % self.img_path)
                    img = None
                except PIL.UnidentifiedImageError:
                    print("Error: data returned from download_img, for path",
                          "'%s' is invalid (not an image)" % self.img_path)
                    img = None
            else:
                print("Error: could not load remote image from path %s" % self.img_path)
                img = None
        else:
            try:
                img = Image.open(self.img_path)
            except FileNotFoundError:
                print("Error: could not load image from path %s" % self.img_path)
                img = None
            except PIL.UnidentifiedImageError:
                print("Error: data returned from download_img, for path",
                      "'%s' is invalid (not an image)" % self.img_path)
                img = None

        self.pil_img = img


def dprint(msg):
    """Debug print statement. Adds DEBUG to the front of a string and prints it."""
    global debug
    if debug:
        print("DEBUG:", str(msg))


# Globals
slideshow_imgs = []
config = None
imgs_index = -1
preload_index = -1

win = None
canvas = None
is_full = False
win_width = 958
win_height = 720


def find_config_file():
    """Finds the config file depending on what operating system is running this program."""

    # Check windows user directory
    if sys.platform == 'win32':
        file_path = os.path.expandvars(r'%LOCALAPPDATA%\\' + CONFIG_FILE)
        dprint(file_path)
        dprint(os.path.exists(file_path))
        if os.path.exists(file_path):
            return file_path

    # Check linux user config and system-wide directory
    if sys.platform.startswith('linux'):
        file_path = os.path.expandvars('$HOME/.config/' + CONFIG_FILE)
        dprint(file_path)
        if os.path.exists(file_path):
            return file_path
        file_path = '/etc/' + CONFIG_FILE
        if os.path.exists(file_path):
            return file_path

    # Check CWD
    file_path = CONFIG_FILE
    if os.path.exists(file_path):
        return file_path

    # Check directory of script location
    script_file = os.path.realpath(__file__)
    dprint("script_file = " + script_file)
    script_dir = os.path.dirname(script_file)
    file_path = script_dir + os.sep + CONFIG_FILE
    dprint(file_path)
    if os.path.exists(file_path):
        return file_path

    # Didn't find it
    return None


# Make sure there is a cache directory to download images into.
def define_cache(cfg):
    """Creates a cache folder if the name of the one in the Config object does
    not already exist.
    """
    if not os.path.exists(cfg.cache_dir):
        os.mkdir(cfg.cache_dir)


def init_window():
    """Create tkinter window and pack canvas to it.\n
    Also binds key presses to functions.
    """
    global win, canvas

    win = tkinter.Tk()
    win.title("Slideshow")
    win.geometry(config.win_start_res)
    canvas = tkinter.Canvas(win, width=win_width, height=win_height,
                            bg='black')
    canvas.pack(fill=tkinter.BOTH, expand=True)

    win.attributes("-fullscreen", config.start_full)
    win.bind("<F11>", toggle_fullscreen)
    win.bind("<Escape>", quit_window)
    win.bind("<Right>", rotate_img_forward)
    win.bind("<Left>", rotate_img_back)
    update_win_info()


# have pylint ignore unused arg 'event'
def toggle_fullscreen(event):  # pylint: disable=W0613
    """Switches between fullscreen and windowed.

    :param event - keypress event
    """
    global is_full
    is_full = not is_full
    win.attributes("-fullscreen", is_full)


# have pylint ignore unused arg 'event'
def quit_window(event):  # pylint: disable=W0613
    """Closes the window.

    :param event - keypress event
    """
    win.destroy()


def get_paths(sources):
    """Takes each source in Config.sources and stores the path in global img_paths.

    TODO: refactor img_paths into SlideshowImage object

    :param sources: list[str] - the list of sources from the Config object
    """

    for src in sources:
        if src.startswith("http"):
            get_http_paths(src)
        else:
            get_file_paths(src)


def get_http_paths(url):
    """Gets the img_path from the html and appends it to the global img_paths list.

    TODO: refactor img_paths into SlideshowImage object

    :param url: str - comes from the Config source
    """
    global slideshow_imgs

    dprint("getting html for url %s" % url)
    html = requests.get(url).text
    dprint("html=\n'%s'" % html)
    tags = get_img_tags(html)
    dprint("tags=%s" % tags)

    if not tags:
        print("Error: no image tags found on web page: %s" % url)
        return

    for img_tag in tags:
        # link = get_link(url, tag)

        # This does not handle srcset stuff

        base_url = os.path.dirname(url)
        dprint("base_url=%s" % base_url)
        url_parts = urlparse(url)
        url_prefix = url_parts.scheme + "://" + url_parts.netloc

        img_link = img_tag.get("src", None)

        if img_link.startswith("./"):
            img_link = url_prefix + img_link[1:]
        elif img_link.startswith("/"):
            img_link = url_prefix + img_link
        else:
            img_link = url_prefix + "/" + img_link

        dprint("Adding %s to img_paths" % img_link)
        # img_paths.append(img_link)
        # pil_imgs.append(None)
        # tk_imgs.append(None)
        slideshow_imgs.append(SlideshowImage(img_path=img_link))


def get_img_tags(html):
    """Gets the html <img> tags, e.x. <img src="..." height=...>.

    :param html: str - the full html text from the src url

    :returns img_tags: bs4.ResultSet - the list of html <img> tags
    """
    # Parse HTML Code
    soup = BeautifulSoup(html, 'html.parser')
    # find all images in URL
    img_tags = soup.findAll('img')
    dprint("img_tags=%s" % img_tags)
    return img_tags


def get_file_paths(directory):
    """Gets the directorial image tags.

    :param directory: str - the name of the directory from the Config source

    :returns img_tags: bs4.ResultSet - the list of html <img> tags
    """
    global slideshow_imgs

    saved_dir = os.getcwd()
    os.chdir(directory)
    img_filenames = os.listdir()

    if not img_filenames:
        print("Error: no image files found in directory %s" % directory)

    for filename in img_filenames:
        path = os.path.abspath(filename)
        # img_paths.append(path)
        # pil_imgs.append(None)
        # tk_imgs.append(None)
        slideshow_imgs.append(SlideshowImage(img_path=path))
    os.chdir(saved_dir)


def async_preload_img():
    """Increment preload_index then

    :param preload_index: int - ...
    """

    global slideshow_imgs
    global preload_index
    global win

    if preload_index >= len(slideshow_imgs)-1:
        dprint("IN ASYNC PRELOAD: done")
        return

    preload_index += 1

    dprint("IN ASYNC PRELOAD: preload_index = %s" % preload_index)

    # IF pil_img of SlideshowImage at preload_i is None
    if not slideshow_imgs[preload_index].pil_img:
        # pil_img of SlideshowImage at preload_i <- loaded img_path
        slideshow_imgs[preload_index].load_pil_from_path()
    else:
        return
    # win.after(100, async_preload_img())


def download_img(cache_dir, img_link):
    """Downloads the remote (web) image to the cache directory specified in
    :class:`Config` object.

    :param cache_dir: str = the directory to download the image to
    :param img_link: str = the http path to the remote image
    """

    dprint("In download_img (line 338) cache_dir = %s" % cache_dir)
    filename = os.path.basename(img_link)
    filepath = cache_dir + os.sep + filename

    if os.path.exists(filepath):
        print("Using img", filename, "from cache directory")
        return filepath

    try:
        print("Downloading img", img_link)
        response = requests.get(img_link)

        # print("filepath =", filepath)

        with open(filepath, "wb+") as f:
            f.write(response.content)

        return filepath

    # have pylint ignore this too-general exception
    # maybe later come back and catch some request-specific exceptions here
    # for better diagnostics
    except Exception:  # pylint: disable=W0703
        print("Error: Could not download %s" % img_link)
        return ""


def preload_imgs():
    """Immediately loads/downloads the first `2` images."""

    dprint("ENTERING PRELOAD_IMGS")

    global slideshow_imgs
    global preload_index

    for i in range(2):
        try:
            slideshow_imgs[i].load_pil_from_path()
        except IndexError:
            print("IN preload_imgs(): could not load img at index '%s'" % i)

    preload_index = i

    # async_preload_img()
    dprint("EXITING PRELOAD_IMGS")


def resize_img(img):
    img_w, img_h = img.size
    w_scale_factor = win_width/img_w
    h_scale_factor = win_height/img_h

    scale_factor = min(min(w_scale_factor, h_scale_factor), config.max_grow)
    # scale_factor = min(w_scale_factor, h_scale_factor)

    # print("DEBUG", scale_factor, MAX_GROW)

    # print("DEBUG", img_w, img_h, scale_factor, win_width, win_height)

    if scale_factor < .95 or scale_factor > 1.05:
        return img.resize((int(img_w*scale_factor), int(img_h*scale_factor)))

    return img


# Define rotation through each image in the directory after WAIT_TIME seconds
def update_img():
    """Takes the PIL img, resizes according to current screen dimenstions, creates tk img, and
    adds the tk img to the tk canvas.
    """
    global slideshow_imgs
    global imgs_index
    global win_width, win_height
    global canvas

    dprint("IN UPDATE IMG: imgs_index = " + str(imgs_index))

    # IF no pil_img at imgs_i of SlideshowImage:
    if not slideshow_imgs[imgs_index].pil_img:
        slideshow_imgs[imgs_index].load_pil_from_path()
    else:
        dprint("using already-loaded image")

    # Resize the PIL image; throw error if there is no PIL image at the index.
    if not slideshow_imgs[imgs_index].pil_img:
        print("ERROR, pil_img was None, img_path =", slideshow_imgs[imgs_index].img_path)
        return

    pil_img_r = resize_img(slideshow_imgs[imgs_index].pil_img)

    # Save tkinter img into global array for python reference counting.
    slideshow_imgs[imgs_index].tk_img = ImageTk.PhotoImage(pil_img_r)

    canvas.delete("all")

    win_width = win.winfo_width()
    win_height = win.winfo_height()

    canvas.create_image((win_width)/2, (win_height)/2,
                        anchor=tkinter.CENTER,
                        image=slideshow_imgs[imgs_index].tk_img)


def next_img():
    """Updates the imgs_index, then calls update_img() to put the image to the screen.
    After wait_time, it calls itself again, recursively.


    """

    global imgs_index
    imgs_index += 1
    if imgs_index >= len(slideshow_imgs)-1:
        imgs_index -= len(slideshow_imgs)
    if imgs_index < 0:
        imgs_index += len(slideshow_imgs)

    update_img()
    win.after(config.wait_time, next_img)
    async_preload_img()


# have pylint ignore unused arg 'event'
def rotate_img_forward(event):  # pylint: disable=W0613
    """Increments imgs_index then calls update_img()"""

    global imgs_index

    imgs_index += 1
    if imgs_index >= len(slideshow_imgs)-1:
        imgs_index -= len(slideshow_imgs)
    if imgs_index < 0:
        imgs_index += len(slideshow_imgs)

    update_img()


# have pylint ignore unused arg 'event'
def rotate_img_back(event):  # pylint: disable=W0613
    """Decrements imgs_index then calls update_img()"""

    global imgs_index

    imgs_index -= 1

    if imgs_index >= len(slideshow_imgs)-1:
        imgs_index -= len(slideshow_imgs)
    if imgs_index < 0:
        imgs_index += len(slideshow_imgs)

    update_img()


def update_win_info():
    """Gets the current width and height of the window and updates global
    win_width and win_height.
    """

    global win_width, win_height
    global win

    win_width = win.winfo_width()
    win_height = win.winfo_height()
    dprint("win_width")

    win.after(1, update_win_info)


def main():
    global debug
    global config
    global is_full, win_width, win_height
    global win

    if "--debug" in sys.argv:
        debug = True

    config_file = find_config_file()
    dprint(config_file)
    config = Config(config_file)

    is_full = config.start_full
    win_width = config.win_start_width
    win_height = config.win_start_height

    define_cache(config)
    init_window()
    get_paths(config.sources)

    if not slideshow_imgs:
        print("Error: no images found. Aborting program")
        print("(Maybe check the 'source' lines in your config file?)")
        sys.exit(1)

    print('Slideshow is running in another window...')
    preload_imgs()

    # start updating images after mainloop starts
    win.after(100, next_img)
    # win.after(200, async_preload_img())

    win.mainloop()


if __name__ == '__main__':
    main()
