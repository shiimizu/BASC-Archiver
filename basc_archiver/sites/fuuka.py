#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Fuuka Archiver Class
from __future__ import print_function
from __future__ import absolute_import

from .base import BaseSiteArchiver
from .. import utils

#from . import pyfuuka
import pyfuuka
from bs4 import BeautifulSoup

import sys
import os
import re
import codecs
import threading
import json as Json
from urllib.parse import urlparse

THREAD_NONEXISTENT = 'Thread {site} / {board} / {thread_id} does not exist.'
THREAD_NONEXISTENT_REASON = ("Either the thread already 404'ed, your URL is incorrect, "
                             "or you aren't connected to the internet.")
IMAGE_DL = '{timestamp}   Image {site} / {board} / {thread_id} / {filename} downloaded'
THUMB_DL = '{timestamp}   Thumbnail {site} / {board} / {thread_id} / {filename} downloaded'
THREAD_404 = "{timestamp} Thread {site} / {board} / {thread_id} 404'd."
THREAD_ARCHIVED = "{timestamp} Thread {site} / {board} / {thread_id} has been archived."
THREAD_NEW_REPLIES = '{timestamp} Thread {site} / {board} / {thread_id}  -  {replies} new replies'
THREAD_CHILD_FOUND = '{timestamp} Child thread {site} / {board} / {thread_id} found and now being downloaded'

# finding board name/thread id
THREAD_REGEX = re.compile(r"""https?://(?:boards\.)?4chan(?:nel)?\.org/([0-9a-zA-Z]+)/(?:res|thread)/([0-9]+)""")

# top level domains
FOURCHAN_BOARDS = 'boards.4chan.org'
FOURCHAN = '4chan.org'
FOURCHANNEL = '4channel.org'
FOURCHANNEL_BOARDS = 'boards.4channel.org'
FOURCHAN_CDN = '4cdn.org'

# new urls
#FOURCHAN_API = 'api.' + FOURCHAN # api.4chan.org also works, but 4cdn still on
#FOURCHAN_IMAGES = 'is.' + FOURCHAN
#FOURCHAN_THUMBS = 'is.' + FOURCHAN
#FOURCHAN_STATIC = 's.' + FOURCHAN_CDN # static.4chan.org also works, but not yet

# cdn domains (no longer in use for images)
FOURCHAN_API = 'a.' + FOURCHAN_CDN
FOURCHAN_IMAGES = 'i.' + FOURCHAN_CDN
FOURCHAN_THUMBS = 'i.' + FOURCHAN_CDN
FOURCHAN_STATIC = 's.' + FOURCHAN_CDN

# retrieval footer regex
FOURCHAN_BOARDS_FOOTER = '/%s/thread/%s'
FOURCHAN_API_FOOTER = FOURCHAN_BOARDS_FOOTER + '.json'
FOURCHAN_IMAGES_FOOTER = '/%s/%s'
FOURCHAN_THUMBS_FOOTER = '/%s/%s'

# download urls
FOURCHAN_BOARDS_URL = FOURCHAN_BOARDS + FOURCHAN_BOARDS_FOOTER
FOURCHAN_API_URL = FOURCHAN_API + FOURCHAN_API_FOOTER
FOURCHAN_IMAGES_URL = FOURCHAN_IMAGES + FOURCHAN_IMAGES_FOOTER
FOURCHAN_THUMBS_URL = FOURCHAN_THUMBS + FOURCHAN_THUMBS_FOOTER

# html parsing regex
HTTP_HEADER_UNIV = r"https?://"  # works for both http and https links
FOURCHAN_IMAGES_REGEX = r"/\w+/([0-9]+\.[a-zA-Z0-9]+)"
FOURCHAN_THUMBS_REGEX = r"/\w+/([0-9]+s\.[a-zA-Z0-9]+)"
FOURCHAN_CSS_REGEX = r"/css/([\w\.\d]+.css)"
FOURCHAN_JS_REGEX = r"/js/([\w\.\d]+.js)"
CHILDREGEX = re.compile(r"""href="/([0-9a-zA-Z]+)/(?:res|thread)/([0-9]+)""")

