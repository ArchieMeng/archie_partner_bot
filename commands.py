import telegram
from telegram.ext import CommandHandler
from telegram.ext.dispatcher import run_async
from GelbooruViewer import GelbooruPicture, GelbooruViewer
from random import randint
from collections import defaultdict
import pickle
import atexit
import signal
import sys
import logging
from threading import Lock

PICTURE_INFO_TEXT = """
id: {picture_id}
size: {width}*{height}
source: {source}
Original url: {file_url}
rating: {rating}
"""
PIC_CHAT_DIC_FILE_NAME = 'picture_chat_id.dic'
pic_chat_dic_lock = Lock()


gelbooru_viewer = GelbooruViewer()

try:
    with open(PIC_CHAT_DIC_FILE_NAME, 'rb') as fp:
        picture_chat_id_dic = pickle.load(fp)
except FileNotFoundError:
    picture_chat_id_dic = defaultdict(set)


@atexit.register
def save_pic_chat_dic():
    with open(PIC_CHAT_DIC_FILE_NAME, 'wb') as fp:
        pickle.dump(picture_chat_id_dic, fp, protocol=2)


def raise_exit(signum, stack):
    sys.exit(-1)
signal.signal(signal.SIGTERM, raise_exit)


@run_async
def hello(bot, update):
    bot.send_message(
        chat_id=update.message.chat_id,
        text="""
        My name is Altair, ArchieMeng's partner.
        My core is shared on https://github.com/ArchieMeng/archie_partner_bot
        """
    )


@run_async
def send_gelbooru_images(bot: telegram.bot.Bot, update: telegram.Update, args):
    chat_id = update.message.chat_id
    message_id = update.message.message_id

    bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.TYPING)

    # internal function to send picture to chat
    def send_picture(p: GelbooruPicture):
        url = p.preview_url
        logging.info("id: {pic_id} - file_url: {file_url}".format(
            pic_id=p.picture_id,
            file_url=url
        ))
        bot.send_photo(
            chat_id=chat_id,
            reply_to_message_id=message_id,
            photo=url
        )

    # internal function to send info of picture to chat
    def send_picture_info(p: GelbooruPicture):
        bot.send_message(
            chat_id=chat_id,
            text=PICTURE_INFO_TEXT.format(
                picture_id=p.picture_id,
                width=p.width,
                height=p.height,
                source=p.source,
                file_url=p.file_url,
                rating=p.rating
            ),
            disable_web_page_preview=True
        )

    if args:
        # fetch picture_id = args[0] of it is digits
        if args[0].isdigit():
            bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.UPLOAD_PHOTO)
            picture = gelbooru_viewer.get(id=args[0])
            if picture:
                picture = picture[0]
                send_picture(picture)
                send_picture_info(picture)
                with pic_chat_dic_lock:
                    picture_chat_id_dic[chat_id].add(picture.picture_id)
            else:
                bot.send_message(
                    chat_id=chat_id,
                    reply_to_message_id=message_id,
                    text="id: {picture_id} not found".format(picture_id=args[0])
                )
            return

        bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.UPLOAD_PHOTO)
        pictures = gelbooru_viewer.get(tags=args)
        if len(pictures) >= 1:
            for pic in pictures:
                with pic_chat_dic_lock:
                    if pic.picture_id not in picture_chat_id_dic[chat_id]:
                        send_picture(pic)
                        send_picture_info(pic)
                        picture_chat_id_dic[chat_id].add(pic.picture_id)
                        break
            else:
                bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.TYPING)
                with pic_chat_dic_lock:
                    picture_chat_id_dic[chat_id] = {pictures[0].picture_id}
                    send_picture(pictures[0])
                    send_picture_info(pictures[0])
        else:
            bot.send_message(
                chat_id=chat_id,
                reply_to_message_id=message_id,
                text="Tag: {tags} not found".format(tags=args)
            )
    else:
        bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.UPLOAD_PHOTO)
        picture = gelbooru_viewer.get(limit=1)
        with pic_chat_dic_lock:
            viewed = not picture or picture[0].picture_id in picture_chat_id_dic[chat_id]
        while viewed:
            picture = gelbooru_viewer.get(id=randint(1, GelbooruViewer.MAX_ID))
            with pic_chat_dic_lock:
                viewed = not picture or picture[0].picture_id in picture_chat_id_dic[chat_id]
        picture = picture[0]
        with pic_chat_dic_lock:
            picture_chat_id_dic[chat_id].add(picture.picture_id)
        bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.UPLOAD_PHOTO)
        send_picture(picture)
        send_picture_info(picture)


@run_async
def tag_id(bot: telegram.Bot, update: telegram.Update, args):
    chat_id = update.message.chat_id
    message_id = update.message.message_id

    if args and args[0].isdigit():
        pic_id = args[0]
        picture = gelbooru_viewer.get(id=pic_id)
        if picture:
            picture = picture[0]
            bot.send_message(
                chat_id=chat_id,
                reply_to_message_id=message_id,
                text=", ".join(picture.tags)
            )
        else:
            bot.send_message(
                chat_id=chat_id,
                reply_to_message_id=message_id,
                text="id: {pic_id} not found".format(pic_id=pic_id)
            )
    else:
        bot.send_message(
            chat_id=chat_id,
            reply_to_message_id=message_id,
            text="/tag <id> to get tags of picture which has id.\n id must be an int"
        )

start_handler = CommandHandler(
    command='start',
    callback=hello
)

taxi_handler = CommandHandler(
    command='taxi',
    callback=send_gelbooru_images,
    pass_args=True
)

tag_handler = CommandHandler(
    command='tag',
    callback=tag_id,
    pass_args=True
)
COMMAND_HANDLERS = [
    start_handler,
    taxi_handler,
    tag_handler
]
