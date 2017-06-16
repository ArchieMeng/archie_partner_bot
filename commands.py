import telegram
from telegram.ext import CommandHandler
from GelbooruViewer import GelbooruPicture, GelbooruViewer
from random import randint
from collections import defaultdict
import pickle
import atexit
import signal
import sys

PICTURE_INFO_TEXT = """
id: {picture_id}
size: {width}*{height}
tags: {tags}
rating: {rating}
"""
PIC_CHAT_DIC_FILE_NAME = 'picture_chat_id.dic'
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


def hello(bot, update):
    bot.send_message(
        chat_id=update.message.chat_id,
        text="""
        My name is Altair, ArchieMeng's partner.
        My core is shared on https://github.com/ArchieMeng/archie_partner_bot
        """
    )


def send_gelbooru_images(bot: telegram.bot.Bot, update: telegram.Update, args):
    chat_id = update.message.chat_id
    message_id = update.message.message_id

    def send_picture(p: GelbooruPicture):
        bot.send_photo(
            chat_id=chat_id,
            reply_to_message_id=message_id,
            photo=p.file_url
        )

    def send_picture_info(p: GelbooruPicture):
        bot.send_message(chat_id=chat_id, text=PICTURE_INFO_TEXT.format(
            picture_id=p.picture_id,
            width=p.width,
            height=p.height,
            tags=' '.join(p.tags),
            rating=p.rating
        ))

    bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.UPLOAD_PHOTO)

    if args:
        # fetch picture_id = args[0] of it is digits
        if args[0].isdigit():
            picture = gelbooru_viewer.get(id=args[0])
            if picture:
                picture = picture[0]
                send_picture(picture)
                send_picture_info(picture)
                picture_chat_id_dic[chat_id].add(picture.picture_id)
            else:
                bot.send_message(
                    chat_id=chat_id,
                    reply_to_message_id=message_id,
                    text="id: {picture_id} not found".format(picture_id=args[0])
                )
            return

        pictures = gelbooru_viewer.get(tags=args)
        if len(pictures) >= 1:
            for pic in pictures:
                if pic.picture_id not in picture_chat_id_dic[chat_id]:
                    send_picture(pic)
                    send_picture_info(pic)
                    picture_chat_id_dic[chat_id].add(pic.picture_id)
                    break
            else:
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
        picture = gelbooru_viewer.get(limit=1)
        while not picture or picture[0].picture_id in picture_chat_id_dic[chat_id]:
            picture = gelbooru_viewer.get(id=randint(1, gelbooru_viewer.max_id))
        picture = picture[0]
        send_picture(picture)
        send_picture_info(picture)
        picture_chat_id_dic[chat_id].add(picture.picture_id)


def source_id(bot: telegram.Bot, update: telegram.Update, args):
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
                text=picture.source
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
            text="/source <id> to get source url of picture which has id.\n id must be an int"
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

source_handler = CommandHandler(
    command='source',
    callback=source_id,
    pass_args=True
)
COMMAND_HANDLERS = [
    start_handler,
    taxi_handler,
    source_handler
]
i = 1
