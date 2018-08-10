import ctypes
import os
from multiprocessing import Process, Manager, Value

import telegram
from telegram.ext import CommandHandler
from telegram.ext.dispatcher import run_async
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from lru import LRU
from GelbooruViewer import GelbooruPicture, GelbooruViewer
from random import randint, seed
from collections import defaultdict
import pickle
import atexit
import signal
import sys
import re
import logging
from threading import Lock
from io import BytesIO
from time import time, sleep
from requests import get
from concurrent.futures import ThreadPoolExecutor

from calc import calc
from recycle_cache import RecycleCache
from videos_fetcher import get_info, download
import redis_dao

# Constants
PICTURE_INFO_TEXT = """
id: {picture_id}
size: {width}*{height}
rating: {rating}
Original url: {file_url}
view page:{view_url}
"""
PIC_FORMAT_HTML = """
<a href="https://gelbooru.com/index.php?page=post&s=view&id={picture_id}">{picture_id}</a>
<a>size: {width} * {height}</a>
<a href="{file_url}">original</a>
<a href="{source}">source</a>
<strong>rating:{rating}</strong>
"""

file_path = os.path.dirname(__file__)
PIC_CHAT_DIC_FILE_NAME = 'picture_chat_id.dic'
RECENT_ID_FILE_NAME = 'recent_id_cache.pickle'
PIC_CACHE_FILE_NAME = 'picture_cache.pickle'
SHORT_URL_ADDR = "examples.com:1234" # Todo change this to your short url server addr
SAFE_TAG = "rating:safe"
REDIS_PORT = 12710
REDIS_LRU_PORT = 12711
COMMAND_HANDLERS = [] # list of command_handlers

# global variables
recent_cache_size = 6
picture_chat_id_dic = redis_dao.RedisSetDict(port=REDIS_PORT)
picture_chat_id_dic[0].ping() # start redis server if not started
gelbooru_viewer = GelbooruViewer()
send_lock = Lock()
recent_picture_id_caches = defaultdict(lambda: RecycleCache(recent_cache_size))
gelbooru_viewer.cache = LRU(gelbooru_viewer.MAX_CACHE_SIZE)


def load_data():
    """
    load previous global data
    :return: None
    """
    global recent_picture_id_caches

    try:
        with open(file_path + '/' + RECENT_ID_FILE_NAME, 'rb') as fp:
            caches_dict = pickle.load(fp)
            # recent_id_caches contain a lambda function which can not be pickled
            for k in caches_dict:
                for v in caches_dict[k][::-1]:
                    recent_picture_id_caches[k].add(v)

    except FileNotFoundError:
        pass

    # try:
    #     with open(file_path + '/' + PIC_CACHE_FILE_NAME, 'rb') as fp:
    #         gelbooru_viewer.cache = pickle.load(fp)
    # except FileNotFoundError:
    #     pass


# start up operation
load_data()
seed(time())


@atexit.register
def save_data():
    # with open(file_path + '/' + PIC_CHAT_DIC_FILE_NAME, 'wb') as fp:
    #     pickle.dump(picture_chat_id_dic, fp, protocol=2)

    with open(file_path + '/' + RECENT_ID_FILE_NAME, 'wb') as fp:
        # recent_id_caches contain a lambda function which can not be pickled
        cache_dict = {k: [*recent_picture_id_caches[k]] for k in recent_picture_id_caches}
        pickle.dump(cache_dict, fp, protocol=2)

    # with open(file_path + '/' + PIC_CACHE_FILE_NAME, 'wb') as fp:
    #     pickle.dump(gelbooru_viewer.cache, fp, protocol=2)


def raise_exit(signum, stack):
    sys.exit(-1)


signal.signal(signal.SIGTERM, raise_exit)


def is_public_chat(update: telegram.Update):
    if isinstance(update.message.chat, telegram.Chat):
        chat = update.message.chat
        return chat.type != telegram.Chat.PRIVATE
    else:
        print(update.message.chat)
        return True


def url2short(url: str):
    """
    use custom short url service to shorten url.If not success, url will not be modified

    :param url: url to shorten

    :return: short_url
    """
    if url:
        try:
            req = get(
                "http://{}/shorten/".format(SHORT_URL_ADDR),
                params={
                    "url": url
                }
            )
            # logging.info("url2short request status code", req.status_code)
            # logging.info("url2short request content", req.content)
            if req.status_code >= 400:
                return url
            else:
                short_url = req.text
                return short_url
        except Exception as e:
            print(type(e), e)
    return url


