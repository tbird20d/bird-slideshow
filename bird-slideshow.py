#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
#
# bird-slideshow.py - a slideshow app, with network support and async
#     image loading
#

"""Implements a simple slideshow."""

import os
import sys
import subprocess
from urllib.parse import urlparse, ParseResult
import tkinter
import requests
import PIL
from PIL import Image, ImageTk
from bs4 import BeautifulSoup, ResultSet

_debug: bool = False
VERSION: tuple = (0, 7, 0)
CONFIG_FILE: str = "bird-slideshow.cfg"
TRUTH_TABLE: dict = {"True": True, "False": False,
                     "1": True, "0": False,
                     "Yes": True, "No": False}


# Classes
# have pylint ignore too many instance attributes in this class
class Config:  # pylint: disable=R0902
    """Responsible for handling all configurable-related items and actions.

    Defines configurable items as attributes of an instance of the `Config`
    object.
    """

    # have pyre ignore None casting to type annotated parameter
    def __init__(self, config_file: str = None):  # pyre-ignore[9]
        """Constructs a new instance of the `Config` object.

        Args:
            ::param:`config_file: str` - The name of the config file if there
            is one (default is None)

        Calls:
            ::private_method:`_read_config()`
            ::private_method:`_input_config()`
            ::private_method:`_convert_win_res()`
        """

        # Default values
        self.sources: list = []
        self.wait_time: int = 5
        self.start_full: bool = False
        self.win_start_res: str = "958x720"
        self.win_start_width: int = 958
        self.win_start_height: int = 720
        self.max_resize: float = 4.0
        self.max_preload: int = 2
        self.cache_dir: str = "cache"
        self.small_memory: bool = False

        self.config_file: str = config_file

        if self.config_file:
            self._read_config()
        else:
            self._input_config()

        self._convert_win_res()

    def _read_config(self):
        """Read from config file and assign all the config items in the file to the attributes.

        Called by:
            ::constructor:`self.__init__()`
        """

        with open(self.config_file, 'r', encoding='utf-8') as options_file:
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
                elif name == "max_preload":
                    self.max_preload = int(value)
                elif name == "max_resize":
                    value = float(value)
                    # constrain to between 0.05 and 50
                    value = min(max(value, 0.05), 50)
                    self.max_resize = value
                elif name == "cache_dir":
                    self.cache_dir = value
                elif name == "small_memory":
                    self.small_memory = TRUTH_TABLE[value.capitalize()]
                else:
                    print("Unknown config option: '%s'" % name)

    def _input_config(self):
        """Ask user to input all values for config items and assign them to attributes.

        Called by:
            ::constructor:`self.__init__()`
        """

        num_sources = int(input("Number of image sources (from directories or webpages): "))
        for _ in range(num_sources):
            source = input("Source of images (directory or url): ")
            self.sources.append(source)
        self.wait_time = int(float(input("Wait time in seconds: ")) * 1000)
        value = input("Start in fullscreen mode (True/False): ")
        self.start_full = TRUTH_TABLE[value.capitalize()]
        self.win_start_res = input("Window resolution (in the form '{width}x{height}'): ")
        self.max_resize = float(input("Max resize factor for image resizing (2 = 200%): "))
        self.cache_dir = input("Directory for cache: ")

    def _convert_win_res(self):
        """Converts the win_res string into win_width and win_height ints.

        Called by:
            ::constructor:`self.__init__()`
        """

        width, height = self.win_start_res.split('x')
        self.win_start_width = int(width)
        self.win_start_height = int(height)


