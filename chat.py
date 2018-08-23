import numpy
import telegram
from telegram.ext import MessageHandler
from telegram.ext.dispatcher import run_async
import filters
from telegram.ext.filters import Filters
from pickle import dump
from gelbooru_commands import send_tags_info
from io import BytesIO
from resizeimage.resizeimage import resize_contain as resize
from PIL import Image
from GelbooruClassifier.classifier import GelbooruClassifier

MESSAGE_HANDLERS = []
img2arr = lambda img: numpy.array(img).flatten()
std_size = (150, 100)
classifier = GelbooruClassifier(params_name='logreg_params.h5')


def set_message_handler(
        set_filters,
        allow_edited=False,
        pass_update_queue=False,
        pass_job_queue=False,
        pass_user_data=False,
        pass_chat_data=False,
        message_updates=True,
        channel_post_updates=True,
        edited_updates=False
):
    def decorate(func):
        MESSAGE_HANDLERS.append(
            MessageHandler(
                filters=set_filters,
                callback=func,
                allow_edited=allow_edited,
                pass_update_queue=pass_update_queue,
                pass_job_queue=pass_job_queue,
                pass_user_data=pass_user_data,
                pass_chat_data=pass_chat_data,
                message_updates=message_updates,
                channel_post_updates=channel_post_updates,
                edited_updates=edited_updates
            )
        )
        return func
    return decorate


@set_message_handler(set_filters=filters.test)
@run_async
def echo(bot: telegram.bot.Bot, update: telegram.Update):
    bot.send_message(
        chat_id=update.message.chat_id,
        text=update.message.text
    )


@set_message_handler(set_filters=Filters.text)
@run_async
def record(bot: telegram.bot.Bot, update: telegram.Update):
    text = update.message.text
    if text.startswith("id:") and text[3:].strip().isdigit():
        send_tags_info(bot, update, text[3:])
    # just record message
    chat_id = update.message.chat_id
    # record messages using pickle
    with open("message_of_{}".format(chat_id), "a+b") as record_file:
        dump(update.message, record_file)


# image receiver: receive images with caption set to "tags"
@set_message_handler(set_filters=Filters.photo)
@run_async
def photo_record(bot: telegram.Bot, update: telegram.Update):
    if update.message.caption and update.message.caption == "tags":
        photo_id = update.message.photo[0].file_id
        image_io = BytesIO()
        bot.get_file(photo_id).download(out=image_io)
        image = Image.open(image_io)
        image = resize(image, std_size)
        image = image.convert("RGB")
        img_vec = img2arr(image)
        tags = classifier.predict_tags(numpy.array([img_vec]))[0]
        update.message.reply_text("tags:" + ','.join(tags))

