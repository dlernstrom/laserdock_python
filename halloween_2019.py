import logging
import logging.config
import os
import random
import sys

from image_parser.image_parser import ImageParser
from laserdock.laser_dock import LaserDock

BASE_LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {'format': '%(asctime)s - %(levelname)s - %(message)s', 'datefmt': '%Y-%m-%d %H:%M:%S'}
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'default',
            'stream': 'ext://sys.stdout'
        },
    },
    'loggers': {
        '': {
            'level': 'DEBUG',
            'handlers': ['console'],
        },
    }
}
logging.config.dictConfig(BASE_LOGGING_CONFIG)
logger = logging.getLogger()
logger.warning('hello world')
img = os.path.join('img', 'halloween2019.png')


if __name__ == '__main__':
    cache = False
    border_only = False
    if 'border' in sys.argv:  # border loop
        border_only = True
    if 'cache' in sys.argv:
        cache = True
    parser = ImageParser(img_to_burn=img, border_only=border_only, cache=cache)
    dock = LaserDock()
    dock.intensity_minimum = 0
    if border_only:  # border loop
        dock.intensity_differential = 0.25  # (seconds) very fast for border squirrly loop
        samples_for_burning = parser.get_border_samples()
        logger.warning('there are %s samples for burning', len(samples_for_burning))
        loop = True
    else:
        dock.intensity_differential = 3.0  # (seconds) full plywood intensity
        samples_for_burning = parser.sample_iterator()
        loop = False
    while True:
        for sample in samples_for_burning:
            dock.burn_sample(sample)
        if loop:
            continue
        break
