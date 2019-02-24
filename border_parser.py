import logging

from image_parser.border_parser import BorderParser
from laserdock.laser_dock import LaserDock

logger = logging.getLogger(__name__)


if __name__ == '__main__':
    parser = BorderParser()
    repeat_burn = True

    dock = LaserDock()
    dock.intensity_minimum = 0
    dock.intensity_differential = 10
    samples_for_burning = parser.make_samples()
    starting_sample = 0
    while True:
        dock.burn_samples(starting_sample, samples_for_burning)