class SlideshowImage:
    """Stores each image type in one object."""

    def __init__(self, img_path: str):
        """Constructs a new instance of `SlideshowImage`

        Args:
            ::param:`img_path: str` - the full image path
        """
        self.img_path: str = img_path
        self.local_filepath: str = ""
        # have pyre ignore type annotated attributes initialized as None
        self.pil_img: Image.Image = None  # pyre-ignore[8]
        self.tk_img: ImageTk.PhotoImage = None  # pyre-ignore[8]

    def get_image_local(self):
        """Gets an image file from image path into local filesystem.  If
        the image is remote (web or ssh), it is downloaded to the cache
        and a cache filepath is returned.

        Returns:
            ::return:`filepath, img_src` - the path to the image file, and
              a string describing the image source

        Called by:
            ::method:'load_pil_from_path()'
        """
        global config

        if self.img_path.startswith("http"):
            img_src = "downloaded from web"
            filepath = download_web_img(config.cache_dir, self.img_path)
            if not filepath:
                print("Error: could not load remote image from path %s" % self.img_path)
        elif self.img_path.startswith("ssh:"):
            img_src = "downloaded from ssh"
            filepath = download_ssh_img(config.cache_dir, self.img_path)
            if not filepath:
                print("Error: could not load remote image from path %s" % self.img_path)
        else:
            img_src = "from local filesystem"
            filepath = self.img_path

        return filepath, img_src

    def load_pil_from_path(self):
        """Takes an image path and turns it into a PIL image.

        Downloads the image file into cache if necessary, then reads the
        image file into a PIL image in memory.

        Called by:
            ::function:`async_preload_img()`
            ::function:`preload_imgs()`
            ::function:`update_img()`

        Calls:
            ::function:`download_web_img()`
            ::function:`download_ssh_img()`
        """

        global config
        global load_count

        if self.pil_img:
            return

        # if image is not already downloaded, put it into local cache
        img_src = "from previous download"
        if not self.local_filepath:
            filepath, img_src = self.get_image_local()
            self.local_filepath = filepath

        img: Image.Image = None
        try:
            dprint("loading PIL image for file %s" % self.local_filepath)
            img = Image.open(self.local_filepath)
        except FileNotFoundError:
            print("Error: could not load image from path %s" % self.local_filepath)
        except PIL.UnidentifiedImageError:
            print("Error: data %s, for path '%s' is invalid (not an image)" %
                  (img_src, self.img_path))

        if img:
            self.pil_img = img
            load_count += 1


# Global Variables
# have pyre ignore type annotated variables initialized as None
slideshow_imgs: list = []
config: Config = None  # pyre-ignore[9]
imgs_index: int = -1
preload_index: int = -1
load_count: int = 0

win: tkinter.Tk = None  # pyre-ignore[9]
canvas: tkinter.Canvas = None  # pyre-ignore[9]
is_full: bool = False
is_paused: bool = False
win_width: int = 958
win_height: int = 720


# Global Functions
def dprint(msg):
    """Debug print statement. Adds DEBUG to the front of a string
    and prints it.
    """

    global _debug

    if _debug:
        print("DEBUG:", str(msg))


def find_config_file():
    """Finds the config file depending on what operating system is running
    this program.

    Returns:
        ::return:`str | None` - either the path to the config file or None

    Called by:
        ::__main__:`main()`
    """

    # Check windows user directory
    if sys.platform == 'win32':
        file_path = os.path.expandvars('%LOCALAPPDATA%\\' + CONFIG_FILE)
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


def define_cache(cfg: Config):
    """Creates a cache folder if the name of the one in the passed `Config`
    object does not already exist.

    Args:
        ::param:`cfg: Config` - the `Config` object to get the cache
        directory from

    Called by:
        ::__main__:`main()`
    """

    if not os.path.exists(cfg.cache_dir):
        os.mkdir(cfg.cache_dir)