def get_img(url: str):
    """
    get image io object of url
    :param url: url of image
    :return:
    """
    file_name = url.split('/')[-1]
    response = get(
        url,
        headers= {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US',
            'User-Agent': 'Mozilla/5.0 GelbooruViewer/1.0 (+https://github.com/ArchieMeng/GelbooruViewer)'
        }
    )
    if response.status_code == 200 or response.status_code == 304:
        img_io = BytesIO(response.content)
        img_io.name = file_name
        return img_io
    else:
        return None


def send_picture(
        bot: telegram.bot.Bot,
        chat_id,
        message_id,
        p: GelbooruPicture,
        use_short_url=True
):
    """
    Used to send Gelbooru picture

    :param bot: Telegrambot object

    :param chat_id: id of chat channel

    :param message_id: id of incoming message

    :param p: Gelbooru picture object

    :param use_short_url: Whether using short url for images. Default True.

    :return: None
    """
    def get_correct_url(url: str):
        if url:
            try:
                return re.findall(r'((http|https)://.*)', url)[0][0]
            except Exception as e:
                logging.error(e)
                logging.error("wrong url", url)
                return url
        else:
            return url
    # use regular expression in case of wrong url format
    url = get_correct_url(p.sample_url)

    # logging.info("id: {pic_id} - file_url: {file_url}".format(
    #     pic_id=p.picture_id,
    #     file_url=url
    # ))

    if use_short_url:
        with ThreadPoolExecutor(max_workers=5) as executor:
            view_url = executor.submit(
                url2short,
                'https://gelbooru.com/index.php?page=post&s=view&id=' + str(p.picture_id)
            )
            source_url = executor.submit(url2short, get_correct_url(p.source))
            file_url = executor.submit(url2short, get_correct_url(p.file_url))
            source_url = source_url.result()
            file_url = file_url.result()
            view_url = view_url.result()
    else:
        source_url, \
        file_url, \
        view_url = \
            p.source, \
            p.file_url, \
            'https://gelbooru.com/index.php?page=post&s=view&id=' + str(p.picture_id)

    recent_picture_id_caches[chat_id].add(p.picture_id)
    bot.send_photo(
        chat_id=chat_id,
        reply_to_message_id=message_id,
        photo=url,
        caption=PICTURE_INFO_TEXT.format(
            rating=p.rating,
            picture_id=p.picture_id,
            view_url=view_url,
            width=p.width,
            height=p.height,
            file_url=file_url,
        ),
        reply_markup=ReplyKeyboardRemove()
    )


def set_command_handler(
        command,
        filters=None,
        allow_edited=False,
        pass_args=False,
        pass_update_queue=False,
        pass_job_queue=False,
        pass_user_data=False,
        pass_chat_data=False
):
    def decorate(func):
        COMMAND_HANDLERS.append(
            CommandHandler(
                command=command,
                callback=func,
                filters=filters,
                allow_edited=allow_edited,
                pass_args=pass_args,
                pass_update_queue=pass_update_queue,
                pass_job_queue=pass_job_queue,
                pass_user_data=pass_user_data,
                pass_chat_data=pass_chat_data
            )
        )
        return func
    return decorate


def send_tags_info(bot: telegram.bot.Bot, update: telegram.Update, pic_id):
    message_id = update.message.message_id
    chat_id = update.message.chat_id

    bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.TYPING)
    picture = gelbooru_viewer.get(id=pic_id)

    if is_public_chat(update):
        fetch_method = '/img'
    else:
        fetch_method = '/taxi'

    if picture:
        col = 3
        picture = picture[0]
        buttons = [KeyboardButton("{} {}".format(fetch_method, tag)) for tag in picture.tags]
        reply_markup = ReplyKeyboardMarkup(
            [buttons[i:i + col] for i in range(0, len(buttons), col)],
            one_time_keyboard=True,
            resize_keyboard=True
        )
        bot.send_message(
            chat_id=chat_id,
            reply_to_message_id=message_id,
            text=", ".join(picture.tags),
            reply_markup=reply_markup
        )
    else:
        bot.send_message(
            chat_id=chat_id,
            reply_to_message_id=message_id,
            text="id: {pic_id} not found".format(pic_id=pic_id)
        )


