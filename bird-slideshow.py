#!/usr/bin/python3
#
# bird-slideshow.py - a slideshow app, with network support and async
#     image loading
#
# todo:
#   add usage help

debug = False

import os
import sys
import requests
from urllib.parse import urlparse
from tkinter import *
from PIL import Image, ImageTk
from bs4 import BeautifulSoup

class Config:
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

        if self.config_file in os.listdir():
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
                    self.start_full = {"True":True,
                                       "False":False,
                                       "1":True,
                                       "0":False,
                                       "Yes":True,
                                       "No":False}[value.capitalize()]
                elif name == "default_resolution":
                    self.win_start_res = value
                elif name == "max_grow":
                    self.max_grow = float(value)
                elif name ==  "cache_dir":
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
        self.start_full = {"True":True, "False":False}[input("Start in fullscreen mode (True/False): ").capitalize()]
        self.win_start_res = input("Window resolution (in the form '{width}x{height}'): ")
        self.max_grow = float(input("Max growth factor for image resizing (2 = 200%): "))
        self.cache_dir = input("Directory for cache: ")

    def convert_win_res(self):
        """Converts the win_res string into win_width and win_height ints."""
        width, height = self.win_start_res.split('x')
        self.win_start_width = int(width)
        self.win_start_height = int(height)


class SlideshowImage:
    def __init__(self, img_path=None, pil_img=None, tk_img=None):
        """Stores each image type in one object."""
        self.img_path = img_path
        self.pil_img = pil_img
        self.tk_img = tk_img


def dprint(msg):
    """Debug print statement. Adds DEBUG to the front of a string and prints it."""
    global debug
    if debug:
        print("DEBUG:", str(msg))

# Globals
# img_paths = []
# pil_imgs = []
# tk_imgs = []
# ^v refactoring
slideshow_imgs = []

imgs_index = -1

config = Config("options.txt")

win = None
canvas = None
is_full = config.start_full
win_width = config.win_start_width
win_height = config.win_start_height


# Make sure there is a cache directory to download images into.
def define_cache(config):
    """Creates a cache folder if the name of the one in the Config object does
    not already exist.
    """
    if not os.path.exists(config.cache_dir):
        os.mkdir(config.cache_dir)


def init_window():
    """Create tkinter window and pack canvas to it.\n
    Also binds key presses to functions.
    """
    global win, canvas

    win = Tk()
    win.title("Slideshow")
    win.geometry(config.win_start_res)
    canvas = Canvas(win,
        width = win_width,
        height = win_height,
        bg='black'
    )
    canvas.pack(fill=BOTH, expand=True)

    win.attributes("-fullscreen", config.start_full)
    win.bind("<F11>", toggle_fullscreen)
    win.bind("<Escape>", quit_window)
    win.bind("<Right>", rotate_img_forward)
    win.bind("<Left>", rotate_img_back)
    update_win_info()


def toggle_fullscreen(event):
    """Switches between fullscreen and windowed.
    
    :param event - keypress event
    """
    global is_full
    is_full = not is_full
    win.attributes("-fullscreen", is_full)


def quit_window(event):
    """Closes the window.
    
    :param event - keypress event
    """
    win.destroy()


def get_paths(sources):
    """Takes each source in Config.sources and stores the path in global img_paths.

    TODO: refactor img_paths into SlideshowImage object

    :param sources: list[str] - the list of sources from the Config object
    """
    global img_paths

    for src in sources:
        if src.startswith("http"):
            get_http_paths(src)
        else:
            get_file_paths(src)

    if debug:
        for path in img_paths:
            dprint("path=%s" % path)


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


def async_preload_img(preload_index):
    """

    TODO: refactor img_paths and pil_imgs into SlideshowImage object

    :param preload_index: int - ...
    """
    # global img_paths, pil_imgs
    global slideshow_imgs

    dprint("IN ASYNC PRELOAD: preload_index = %s" % preload_index)

    # img_path = img_paths[preload_index]
    # pil_image = pil_imgs[preload_index]
    # if not pil_image:
    #     pil_image = load_img(img_path)
    #     pil_imgs[preload_index] = pil_image

    # IF pil_img of SlideshowImage at preload_i is None
    if not slideshow_imgs[preload_index].pil_img:
        # pil_img of SlideshowImage at preload_i <- loaded img_path
        slideshow_imgs[preload_index].pil_img = load_img(slideshow_imgs[preload_index].img_path)