# regex links to 4chan servers
FOURCHAN_IMAGES_URL_REGEX = re.compile(HTTP_HEADER_UNIV + FOURCHAN_IMAGES + FOURCHAN_IMAGES_REGEX)
FOURCHAN_THUMBS_URL_REGEX = re.compile(HTTP_HEADER_UNIV + FOURCHAN_THUMBS + FOURCHAN_THUMBS_REGEX)
FOURCHAN_CSS_URL_REGEX = re.compile(HTTP_HEADER_UNIV + FOURCHAN_STATIC + '/css/')
FOURCHAN_JS_URL_REGEX = re.compile(HTTP_HEADER_UNIV + FOURCHAN_STATIC + '/js/')

# default folder and file names
_DEFAULT_FOLDER = '4chan'
_IMAGE_DIR_NAME = 'images'
_THUMB_DIR_NAME = 'thumbs'
_CSS_DIR_NAME = 'css'
_JS_DIR_NAME = 'js'
EXT_LINKS_FILENAME = 'external_links.txt'

# The Ultimate URL Regex
# http://stackoverflow.com/questions/520031/whats-the-cleanest-way-to-extract-urls-from-a-string-using-python
URLREGEX = re.compile(r"""((?:[a-z][\w-]+:(?:/{1,3}|[a-z0-9%])|www\d{0,3}[.]|[a-z0-9.\-]+[.‌​][a-z]{2,4}/)(?:[^\s()<>]+|(([^\s()<>]+|(([^\s()<>]+)))*))+(?:(([^\s()<>]+|(‌​([^\s()<>]+)))*)|[^\s`!()[]{};:'".,<>?«»“”‘’]))""", re.DOTALL)

HTTP_HEADER = "https://"
API_HEADER = "/_/api/chan/"
API_TYPE = "post/"
API_QUERY = "?board=%s&num=%s"
BACKLINK_REGEX = r"""(<a *.*class="backlink"*.>*).*?(<\/a>)"""

