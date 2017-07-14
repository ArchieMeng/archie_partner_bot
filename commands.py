import telegram
from telegram.ext import CommandHandler
from telegram.ext.dispatcher import run_async
from GelbooruViewer import GelbooruPicture, GelbooruViewer
from random import randint, seed
from collections import defaultdict
import pickle
import atexit
import signal
import sys
import logging
from threading import Lock
from time import time

# Constants
PICTURE_INFO_TEXT = """
id: {picture_id}
size: {width}*{height}
source: {source}
Original url: {file_url}
rating: {rating}
"""
PIC_CHAT_DIC_FILE_NAME = 'picture_chat_id.dic'
COMMAND_HANDLERS = [] # list of command_handlers

# global variables
pic_chat_dic_lock = Lock()
gelbooru_viewer = GelbooruViewer()

# start up function
try:
    with open(PIC_CHAT_DIC_FILE_NAME, 'rb') as fp:
        picture_chat_id_dic = pickle.load(fp)
except FileNotFoundError:
    picture_chat_id_dic = defaultdict(set)
seed(time())


@atexit.register
def save_pic_chat_dic():
    with open(PIC_CHAT_DIC_FILE_NAME, 'wb') as fp:
        pickle.dump(picture_chat_id_dic, fp, protocol=2)


def raise_exit(signum, stack):
    sys.exit(-1)
signal.signal(signal.SIGTERM, raise_exit)


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


@set_command_handler('start')
@run_async
def hello(bot, update):
    bot.send_message(
        chat_id=update.message.chat_id,
        text="""
        My name is Altair, ArchieMeng's partner.
        My core is shared on https://github.com/ArchieMeng/archie_partner_bot
        """
    )


@set_command_handler('img', pass_args=True)
@run_async
def send_safe_gelbooru_images(bot: telegram.bot.Bot, update: telegram.Update, args):
    chat_id = update.message.chat_id
    message_id = update.message.message_id
    h_rating = {'e', 'q'}

    bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.TYPING)

    # internal function to send picture to chat
    def send_picture(p: GelbooruPicture):
        url = p.sample_url
        logging.info("id: {pic_id} - file_url: {file_url}".format(
            pic_id=p.picture_id,
            file_url=url
        ))
        bot.send_photo(
            chat_id=chat_id,
            reply_to_message_id=message_id,
            photo=url,
            caption=PICTURE_INFO_TEXT.format(
                picture_id=p.picture_id,
                width=p.width,
                height=p.height,
                source=p.source,
                file_url=p.file_url,
                rating=p.rating
            )
        )

    if args:
        # fetch picture_id = args[0] of it is digits
        if args[0].isdigit():
            bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.UPLOAD_PHOTO)
            picture = gelbooru_viewer.get(id=args[0])
            if picture:
                picture = picture[0]
                send_picture(picture)
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
            pictures = gelbooru_viewer.get_all(tags=args, num=500)
            if len(pictures) >= 1:
                send = False
                for pic in pictures:
                    with pic_chat_dic_lock:
                        if pic.picture_id not in picture_chat_id_dic[chat_id]:
                            if pic.rating not in h_rating:
                                picture_chat_id_dic[chat_id].add(pic.picture_id)
                                send = True
                    if send:
                        send_picture(pic)
                        return
                else:
                    bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.TYPING)
                    for pic in pictures:
                        if pic.rating not in h_rating:
                            picture_chat_id_dic[chat_id] = {pic.picture_id}
                            send_picture(pic)
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
            # for we have judged viewed before, we can only judge valid here
            invalid_or_viewed = not picture or picture[0].rating in h_rating
            if picture and picture[0].rating in h_rating:
                with pic_chat_dic_lock:
                    picture_chat_id_dic[chat_id].remove(pic_id)
        picture = picture[0]
        with pic_chat_dic_lock:
            picture_chat_id_dic[chat_id].add(picture.picture_id)
        bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.UPLOAD_PHOTO)
        send_picture(picture)


@set_command_handler('taxi', pass_args=True)
@run_async
def send_gelbooru_images(bot: telegram.bot.Bot, update: telegram.Update, args):
    chat_id = update.message.chat_id
    message_id = update.message.message_id

    bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.TYPING)

    # internal function to send picture to chat
    def send_picture(p: GelbooruPicture):
        url = p.sample_url
        logging.info("id: {pic_id} - file_url: {file_url}".format(
            pic_id=p.picture_id,
            file_url=url
        ))
        bot.send_photo(
            chat_id=chat_id,
            reply_to_message_id=message_id,
            photo=url,
            caption=PICTURE_INFO_TEXT.format(
                picture_id=p.picture_id,
                width=p.width,
                height=p.height,
                source=p.source,
                file_url=p.file_url,
                rating=p.rating
            )
        )

    if args:
        # fetch picture_id = args[0] of it is digits
        if args[0].isdigit():
            bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.UPLOAD_PHOTO)
            picture = gelbooru_viewer.get(id=args[0])
            if picture:
                picture = picture[0]
                send_picture(picture)
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
            pictures = gelbooru_viewer.get_all(tags=args, num=500)
            if len(pictures) >= 1:
                send = False
                for pic in pictures:
                    with pic_chat_dic_lock:
                        if pic.picture_id not in picture_chat_id_dic[chat_id]:
                            picture_chat_id_dic[chat_id].add(pic.picture_id)
                            send = True
                    if send:
                        send_picture(pic)
                        break
                else:
                    bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.TYPING)
                    with pic_chat_dic_lock:
                        picture_chat_id_dic[chat_id] = {pictures[0].picture_id}
                        send_picture(pictures[0])
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
        send_picture(picture)


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