def init_window():
    """Create tkinter window and pack canvas to it.

    Also binds key presses to functions.

    Called by:
        ::__main__:`main()`

    Calls:
        ::function:`toggle_fullscreen()`
        ::function:`quit_window()`
        ::function:`rotate_img_forward()`
        ::function:`rotate_img_back()`
        ::function:`update_win_info()`
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
    win.bind("q", quit_window)
    win.bind("<Right>", rotate_img_forward)
    win.bind("<Left>", rotate_img_back)
    win.bind("p", toggle_pause)
    update_win_info()


# have pylint ignore unused arg 'event'
def toggle_fullscreen(event):  # pylint: disable=W0613
    """Switches between fullscreen and windowed.

    Args:
        ::param:`event` - keypress event

    Called by:
        ::function:`init_window()`
    """
    global is_full
    is_full = not is_full
    win.attributes("-fullscreen", is_full)


# have pylint ignore unused arg 'event'
def toggle_pause(event):  # pylint: disable=W0613
    """Switches between fullscreen and windowed.

    Args:
        ::param:`event` - keypress event

    Called by:
        ::function:`init_window()`
    """
    global is_paused

    is_paused = not is_paused
    update_img()


# have pylint ignore unused arg 'event'
def quit_window(event):  # pylint: disable=W0613
    """Closes the window.

    Args:
        ::param:`event` - keypress event

    Called by:
        ::function:`init_window()`
    """
    win.destroy()


def get_paths(sources: list):
    """Takes each source in passed sources and stores the path as an attribute
    of `SlideshowImage` and appends to global list slideshow_imgs.

    Args:
        ::param:`sources: list[str]` - the list of sources from the `Config` object

    Called by:
        ::__main__:`main()`

    Calls:
        ::function:`get_file_paths()`
        ::function:`get_http_paths()`
        ::function:`get_ssh_paths()`
    """

    for src in sources:
        if src.startswith("http"):
            get_http_paths(src)
        elif src.startswith("ssh"):
            get_ssh_paths(src)
        else:
            get_file_paths(src)


def get_http_paths(url: str):
    """Gets the <img> tags from the html, gets image links from the src
    attribute of each tag, and creates new instances of `SlideshowImage` using
    the links which are then appended to global list.

    Args:
        ::param:`url: str` - comes from the `Config` source attribute

    Called by:
        ::function:`get_paths()`

    Calls:
        ::function:`get_img_tags()`
    """
    global slideshow_imgs

    dprint("getting html for url %s" % url)
    html: str = requests.get(url, timeout=10).text
    dprint("html=\n'%s'" % html)
    tags: ResultSet = get_img_tags(html)
    dprint("tags=%s" % tags)

    if not tags:
        print("Error: no image tags found on web page: %s" % url)
        return

    for img_tag in tags:
        # link = get_link(url, tag)

        # This does not handle srcset stuff

        base_url: str = os.path.dirname(url)
        dprint("base_url=%s" % base_url)
        url_parts: ParseResult = urlparse(url)
        url_prefix: str = url_parts.scheme + "://" + url_parts.netloc

        img_link: str = img_tag.get("src", None)

        if img_link.startswith("./"):
            img_link = url_prefix + img_link[1:]
        elif img_link.startswith("/"):
            img_link = url_prefix + img_link
        else:
            img_link = url_prefix + "/" + img_link

        dprint("Adding %s to img_paths" % img_link)
        slideshow_imgs.append(SlideshowImage(img_link))


def get_img_tags(html: str) -> ResultSet:
    """Gets all the html <img> tags (e.x. <img src="..." height=...>) from the
    passed html text.

    Args:
        ::param:`html: str` - the full html text from the src url

    Returns:
        ::return:`ResultSet[Tag]` - a list of html <img> tags

    Called by:
        ::function:`get_http_paths()`
    """
    # Parse HTML Code
    soup = BeautifulSoup(html, 'html.parser')
    # find all images in URL
    img_tags: ResultSet = soup.findAll('img')
    dprint("img_tags=%s" % img_tags)
    return img_tags


def ssh_path_elements(src_path: str) -> tuple:
    """Gets the parts of an ssh src path: user, password, server, path

    Args:
        ::param:`src_path: str` - the source path

    Returns:
        ::return:`tuple[str, str, str, str]` - the user, password, server, and path

    Called by:
        ::function:`get_ssh_paths()`
    """
    if src_path.startswith("ssh:"):
        src_path = src_path[4:]

    if '@' in src_path:
        user_and_password, server_and_path = src_path.split('@', 1)
        if ":" in user_and_password:
            user, password = user_and_password.split(':', 1)
        else:
            user = user_and_password
            password = ""
    else:
        user = ""
        password = ""
        server_and_path = src_path

    if ":" in server_and_path:
        server, path = server_and_path.split(':', 1)
    else:
        print("Error: missing ':' in server and path portion of src path: '%s'" % server_and_path)
        server = server_and_path
        path = "/"

    return (user, password, server, path)


# have pylint ignore too many local vars and too many branches
def get_ssh_paths(src_path: str):  # pylint: disable=R0914,R0912
    """Gets a list of images from the indicated ssh source path, and creates
    new instances of `SlideshowImage` using the links which are then appended
    to global list.

    Args:
        ::param:`src_path: str` - comes from the `Config` source attribute

    Called by:
        ::function:`get_paths()`

    Calls:
        ::function:`ssh_path_elements()`
    """
    global slideshow_imgs

    dprint("getting directory listing for %s" % src_path)
    user, password, server, path = ssh_path_elements(src_path)
    # build appropriate exec string based on src_path elements
    if password:
        cmd = ["/usr/bin/sshpass", "-p", password]
    else:
        cmd = []

    if user:
        user_and_host = user + "@" + server
    else:
        user_and_host = server

    # escape spaces in path
    escaped_path = path.replace(" ", "\\ ")

    cmd += ['/usr/bin/ssh', user_and_host, 'ls', '-F', escaped_path]

    dprint("cmd=%s" % cmd)

    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, check=True, timeout=10)
    except subprocess.CalledProcessError as e:
        print("Error: Executing command '%s'\n%s" % (" ".join(cmd), e.stderr))
        return

    # parse the directory listing
    dir_listing = p.stdout.decode("utf-8")
    dprint("host directory listing=%s" % dir_listing)

    if password:
        user_and_pw = user + ":" + password
    else:
        user_and_pw = user

    # scan directory listing from host, and convert into ssh_paths
    lines = dir_listing.split("\n")
    for line in lines:
        if not line:
            continue
        if line.endswith("/"):
            dprint("found directory '%s'" % line)
            continue
        if line.endswith("*"):
            line = line[:-1]
        ext = os.path.splitext(line)[1]
        if ext in [".png", ".jpeg", ".JPG", ".jpg"]:
            ssh_path = "ssh:%s@%s:%s/%s" % (user_and_pw, server, path, line)
            slideshow_imgs.append(SlideshowImage(ssh_path))
        else:
            dprint("%s is not a picture" % line)


def get_file_paths(directory: str):
    """Gets the paths of each image in the passed directory and creates new
    instances of `SlideshowImage` using the paths which are then appended to
    global list.

    Args:
        ::param:`directory: str` - the name of the directory from the `Config` source

    Called by:
        ::function:`get_paths()`
    """

    global slideshow_imgs

    saved_dir: str = os.getcwd()
    os.chdir(directory)
    img_filenames: list = os.listdir()

    if not img_filenames:
        print("Error: no image files found in directory %s" % directory)

    for filename in img_filenames:
        path: str = os.path.abspath(filename)
        slideshow_imgs.append(SlideshowImage(path))
    os.chdir(saved_dir)


def async_preload_img():
    """Increment preload_index then load the PIL image of the `SlideshowImage`
    at that preload_index.

    Called by:
        ::function:`next_img()`

    Calls:
        ::SlideshowImage_method:`load_pil_from_path()`
    """

    global slideshow_imgs
    global preload_index
    global load_count
    global win

    if load_count >= len(slideshow_imgs):
        dprint("IN ASYNC PRELOAD: done")
        return

    preload_index += 1
    if preload_index >= len(slideshow_imgs)-1:
        preload_index = 0

    dprint("IN ASYNC PRELOAD: preload_index = %s" % preload_index)

    # IF pil_img of SlideshowImage at preload_i is None
    if not slideshow_imgs[preload_index].pil_img:
        # pil_img of SlideshowImage at preload_i <- loaded img_path
        slideshow_imgs[preload_index].load_pil_from_path()
    else:
        return
    # win.after(100, async_preload_img())


def download_web_img(cache_dir: str, img_link: str) -> str:
    """Downloads the remote (web) image to the cache directory specified in
    `Config` object.

    Args:
        :param:`cache_dir: str` - the directory to download the image to
        :param:`img_link: str` - the http path to the remote image

    Returns:
        ::return:`str` - the path to the downloaded file in the cache

    Called by:
        ::SlideshowImage_method:`load_pil_from_path()`
    """

    dprint("In download_web_img (line 338) cache_dir = %s" % cache_dir)
    filename: str = os.path.basename(img_link)
    filepath: str = cache_dir + os.sep + filename

    if os.path.exists(filepath):
        dprint("Using img " + filename + " from cache directory")
        return filepath

    try:
        print("Downloading img", img_link)
        response = requests.get(img_link, timeout=10)

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


# have pylint ignore too many local variables
def download_ssh_img(cache_dir: str, ssh_path: str) -> str:  # pylint: disable=R0914
    """Downloads the remote (ssh) image to the cache directory specified in
    `Config` object.

    Args:
        :param:`cache_dir: str` - the directory to download the image to
        :param:`ssh_path: str` - the ssh path to the remote image

    Returns:
        ::return:`str` - the path to the downloaded file in the cache

    Called by:
        ::SlideshowImage_method:`load_pil_from_path()`

    Calls:
        ::function:`ssh_path_elements()`
    """

    user, password, server, path = ssh_path_elements(ssh_path)

    # build appropriate exec string based on ssh_path elements
    if password:
        cmd = ["sshpass", "-p", password]
    else:
        cmd = []

    if user:
        user_and_host = user + "@" + server
    else:
        user_and_host = server

    # escape spaces in path
    escaped_path = path.replace(" ", "\\ ")

    # scp user@host:/path cache_dir
    host_path = "%s:%s" % (user_and_host, escaped_path)
    filename = os.path.basename(path)
    cache_path = "%s/%s" % (cache_dir, filename)

    # if already in cache, don't download again
    if os.path.exists(cache_path):
        dprint("Using img " + filename + " from cache directory")
        return cache_path

    cmd += ['/usr/bin/scp', host_path, cache_path]

    dprint("cmd=%s" % cmd)

    dprint("Starting download process...")
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           check=True, timeout=20)
    except subprocess.CalledProcessError as e:
        print("Error: Executing '%s'\n%s" % (" ".join(cmd), e.stderr))

    dprint("done")
    out = p.stdout.decode("utf-8")
    err = p.stderr.decode("utf-8")
    dprint("out=%s" % out)
    dprint("err=%s" % err)

    if os.path.exists(cache_path):
        filepath = cache_path
    else:
        filepath = ""

    return filepath


def preload_imgs():
    """Immediately loads/downloads the first :hardcoded:`2` images.

    Called by:
        ::__main__:`main()`

    Calls:
        ::SlideshowImage_method:`load_pil_from_path()`
    """

    global config
    global slideshow_imgs
    global preload_index

    dprint("ENTERING PRELOAD_IMGS")

    for i in range(config.max_preload):
        try:
            slideshow_imgs[i].load_pil_from_path()
        except IndexError:
            print("IN preload_imgs(): could not load img at index '%s'" % i)

    preload_index = i

    # async_preload_img()
    dprint("EXITING PRELOAD_IMGS")


def resize_img(img: Image.Image) -> Image.Image:
    """Takes a pil img and returns a resized pil img.

    Args:
        ::param:`img: Image.Image` - the pil img to be resized

    Returns:
        ::return:`Image.Image` - the resized pil img

    Called by:
        ::function:`update_img()`
    """

    img_w, img_h = img.size
    w_scale_factor: float = win_width/img_w
    h_scale_factor: float = win_height/img_h

    # Picks the minimum between the vertical or horizontal scale factor, then takes the minimum
    # between the scale factor and the max_resize configuration setting.
    scale_factor = min(min(w_scale_factor, h_scale_factor), config.max_resize)
    # print(f"DEBUG: scale_factor = {scale_factor}, config.max_resize = {config.max_resize}")

    if scale_factor < .95 or scale_factor > 1.05:
        return img.resize((int(img_w*scale_factor), int(img_h*scale_factor)))

    return img


# Define rotation through each image in the directory after WAIT_TIME seconds
def update_img():
    """Takes the PIL img, resizes according to current screen dimenstions, creates tk img, and
    adds the tk img to the tk canvas.

    Called by:
        ::function:`next_img()`
        ::function:`rotate_img_forward()`
        ::function:`rotate_img_back()`

    Calls:
        ::function:`resize_img()`
    """

    global slideshow_imgs
    global imgs_index
    global win_width, win_height
    global canvas
    global is_paused

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

    pil_img_r: Image.Image = resize_img(slideshow_imgs[imgs_index].pil_img)

    # Save tkinter img into global array for python reference counting.
    slideshow_imgs[imgs_index].tk_img = ImageTk.PhotoImage(pil_img_r)

    canvas.delete("all")

    win_width = win.winfo_width()
    win_height = win.winfo_height()

    canvas.create_image((win_width)/2, (win_height)/2,
                        anchor=tkinter.CENTER,
                        image=slideshow_imgs[imgs_index].tk_img)

    if is_paused:
        # show paused status
        # Put text on a black background for readability
        canvas.create_rectangle((win_width)/2-50, 36, (win_width)/2+50, 64, fill="black")
        canvas.create_text((win_width)/2, 50, anchor=tkinter.CENTER,
                           text=" paused ", fill="white",
                           font=('Helvetica 15 bold'))
        canvas.pack()


def next_img():
    """Updates the imgs_index, then calls update_img() to put the image to the screen.
    It then schedules itself to be called again after wait_time amount of time.

    Called by:
        ::__main__:`main()`
        ::function:`next_img()`

    Calls:
        ::function:`update_img()`
        ::function:`next_img()`
        ::function:`async_preload_img()`
    """

    global imgs_index
    global is_paused

    if not is_paused:
        last_img = slideshow_imgs[imgs_index]
        imgs_index += 1
        if imgs_index >= len(slideshow_imgs)-1:
            imgs_index -= len(slideshow_imgs)
        if imgs_index < 0:
            imgs_index += len(slideshow_imgs)

        update_img()

        if config.small_memory:
            dprint("Unloading img: %s" % last_img.img_path)
            last_img.tk_img = None
            last_img.pil_img = None

    win.after(config.wait_time, next_img)
    async_preload_img()


# have pylint ignore unused arg 'event'
def rotate_img_forward(event):  # pylint: disable=W0613
    """Increments imgs_index then calls update_img()

    Args:
        ::param:`event` - keypress event

    Called by:
        ::function:`init_window()`

    Calls:
        ::function:`update_img()`
    """

    global imgs_index

    imgs_index += 1
    if imgs_index >= len(slideshow_imgs)-1:
        imgs_index -= len(slideshow_imgs)
    if imgs_index < 0:
        imgs_index += len(slideshow_imgs)

    update_img()


# have pylint ignore unused arg 'event'
def rotate_img_back(event):  # pylint: disable=W0613
    """Decrements imgs_index then calls update_img()

    Args:
        ::param:`event` - keypress event

    Called by:
        ::function:`init_window()`

    Calls:
        ::function:`update_img()`
    """

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

    Called by:
        ::function:`init_window()`
        ::function:`update_win_info()`

    Calls:
        ::function:`update_win_info()`
    """

    global win_width, win_height
    global win

    win_width = win.winfo_width()
    win_height = win.winfo_height()
    # dprint("win_width")

    win.after(1, update_win_info)


def main():
    """Program main function"""

    global _debug
    global config
    global is_full, win_width, win_height
    global win

    if "--debug" in sys.argv:
        _debug = True
        sys.argv.remove("--debug")

    config_file: str = find_config_file()
    dprint(config_file)

    if "-V" in sys.argv or "--version" in sys.argv:
        print("bird-slideshow v%d.%d.%d" % VERSION)
        print("Using config file: %s" % config_file)
        sys.exit(0)

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