class FuukaSiteArchiver(BaseSiteArchiver):
    name = 'fuuka'

    def __init__(self, callback_handler, options):
        BaseSiteArchiver.__init__(self, callback_handler, options)

        self.boards_lock = threading.Lock()
        self.boards = {}
        self.url_info = ""
        
    def url_valid(self, url):
        """Return true if the given URL is for my site."""
        if "4chan" in url: return False
        if not url: return False
        self.url_info = self._url_parse(url)
        return len(self.url_info) == 3 and self.url_info[2].isdigit()

    def _url_info(self, url):
        """INTERNAL: Takes a url, returns board name, thread info."""
        if self.url_valid(url):
            return self.url_info
        else:
            return [None, None, None]
        
    def _url_parse(self, url):
        """INTERNAL: URL parsing."""
        url = url.rstrip('/')
        http_header = ('https://' if self.options.use_ssl else 'http://')
        if "http" not in url:
            url = http_header + url
        url.replace("www.","")
        up = urlparse(url)
        #url_info = list(filter(lambda x: x != '' and x !="thread", up.path.split('/')))
        #api_call = HTTP_HEADER + up.netloc + API_HEADER + API_TYPE + API_QUERY % (url_info[0], url_info[1])
        return [up.netloc] + list(filter(lambda x: x != '' and x !="thread", up.path.split('/')))

    def add_thread(self, url):
        """Try to add the given thread to our internal list."""
        domain_name, board_name, thread_id = self._url_info(url)
        thread_id = int(thread_id)
        return self._add_thread_from_info(board_name, domain_name, thread_id)

    def _add_thread_from_info(self, board_name, domain_name, thread_id):
        """Add a thread to our internal list from direct board name/thread id."""
        # already exists
        with self.threads_lock:
            if thread_id in self.threads:
                return False

        # running board object
        with self.boards_lock:
            if board_name not in self.boards:
                self.boards[board_name] = pyfuuka.Board(board_name, domain_name,
                                                             https=self.options.use_ssl)
            running_board = self.boards[board_name]

            if not running_board.thread_exists(thread_id):
                print(THREAD_NONEXISTENT.format(**{
                    'site': self.name,
                    'board': board_name,
                    'thread_id': thread_id,
                }))
                print(THREAD_NONEXISTENT_REASON)
                return False

        # add thread to download list
        with self.threads_lock:
            self.threads[thread_id] = {
                'board': board_name,
                'dir': self.base_thread_dir.format(board=board_name, thread=thread_id),
                'thread_id': thread_id,
                'total_files': 0,
                'images_downloaded': 0,
                'thumbs_downloaded': 0,
                'alive': True,
            }
            status_info = self.threads[thread_id]
        self.update_status('new_thread', info=status_info)

        self.add_to_dl('thread', board=board_name, thread_id=thread_id)
        return True

    def download_item(self, item):
        """Download the given item."""
        http_header = ('https://' if self.options.use_ssl else 'http://')
        imgs = ['gif','png','jpg','jpeg','webm']
        
        # images
        if item.dl_type == 'image':
            if self.options.thumbs_only:
                return True
            
            
            # File url from API
            # Needs fuuka media link
            # fileurl post url
            # filename post filename
            
            board_name = item.info['board']
            thread_id = item.info['thread_id']
            images_dir = self.base_images_dir.format(board=board_name, thread=thread_id)
            filename = item.info['filename']
            file_url = item.info['fileurl'] # http_header + FOURCHAN_IMAGES_URL % (board_name, filename)
            file_path = os.path.join(images_dir, filename)

            if not os.path.exists(file_path):
                utils.mkdirs(images_dir)
                if utils.download_file(file_path, file_url):
                    with self.threads_lock:
                        self.threads[thread_id]['images_downloaded'] += 1
                        status_info = self.threads[thread_id]
                        status_info['filename'] = filename
                    self.update_status('image_dl', info=status_info)
                    if not self.options.silent:
                        print(IMAGE_DL.format(**{
                            'site': self.name,
                            'board': board_name,
                            'thread_id': thread_id,
                            'filename': filename,
                            'timestamp': utils.timestamp(),
                        }))

        # thumbnails
        elif item.dl_type == 'thumb':
            if self.options.skip_thumbs:
                return True

            board_name = item.info['board']
            thread_id = item.info['thread_id']
            thumbs_dir = self.base_thumbs_dir.format(board=board_name, thread=thread_id)
            filename = item.info['filename']

            file_url = item.info['fileurl'] # http_header + FOURCHAN_THUMBS_URL % (board_name, filename)
            file_path = os.path.join(thumbs_dir, filename)

            if not os.path.exists(file_path):
                utils.mkdirs(thumbs_dir)
                if utils.download_file(file_path, file_url):
                    with self.threads_lock:
                        self.threads[thread_id]['thumbs_downloaded'] += 1
                        status_info = self.threads[thread_id]
                        status_info['filename'] = filename
                    self.update_status('thumb_dl', info=status_info)
                    if not self.options.silent:
                        print(THUMB_DL.format(**{
                            'site': self.name,
                            'board': board_name,
                            'thread_id': thread_id,
                            'filename': filename,
                            'timestamp': utils.timestamp(),
                        }))

        # thread
        elif item.dl_type == 'thread':
            board_name = item.info['board']
            thread_id = item.info['thread_id']
            thread_dir = self.base_thread_dir.format(board=board_name, thread=thread_id)

            with self.threads_lock:
                status_info = self.threads[thread_id]
            self.update_status('thread_start_download', info=status_info)

            thread = self.threads[thread_id]
            with self.boards_lock:
                # skip if no new posts
                if 'thread' in thread:
                    new_replies = thread['thread'].update()
                    if thread['thread'].archived:
                        # thread got archived
                        print(THREAD_ARCHIVED.format(**{
                            'site': self.name,
                            'board': board_name,
                            'thread_id': thread_id,
                        }))
                        with self.threads_lock:
                            status_info = self.threads[thread_id]
                        self.update_status('archived', info=status_info)
                        self.threads[thread_id]['alive'] = False
                        return True
                    elif new_replies < 1:
                        # skip if no new posts
                        item.delay_dl_timestamp()

                        with self.threads_lock:
                            status_info = self.threads[thread_id]
                        status_info['next_dl'] = item.next_dl_timestamp
                        self.update_status('thread_dl', info=status_info)

                        self.add_to_dl(item=item)
                        return True
                    elif thread['thread'].is_404:
                        # thread 404'd
                        print(THREAD_404.format(**{
                            'site': self.name,
                            'board': board_name,
                            'thread_id': thread_id,
                            'timestamp': utils.timestamp(),
                        }))
                        with self.threads_lock:
                            status_info = self.threads[thread_id]
                        self.update_status('404', info=status_info)
                        self.threads[thread_id]['alive'] = False
                        return True
                    else:
                        with self.threads_lock:
                            # TODO: extend BASC-py4chan to give us this number directly
                            self.threads[thread_id]['total_files'] = len(list(thread['thread'].filenames()))
                else:
                    running_board = self.boards[board_name]
                    running_thread = running_board.get_thread(thread_id)
                    self.threads[thread_id]['thread'] = running_thread
                    thread['thread'] = running_thread
                    new_replies = len(running_thread.all_posts)
                    with self.threads_lock:
                        # TODO: extend BASC-py4chan to give us this number directly
                        self.threads[thread_id]['total_files'] = len(list(running_thread.filenames()))
                    if thread['thread'].archived:
                        # thread got archived
                        print(THREAD_ARCHIVED.format(**{
                            'site': self.name,
                            'board': board_name,
                            'thread_id': thread_id,
                            'timestamp': utils.timestamp(),
                        }))
                        with self.threads_lock:
                            status_info = self.threads[thread_id]
                        self.update_status('archived', info=status_info)
                        self.threads[thread_id]['alive'] = False

            # thread
            if not self.options.silent:
                print(THREAD_NEW_REPLIES.format(**{
                    'site': self.name,
                    'board': board_name,
                    'thread_id': thread_id,
                    'replies': new_replies,
                    'timestamp': utils.timestamp(),
                }))

            utils.mkdirs(thread_dir)

            # record external urls and follow child threads
            external_urls_filename = os.path.join(thread_dir, EXT_LINKS_FILENAME)
            with codecs.open(external_urls_filename, 'w', encoding='utf-8') as external_urls_file:
                # all posts, including topic
                all_posts = [thread['thread'].topic] + thread['thread'].posts
                for reply in all_posts:
                    rep = reply.html_comment
                    if rep is None:
                        continue

                    #a = REG.findall(rep)
                    #regx = ''.join(str(v) for v in a)
                    # 4chan puts <wbr> in middle of urls for word break, remove them
                    cleaned_comment = re.sub(r'\<wbr\>', '', rep)
                    cleaned_comment = re.sub(BACKLINK_REGEX, '', cleaned_comment)

                    # child threads
                    if self.options.follow_child_threads:
                        for child_board, child_id in CHILDREGEX.findall(cleaned_comment):
                            is_same_board = child_board == board_name
                            child_id = int(child_id)

                            if child_id not in self.threads:
                                if self.options.follow_to_other_boards or is_same_board:
                                    if self._add_thread_from_info(child_board, thread['thread'].domain, child_id):
                                        print(THREAD_CHILD_FOUND.format(**{
                                            'site': self.name,
                                            'board': child_board,
                                            'thread_id': child_id,
                                            'timestamp': utils.timestamp(),
                                        }))

                    # external urls
                    #if not URLREGEX.findall(reply.comment):
                    #    continue

                    for found in URLREGEX.findall(cleaned_comment):
                        for url in found:
                            if url:
                                external_urls_file.write('{}\n'.format(url))

            # dump fuuka json file, pretty printed
            local_filename = os.path.join(thread_dir, '{}.json'.format(thread_id))
            with open(local_filename, 'w', encoding="utf-8") as json_file:
                Json.dump(thread['thread'].json, json_file, sort_keys=True, indent=4) # Reuse json gotten from beginning
            #url = http_header + FOURCHAN_API_URL % (board_name, thread_id)
            #utils.download_json(local_filename, url, clobber=True)

            # and output thread html file
            domain = thread['thread'].domain
            local_filename = os.path.join(thread_dir, '{}.html'.format(thread_id))
            url = http_header + domain +  FOURCHAN_BOARDS_FOOTER % (board_name, thread_id)
            #fuuka_css = """.*link.*href=["|\']?(.*[\\\|\/]?.*)\.css["|\']?.*"""
            #fuuka_remove_comment = """(<!--[\s\S]*?-->)"""
            downloaded_html = False
            
            if utils.download_file(local_filename, url, clobber=True):
                
                contents = codecs.open(local_filename, encoding='utf-8').read()
                soup = BeautifulSoup(contents, features="html.parser")
                downloaded_html = True
                
                # get css files
                if not self.options.skip_css:
                    css_dir = os.path.join(thread_dir, _CSS_DIR_NAME)
                    utils.mkdirs(css_dir)
                    
                    for tag in soup.find_all('link', rel="stylesheet", href=True):
                        url = tag['href']
                        css_filename = os.path.basename(url)
                        local_css_filename = os.path.join(_CSS_DIR_NAME, css_filename)
                        utils.download_file(os.path.join(css_dir,css_filename), url)
                        tag['href'] = local_css_filename # Applies CSS changes to html
                        #print(local_css_filename)
                        
                    #css_regex = re.compile(FOURCHAN_CSS_REGEX)
                    #found_css_files = css_regex.findall(codecs.open(local_filename, encoding='utf-8').read())
                    #for css_filename in found_css_files:
                    #    local_css_filename = os.path.join(css_dir, css_filename)
                    #    url = http_header + FOURCHAN_STATIC + '/css/' + css_filename
                    #    utils.download_file(local_css_filename, url)

                # get js files
                if not self.options.skip_js:
                    js_dir = os.path.join(thread_dir, _JS_DIR_NAME)
                    utils.mkdirs(js_dir)
                    
                    for tag in soup.find_all('script'):
                        url = tag.get('src')
                        if url and (domain in url or "ajax" in url):
                            while '/' in url[0]:
                                url = tag.get('src').lstrip('/')
                            if "http" not in url :
                                if "ajax" not in url:
                                    url = http_header + domain + "/" + url
                                else:
                                    url = http_header +  url
                            js_filename = os.path.basename(url)
                            local_js_filename = os.path.join(_JS_DIR_NAME, js_filename)
                            utils.download_file(os.path.join(js_dir,js_filename), url) # js_filename[:js_filename.index('.js')+len('.js')] Remove JS api queries attached to filename
                            tag['src'] = local_js_filename # Applies JS changes to html
                            #print(local_js_filename)

                    #js_regex = re.compile(FOURCHAN_JS_REGEX)
                    #found_js_files = js_regex.findall(codecs.open(local_filename, encoding='utf-8').read())
                    #for js_filename in found_js_files:
                    #    local_js_filename = os.path.join(js_dir, js_filename)
                    #    url = http_header + FOURCHAN_STATIC + '/js/' + js_filename
                    #    utils.download_file(local_js_filename, url)

                # convert links to local links
                #utils.file_replace(local_filename, '"//', '"' + http_header)
                #utils.file_replace(local_filename, FOURCHAN_IMAGES_URL_REGEX, _IMAGE_DIR_NAME + r'/\1')
                #utils.file_replace(local_filename, FOURCHAN_THUMBS_URL_REGEX, _THUMB_DIR_NAME + r'/\1')
                #utils.file_replace(local_filename, FOURCHAN_CSS_URL_REGEX, _CSS_DIR_NAME + '/')
                #utils.file_replace(local_filename, FOURCHAN_JS_URL_REGEX, _JS_DIR_NAME + '/')

            # add images to dl queue
            for file in thread['thread'].file_objects():
                self.add_to_dl(dl_type='image', board=board_name, thread_id=thread_id, filename=os.path.basename(file.file_url), fileurl = file.file_url)
                for tag in soup.find_all('a',  href=True):
                    url = tag['href']
                    if any(img in url for img in imgs):
                        if "thumb" in url:
                            tag['href'] = os.path.join(_THUMB_DIR_NAME, os.path.basename(url))
                        else:
                            tag['href'] = os.path.join(_IMAGE_DIR_NAME, os.path.basename(url))
        
            # add thumbs to dl queue
            for file in thread['thread'].file_objects():
                self.add_to_dl(dl_type='thumb', board=board_name, thread_id=thread_id, filename=os.path.basename(file.thumbnail_url), fileurl = file.thumbnail_url)
                for tag in soup.findAll('img'):
                    url = tag.get('src')
                    if "http" in url:
                        tag['src'] = os.path.join(_THUMB_DIR_NAME, os.path.basename(url))
        
            # queue for next dl if thread is still alive
            if thread['alive'] and not self.options.run_once:
                item.delay_dl_timestamp(self.options.thread_check_delay)
                self.add_to_dl(item=item)
            
            # convert links to local links
            if downloaded_html and soup:
                print("Found index.html. Converting links to local links...")
                for link in soup.find_all('a',  href=True):
                    url = link['href']
                    if url and url != "#" and "#" in url:
                        link['href'] = os.path.basename(url)
                with open(local_filename, "w", encoding='utf-8') as file:
                    file.write(str(soup))
            else:
                print("index.html could not be opened!")

            with self.threads_lock:
                if self.options.run_once:
                    self.threads[thread_id]['alive'] = False
            status_info = self.threads[thread_id]
            status_info['next_dl'] = None if self.options.run_once else item.next_dl_timestamp
            self.update_status('thread_dl', info=status_info)
            

    #def download_threads(self):
    #    """Download all the threads we currently hold."""
    #    pass

    #def _download_thread(self, thread_info):
    #    """Download the given thread, from the thread info."""
    #    pass