@set_command_handler('start')
@run_async
def hello(bot, update):
    bot.send_message(
        chat_id=update.message.chat_id,
        text="""
My name is Altair, ArchieMeng's partner.
Using api from Gelbooru.
Tips: send images with caption set to "tags" to get predicted tags
My core is shared on https://github.com/ArchieMeng/archie_partner_bot
        """
    )


def send_gelbooru_images(bot: telegram.bot.Bot, update: telegram.Update, args, safe_mode=False):
    """
    implement send gelbooru images with args to Telegram chat
    :param bot: telegram.bot.Bot
    :param update: telegram.Update
    :param args: args passed by Telegram Chat
    :return:
    """
    chat_id = update.message.chat_id
    message_id = update.message.message_id

    if args:
        # fetch picture_id = args[0] of it is digits
        if args[0].isdigit():
            bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.UPLOAD_PHOTO)
            picture = gelbooru_viewer.get(id=args[0])
            if picture:
                picture = picture[0]
                picture_chat_id_dic[chat_id].add(picture.picture_id)
                send_picture(bot, chat_id, message_id, picture)
            else:
                bot.send_message(
                    chat_id=chat_id,
                    reply_to_message_id=message_id,
                    text="id: {picture_id} not found".format(picture_id=args[0])
                )
            return
        # fetch picture_tags = args
        else:
            bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.UPLOAD_PHOTO)
            pictures = gelbooru_viewer.get_all(tags=args, num=200, limit=10, thread_limit=1)
            if pictures:
                for pic in pictures:
                    if picture_chat_id_dic[chat_id].add(pic.picture_id) == 1:
                        if safe_mode and pic.rating != 's':
                            continue
                        send_picture(bot, chat_id, message_id, pic)
                        break
                else:
                    bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.UPLOAD_PHOTO)
                    # get picture from redis server
                    pic_id = picture_chat_id_dic[chat_id].pop()
                    # get safe picture if safe_mode is True
                    while pic_id:
                        picture = gelbooru_viewer.get(id=pic_id)[0]
                        if not safe_mode or picture.rating == 's':
                            picture_chat_id_dic[chat_id].add(pic_id)
                            send_picture(bot, chat_id, message_id, picture)
                            break
                        pic_id = picture_chat_id_dic[chat_id].pop()
                    picture_chat_id_dic[chat_id].clear()
                    if pic_id:
                        picture_chat_id_dic[chat_id].add(pic_id)
                    else:
                        # all image is NSFW
                        bot.send_message(
                            chat_id=chat_id,
                            reply_to_message_id=message_id,
                            text="No image with these tags is SFW"
                        )

            else:
                bot.send_message(
                    chat_id=chat_id,
                    reply_to_message_id=message_id,
                    text="Tag: {tags} not found".format(tags=args)
                )
    else:
        # send random picture
        bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.UPLOAD_PHOTO)
        # fetch latest picture
        picture = gelbooru_viewer.get(limit=1)
        while picture and picture_chat_id_dic[chat_id].add(picture[0].picture_id) == 0:
            # get a not viewed picture id by offline method
            while True:
                pic_id = randint(1, GelbooruViewer.MAX_ID)
                if picture_chat_id_dic[chat_id].add(pic_id) == 1:
                    break

            picture = gelbooru_viewer.get(id=pic_id)
            if picture:
                # picture found, then stop loop
                break

        picture = picture[0]
        bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.UPLOAD_PHOTO)
        send_picture(bot, chat_id, message_id, picture)


@set_command_handler('img', pass_args=True)
@run_async
def send_safe_gelbooru_images(bot: telegram.bot.Bot, update: telegram.Update, args):
    chat_id = update.message.chat_id
    message_id = update.message.message_id

    bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.TYPING)
    # Todo correctly implement cache routine
    if args and args[0].isdigit():
        bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.UPLOAD_PHOTO)
        picture = gelbooru_viewer.get(id=args[0])
        if picture:
            picture = picture[0]
            if picture.rating == 'e':
                bot.send_message(
                    chat_id=chat_id,
                    reply_to_message_id=message_id,
                    text="id: {picture_id} is NSFW".format(picture_id=args[0])
                )
            else:
                picture_chat_id_dic[chat_id].add(picture.picture_id)
                send_picture(bot, chat_id, message_id, picture)
        else:
            bot.send_message(
                chat_id=chat_id,
                reply_to_message_id=message_id,
                text="id: {picture_id} not found".format(picture_id=args[0])
            )
        return
    else:
        send_gelbooru_images(bot, update, args, safe_mode=True)


