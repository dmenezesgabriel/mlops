import re
from math import ceil

from ssg.domain.readtime.parser import ReadtimeParser

DEFAULT_WORDS_PER_MINUTE = 265


def calculate_readtime_minutes(
    html: str, words_per_minute: int = DEFAULT_WORDS_PER_MINUTE
) -> int:
    parser = ReadtimeParser()
    parser.feed(html)
    parser.close()

    words = len(re.split(r"\W+", parser.text))
    seconds = ceil(words / words_per_minute * 60)
    delay = 12
    for _ in range(parser.images):
        seconds += delay
        if delay > 3:
            delay -= 1

    return ceil(seconds / 60)
