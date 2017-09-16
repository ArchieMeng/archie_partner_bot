from telegram.ext import BaseFilter


class FilterTest(BaseFilter):
    def filter(self, message):
        return message.text.startswith("test")


test = FilterTest()