import os
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
from time import time
from requests import get
from concurrent.futures import ThreadPoolExecutor
from recycle_cache import RecycleCache

# Constants
PICTURE_INFO_TEXT = """
id: {picture_id}
size: {width}*{height}
source: {source}
Original url: {file_url}
rating: {rating}
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
SHORT_URL_ADDR = "localhost:1234"
COMMAND_HANDLERS = [] # list of command_handlers

# global variables
recent_cache_size = 6
pic_chat_dic_lock = Lock()
gelbooru_viewer = GelbooruViewer()
picture_chat_id_dic = defaultdict(set)
send_lock = Lock()
recent_picture_id_caches = defaultdict(lambda: RecycleCache(recent_cache_size))
gelbooru_viewer.cache = LRU(gelbooru_viewer.MAX_CACHE_SIZE)


def load_data():
    """
    load previous global data
    :return: None
    """
    global picture_chat_id_dic
    global recent_picture_id_caches

    try:
        with open(file_path + '/' + PIC_CHAT_DIC_FILE_NAME, 'rb') as fp:
            picture_chat_id_dic = pickle.load(fp)
    except FileNotFoundError:
        pass

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
    with open(file_path + '/' + PIC_CHAT_DIC_FILE_NAME, 'wb') as fp:
        pickle.dump(picture_chat_id_dic, fp, protocol=2)

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
            if req.status_code != 200:
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

    logging.info("id: {pic_id} - file_url: {file_url}".format(
        pic_id=p.picture_id,
        file_url=url
    ))

    # bot.send_message(
    #     chat_id=chat_id,
    #     reply_to_message_id=message_id,
    #     text=PIC_FORMAT_HTML.format(
    #         preview_url=url,
    #         picture_id=p.picture_id,
    #         width=p.width,
    #         height=p.height,
    #         source=p.source,
    #         file_url=p.file_url,
    #         rating=p.rating
    #     ),
    #     parse_mode=telegram.ParseMode.HTML
    # )
    if use_short_url:
        with ThreadPoolExecutor(max_workers=5) as executor:
            view_url = executor.submit(
                url2short,
                get_correct_url('https://gelbooru.com/index.php?page=post&s=view&id=' + str(p.picture_id))
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

    with send_lock:
        recent_picture_id_caches[chat_id].add(p.picture_id)
        bot.send_photo(
            chat_id=chat_id,
            reply_to_message_id=message_id,
            # photo=get_img(url),
            photo=url,
            caption=PICTURE_INFO_TEXT.format(
                picture_id=p.picture_id,
                view_url=view_url,
                width=p.width,
                height=p.height,
                source=source_url,
                file_url=file_url,
                rating=p.rating
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
Deeply thanks to Gelbooru.
My core is shared on https://github.com/ArchieMeng/archie_partner_bot
        """
    )


# Todo add timeout for this command
@set_command_handler('img', pass_args=True)
@run_async
def send_safe_gelbooru_images(bot: telegram.bot.Bot, update: telegram.Update, args):
    chat_id = update.message.chat_id
    message_id = update.message.message_id
    h_rating = {'e', 'q'}

    bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.TYPING)

    if args:
        # fetch picture_id = args[0] if it is digits
        if args[0].isdigit():
            bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.UPLOAD_PHOTO)
            picture = gelbooru_viewer.get(id=args[0])
            if picture:
                picture = picture[0]
                send_picture(bot, chat_id, message_id, picture)
                with pic_chat_dic_lock:
                    picture_chat_id_dic[chat_id].add(picture.picture_id)
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
            pictures = gelbooru_viewer.get_all(tags=args, num=1000, limit=10, thread_limit=2)
            if pictures:
                send = False
                for pic in pictures:
                    with pic_chat_dic_lock:
                        if pic.picture_id not in picture_chat_id_dic[chat_id]:
                            if pic.rating not in h_rating:
                                picture_chat_id_dic[chat_id].add(pic.picture_id)
                                send = True
                    if send:
                        send_picture(bot, chat_id, message_id, pic)
                        return
                else:
                    bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.TYPING)
                    for pic in pictures:
                        if pic.rating not in h_rating:
                            picture_chat_id_dic[chat_id] = {pic.picture_id}
                            send_picture(bot, chat_id, message_id, pic)
                            return
            else:
                bot.send_message(
                    chat_id=chat_id,
                    reply_to_message_id=message_id,
                    text="Tag: {tags} not found".format(tags=args)
                )
    else:
        # send random picture
        bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.UPLOAD_PHOTO)
        picture = gelbooru_viewer.get(limit=1)
        pic_id = GelbooruViewer.MAX_ID
        with pic_chat_dic_lock:
            invalid_or_viewed = not picture\
                                or picture[0].rating in h_rating \
                                or picture[0].picture_id in picture_chat_id_dic[chat_id]
        while invalid_or_viewed:
            # get a not viewed picture id by offline method
            viewed = True
            while viewed:
                pic_id = randint(1, GelbooruViewer.MAX_ID)
                with pic_chat_dic_lock:
                    viewed = pic_id in picture_chat_id_dic[chat_id]
            # add the pic_id into dictionary.
            #  If this section is reached that means pic_id not viewed, so just test validation
            with pic_chat_dic_lock:
                # in case other thread sent this picture before this thread GET it
                if pic_id in picture_chat_id_dic[chat_id]:
                    continue
                else:
                    picture_chat_id_dic[chat_id].add(pic_id)
            picture = gelbooru_viewer.get(id=pic_id)
            # for we have judged viewed before, we can only judge valid here
            invalid_or_viewed = not picture or picture[0].rating in h_rating
            if picture and picture[0].rating in h_rating:
                with pic_chat_dic_lock:
                    picture_chat_id_dic[chat_id].remove(pic_id)
        picture = picture[0]
        with pic_chat_dic_lock:
            picture_chat_id_dic[chat_id].add(picture.picture_id)
        bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.UPLOAD_PHOTO)
        send_picture(bot, chat_id, message_id, picture)


