import logging
import os

from PIL import Image
from tqdm import tqdm

from laserdock_python.laserdock.laser_dock import LaserDock

logger = logging.getLogger(__name__)

IMG = os.path.join('img', 'dharma-swan-logo.jpg')
IMG = os.path.join('img', 'VaultBoy.bmp')
SAMPLES_PER_PACKET = 64
INTENSITY = 1.0
RED_COLOR = int(255 * INTENSITY)
GREEN_COLOR = int(255 * INTENSITY)
BLUE_COLOR = int(255 * INTENSITY)
# REPEATS = 100000  # plywood
# REPEATS = 10000  # 1000 is too slow for poster board
REPEATS = 10000  # plywood
PREVIEW_REPEATS = 10


class BaseParser(object):
    def __init__(self):
        self.width = self.height = 4096
        self.pixel_count = self.width * self.height

    def generate_edge_pixels(self):
        while True:
            for x in range(self.width):
                yield (x, 0)
            for y in range(self.height):
                yield (self.width - 1, y)
            for x in range(self.width):
                yield (self.width - 1 - x, self.height - 1)
            for y in range(self.height):
                yield (0, self.height - 1 - y)

    def flip_sample(self, sample):
        sample['x'] = self.width - 1 - sample['x']
        sample['y'] = self.height - 1 - sample['y']
        return sample

    def pixel_to_sample(self, xpos, ypos):
        return self.flip_sample({'r': RED_COLOR, 'g': GREEN_COLOR, 'b': BLUE_COLOR, 'x': xpos, 'y': ypos})

    def make_samples(self):
        """Filtering to samples in image, this is a generator in this implementation"""
        for generated_pixel in self.generate_edge_pixels():
            yield self.pixel_to_sample(generated_pixel[0], generated_pixel[1])


class BaseImageParser(BaseParser):
    def __init__(self, img):
        super(BaseImageParser, self).__init__()
        self.im = Image.open(img, 'r')
        width, height = self.im.size
        assert width == height == 4096
        self.pixels = list(self.im.getdata())

    def is_cell_white(self, row_counter, col_counter):
        """This method assumes at least a single white pixel border around the entire image, because only black pixels
        will be sent in and the 4 surrounding pixels will be checked"""
        array_position = row_counter * self.width + col_counter
        if self.pixels[array_position] > 200:
            return True
        return False

    def is_cell_border(self, row_counter, col_counter):
        """Assumes that the cell is already determined as black and it is not a border pixel"""
        if self.is_cell_white(row_counter, col_counter - 1):
            return True
        if self.is_cell_white(row_counter, col_counter + 1):
            return True
        if self.is_cell_white(row_counter - 1, col_counter):
            return True
        if self.is_cell_white(row_counter + 1, col_counter):
            return True
        return False


class ImageParser(BaseImageParser):
    def __init__(self):
        super(ImageParser, self).__init__(IMG)
        self.samples = self.make_samples()
        logger.warning('There are %d samples to render' % len(self.samples))

    def make_samples(self):
        """Filtering to samples in image"""
        constrained_samples = []

        for sample_counter in tqdm(range(self.pixel_count)):
            col_counter = sample_counter % self.width
            row_counter = sample_counter // self.width
            if self.is_cell_white(row_counter, col_counter):
                continue
            if self.is_cell_border(row_counter, col_counter):
                if col_counter % 2 == 0 and row_counter % 2 == 0:
                    constrained_samples.append(self.pixel_to_sample(col_counter, row_counter))
                continue
            # sample must be in the field, only do every 20th row
            if row_counter % 20 == 0 and col_counter % 10 == 0:
                constrained_samples.append(self.pixel_to_sample(col_counter, row_counter))
        return constrained_samples


def burn_samples(dock, start, samples_to_burn):
    packet_samples = []
    parser_sample_count = len(samples_to_burn)
    for sample_counter in tqdm(range(start, parser_sample_count)):
        for repeat_entry in range(REPEATS):
            generated_sample = samples_to_burn[sample_counter]
            packet_samples.append(generated_sample)
            if len(packet_samples) == SAMPLES_PER_PACKET:
                dock.send_samples(packet_samples)
                packet_samples = []
    dock.send_samples(packet_samples)


def trace_box(dock, generator):
    packet_samples = []
    for generated_sample in generator():
        for repeat_entry in range(PREVIEW_REPEATS):
            packet_samples.append(generated_sample)
            if len(packet_samples) == SAMPLES_PER_PACKET:
                dock.send_samples(packet_samples)
                packet_samples = []


if __name__ == '__main__':
    img_parser = ImageParser()
    a = LaserDock()
    samples_for_burning = img_parser.make_samples()
    starting_sample = 0
    burn_samples(a, starting_sample, samples_for_burning)
    # base_parser = BaseParser()
    # trace_box(a, base_parser.make_samples)
