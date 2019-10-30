import logging
import os
import random
from logging import config

BASE_LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': True,
    'loggers': {
        '': {
            'level': 'DEBUG',
        },
    }
}
config.dictConfig(BASE_LOGGING_CONFIG)

from image_parser.image_parser import ImageParser
from laserdock.laser_dock import LaserDock

logger = logging.getLogger(__name__)
img = os.path.join('img', 'halloween2019.png')


if __name__ == '__main__':
    parser = ImageParser(img_to_burn=img)
    border_only = 1

    dock = LaserDock()
    dock.intensity_minimum = 0
    if border_only:  # border loop
        dock.intensity_differential = 1000  # very fast for border squirrly loop
        samples_for_burning = parser.get_border_samples()
        loop = True
    else:
        samples_for_burning = parser.sample_iterator
        loop = False
    while True:
        for sample in samples_for_burning:
            dock.burn_sample(samples_for_burning)
        if loop:
            continue
        break