def load_img(path):
    """Takes an image path and turns it into a PIL image. If path is a remote
    (web) image, it will be downloaded into the cache directory from the config
    object.
    
    :param path: str - the path of the image, whether it be from a remote image
    or from the local machine
    """
    # print("loading image: " + path)
    if path.startswith("http"):
        filepath = download_img(config.cache_dir, path)
        if filepath:
            try:
                img = Image.open(filepath)
            except:
                img = None
        else:
            print("Error: could not load remote image from path %s" % path)
            img = None
    else:
        try:
            img = Image.open(path)
        except:
            print("Error: could not load image from path %s" % path)
            img = None

    return img


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

    except:
        print("Error", "Could not download %s" % img_link)
        return ""


# TODO: bug: If only one path, will throw exception
# TODO: Does not change the preload index
def preload_imgs():
    """Immediately loads/downloads the first `2` images."""
    global slideshow_imgs

    for i in range(2):
        try:
            # img = load_img(img_paths[i])
            img = load_img(slideshow_imgs[i].img_path)
        except:
            img = None

        if img:
            # pil_imgs[i] = img
            slideshow_imgs[i].pil_img = img


def resize_img(img: Image.Image):
    img_w, img_h = img.size
    w_scale_factor = win_width/img_w
    h_scale_factor = win_height/img_h


    scale_factor = min(min(w_scale_factor, h_scale_factor), config.max_grow)
    # scale_factor = min(w_scale_factor, h_scale_factor)

    # print("DEBUG", scale_factor, MAX_GROW)

    # print("DEBUG", img_w, img_h, scale_factor, win_width, win_height)

    if scale_factor < .95 or scale_factor > 1.05:
        return img.resize((int(img_w*scale_factor), int(img_h*scale_factor)))


# Define rotation through each image in the directory after WAIT_TIME seconds
def update_img():
    global slideshow_imgs
    global imgs_index
    global win_width, win_height
    global canvas

    dprint("IN UPDATE IMG: imgs_index = " + str(imgs_index))


    # img_path = img_paths[imgs_index]
    # # PIL images list
    # pil_image = pil_imgs[imgs_index]
    # if not pil_image:
    #     pil_image = load_img(img_path)
    #     pil_imgs[imgs_index] = pil_image
    # else:
    #     dprint("using already-loaded image")

    # IF pil_img of SlideshowImage at imgs_i is None
    if not slideshow_imgs[imgs_index].pil_img:
        # pil_img of SlideshowImage at imgs_i <- loaded img_path
        slideshow_imgs[imgs_index].pil_img = load_img(slideshow_imgs[imgs_index].img_path)
    else:
        dprint("using already-loaded image")

    # Resize the PIL image; throw error if there is no PIL image at the index.
    # if not pil_image:
    #     print("ERROR, pil_img was None, img_path =", img_path)
    #     return

    if not slideshow_imgs[imgs_index].pil_img:
        print("ERROR, pil_img was None, img_path =", slideshow_imgs[imgs_index].img_path)
        return

    pil_img_r = resize_img(slideshow_imgs[imgs_index].pil_img)

    # Save tkinter img into global array for python reference counting.
    # tk_image = ImageTk.PhotoImage(pil_img_r)
    # tk_imgs[imgs_index] = tk_image

    slideshow_imgs[imgs_index].tk_img = ImageTk.PhotoImage(pil_img_r)

    canvas.delete("all")

    win_width = win.winfo_width()
    win_height = win.winfo_height()

    canvas.create_image(
        (win_width)/2,
        (win_height)/2,
        anchor = CENTER,
        image = slideshow_imgs[imgs_index].tk_img
    )


def next_img():
    global imgs_index
    imgs_index += 1
    if imgs_index >= len(slideshow_imgs)-1:
        imgs_index -= len(slideshow_imgs)
    if imgs_index < 0:
        imgs_index += len(slideshow_imgs)

    update_img()
    win.after(config.wait_time, next_img)

    preload_index = imgs_index + 1
    if preload_index >= len(slideshow_imgs)-1:
        preload_index = 0

    win.after(100, async_preload_img(preload_index))


def rotate_img_forward(event):
    global imgs_index
    imgs_index += 1
    if imgs_index >= len(slideshow_imgs)-1:
        imgs_index -= len(slideshow_imgs)
    if imgs_index < 0:
        imgs_index += len(slideshow_imgs)

    update_img()


def rotate_img_back(event):
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
    win_width = win.winfo_width()
    win_height = win.winfo_height()

    win.after(1, update_win_info)



def main():
    global debug
    if "--debug" in sys.argv:
        debug = True

    define_cache(config)
    init_window()
    get_paths(config.sources)
    # if not img_paths:
    if not slideshow_imgs:
        print("Error: no images found. Aborting program")
        print("(Maybe check the 'source' lines in your config file?)")
        sys.exit(1)

    print('Slideshow is running in another window...')
    preload_imgs()

    win.after(100, next_img)

    win.mainloop()


if __name__ == '__main__':
    main()