@set_command_handler('taxi', pass_args=True)
@run_async
def send_taxi_images(bot: telegram.bot.Bot, update: telegram.Update, args):
    chat_id = update.message.chat_id
    message_id = update.message.message_id

    bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.TYPING)
    if is_public_chat(update):
        bot.send_message(
            chat_id=chat_id,
            reply_to_message_id=message_id,
            text="Only available in private chat."
        )
        return

    send_gelbooru_images(bot, update, args)


@set_command_handler('tag', pass_args=True)
@run_async
def tag_id(bot: telegram.Bot, update: telegram.Update, args):
    chat_id = update.message.chat_id
    message_id = update.message.message_id

    bot.send_chat_action(
        chat_id=chat_id,
        action=telegram.ChatAction.TYPING
    )
    if args and args[0].isdigit():
        pic_id = args[0]
        send_tags_info(bot, update, pic_id)
    else:
        buttons = [KeyboardButton("id:" + str(pic_id)) for pic_id in recent_picture_id_caches[chat_id]]
        reply_markups = ReplyKeyboardMarkup(
            [buttons[i:i+3] for i in range(0, len(buttons), 3)],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        bot.send_message(
            chat_id=chat_id,
            reply_to_message_id=message_id,
            text="/tag <id> to get tags of picture which has id.\nOr select recently viewed pictures' id below",
            reply_markup=reply_markups
        )


@set_command_handler('you-get', pass_args=True)
def you_get_download(bot: telegram.Bot, update: telegram.Update, args):
    # Todo support concurrent programming
    chat_id = update.message.chat_id
    message_id = update.message.message_id

    if args:
        url = args[0]
        bot.send_chat_action(
            chat_id=chat_id,
            action=telegram.ChatAction.UPLOAD_DOCUMENT
        )

        try:
            info = download(url)
            name, ext = info['title'], info['ext']
        except OSError as e:
            # handle filename too long
            if str(e.strerror) == "File name too long":
                name = "videos"
                info = get_info(url)
                ext = info['ext']
                download(url, output_filename=name)
            else:
                # remove downloaded file
                for file in os.listdir('.'):
                    if file.endswith("download"):
                        os.remove(file)
                raise e

        file_name = name + '.' + ext
        file_name = os.path.join(file_path, file_name)
        bot.send_chat_action(
            chat_id=chat_id,
            action=telegram.ChatAction.UPLOAD_DOCUMENT
        )

        with open(file_name, 'rb') as fp:
            bot.send_document(
                chat_id=chat_id,
                reply_to_message_id=message_id,
                document=fp,
            )
        os.remove(file_name)
    else:
        bot.send_message(
            chat_id=chat_id,
            reply_to_message_id=message_id,
            text="You need to provide an url to download!"
        )


def calculate_impl(formula, result: Value):
    try:
        result.value = str(calc(formula))
    except Exception as e:
        result.value = e.args[0]


@set_command_handler('calc', pass_args=True, allow_edited=True)
@run_async
def calculate(bot: telegram.Bot, update: telegram.Update, args):

    def send_message(text):
        message = update.message or update.edited_message
        chat_id = message.chat_id
        message_id = message.message_id
        if update.message:
            bot.send_message(
                chat_id=chat_id,
                reply_to_message_id=message_id,
                text=text
            )
        else:
            # on edited received
            message.reply_text(text)

    calc_timeout = 1.
    if args:
        formula = ''.join(args)

        with Manager() as manager:
            result = manager.Value('s', " ")
            process = Process(target=calculate_impl, args=(formula, result))
            process.start()
            process.join(calc_timeout)
            if process.is_alive():
                process.terminate()
                send_message("Time Limit Exceeded")
            else:
                send_message(result.value)
    else:
        send_message("Usage: /calc <formula>. Currently, +-*/()^ operator is supported")