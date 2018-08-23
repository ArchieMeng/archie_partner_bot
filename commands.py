import os
from multiprocessing import Process, Manager, Value

import telegram
from telegram.ext import CommandHandler
from telegram.ext.dispatcher import run_async


from calc import calc
from recycle_cache import RecycleCache
from videos_fetcher import get_info, download
import redis_dao

COMMAND_HANDLERS = []  # list of command_handlers


def is_public_chat(update: telegram.Update):
    if isinstance(update.message.chat, telegram.Chat):
        chat = update.message.chat
        return chat.type != telegram.Chat.PRIVATE
    else:
        print(update.message.chat)
        return True

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
Using api from Gelbooru.
Tips: send images with caption set to "tags" to get predicted tags
My core is shared on https://github.com/ArchieMeng/archie_partner_bot
        """
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