# Todo add timeout for this command
@set_command_handler('taxi', pass_args=True)
@run_async
def send_gelbooru_images(bot: telegram.bot.Bot, update: telegram.Update, args):
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

    if args:
        # fetch picture_id = args[0] if it is digits
        if args[0].isdigit():
            bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.UPLOAD_PHOTO)
            picture = gelbooru_viewer.get(id=args[0])
            if picture:
                picture = picture[0]
                send_picture(bot, chat_id, message_id, picture)
                with pic_chat_dic_lock:
                    picture_chat_id_dic[chat_id].add(picture.picture_id)
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
            pictures = gelbooru_viewer.get_all(tags=args, num=1000, limit=10, thread_limit=1)
            if pictures:
                send = False
                for pic in pictures:
                    with pic_chat_dic_lock:
                        if pic.picture_id not in picture_chat_id_dic[chat_id]:
                            picture_chat_id_dic[chat_id].add(pic.picture_id)
                            send = True
                    if send:
                        send_picture(bot, chat_id, message_id, pic)
                        break
                else:
                    bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.UPLOAD_PHOTO)
                    # fix bug for generator pictures
                    for picture in pictures:
                        with pic_chat_dic_lock:
                            picture_chat_id_dic[chat_id] = {picture.picture_id}
                            send_picture(bot, chat_id, message_id, picture)
                            break
            else:
                bot.send_message(
                    chat_id=chat_id,
                    reply_to_message_id=message_id,
                    text="Tag: {tags} not found".format(tags=args)
                )
    else:
        # send random picture
        bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.UPLOAD_PHOTO)
        picture = gelbooru_viewer.get(limit=1)
        pic_id = GelbooruViewer.MAX_ID
        with pic_chat_dic_lock:
            invalid_or_viewed = not picture or picture[0].picture_id in picture_chat_id_dic[chat_id]
        while invalid_or_viewed:
            # get a not viewed picture id by offline method
            viewed = True
            while viewed:
                pic_id = randint(1, GelbooruViewer.MAX_ID)
                with pic_chat_dic_lock:
                    viewed = pic_id in picture_chat_id_dic[chat_id]
            # add the pic_id into dictionary.
            #  If this section is reached that means pic_id not viewed, so just test validation
            with pic_chat_dic_lock:
                # in case other thread sent this picture before this thread GET it
                if pic_id in picture_chat_id_dic[chat_id]:
                    continue
                else:
                    picture_chat_id_dic[chat_id].add(pic_id)
            picture = gelbooru_viewer.get(id=pic_id)
            invalid_or_viewed = not picture
        picture = picture[0]
        with pic_chat_dic_lock:
            picture_chat_id_dic[chat_id].add(picture.picture_id)
        bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.UPLOAD_PHOTO)
        send_picture(bot, chat_id, message_id, picture)


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

