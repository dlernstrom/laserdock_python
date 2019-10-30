import logging
import os

from PIL import Image
from tqdm import tqdm

from laserdock.laser_dock import LaserDock

logger = logging.getLogger(__name__)

# IMG = os.path.join('img', 'CreeperGrayscaleTest.png')
IMG = os.path.join('img', 'Linear-ZonePlateb.png')
SAMPLES_PER_PACKET = 64
FULL_INTENSITY = 255
INTENSITY = 1.0
RED_COLOR = int(255 * INTENSITY)
GREEN_COLOR = int(255 * INTENSITY)
BLUE_COLOR = int(255 * INTENSITY)
# REPEATS = 100000  # plywood
# REPEATS = 10000  # 1000 is too slow for poster board
REPEATS = 10000  # 2x6
REPEATS = 500  # 2x6, no skipping row/col, every pixel # this was too dark, IMO, see creeper
REPEATS = 500  # Poplar, no skipping row/col, linear test (100 not enough)
PREVIEW_REPEATS = 10
FLIP_TOP_BOTTOM = False
FLIP_LEFT_RIGHT = True


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

    def flip_top_bottom(self, sample):
        sample['y'] = self.height - 1 - sample['y']
        return sample

    def flip_left_right(self, sample):
        sample['x'] = self.width - 1 - sample['x']
        return sample

    def pixel_to_sample(self, xpos, ypos, intensity):
        sample = {'r': RED_COLOR, 'g': GREEN_COLOR, 'b': BLUE_COLOR, 'x': xpos, 'y': ypos, 'intensity': intensity}
        if FLIP_TOP_BOTTOM:
            sample = self.flip_top_bottom(sample)
        if FLIP_LEFT_RIGHT:
            sample = self.flip_left_right(sample)
        return sample

    def make_samples(self):
        """Filtering to samples in image, this is a generator in this implementation"""
        for generated_pixel in self.generate_edge_pixels():
            yield self.pixel_to_sample(generated_pixel[0], generated_pixel[1], intensity=0.2)


class BaseImageParser(BaseParser):
    def __init__(self, img):
        super(BaseImageParser, self).__init__()
        self.im = Image.open(img, 'r')
        width, height = self.im.size
        assert width == height == 4096
        self.pixels = list(self.im.getdata())
        self.full_intensity_sum = 255 * 3

    def get_intensity(self, row_counter, col_counter):
        """This method returns the combined intensity of the rgb values and returns the scaling factor"""
        array_position = row_counter * self.width + col_counter
        location = self.pixels[array_position]
        intensity_magnitude = location[0] + location[1] + location[2]
        return 1.0 - 1.0 * intensity_magnitude / self.full_intensity_sum


class ImageParser(BaseImageParser):
    def __init__(self):
        super(ImageParser, self).__init__(IMG)

    def make_samples(self):
        """Filtering to samples in image"""
        constrained_samples = []

        for sample_counter in tqdm(range(self.pixel_count), desc='making samples'):
            col_counter = sample_counter % self.width
            row_counter = sample_counter // self.width
            intensity = self.get_intensity(row_counter, col_counter)
            # row_counter += 200  # shift down by 200 pixels
            constrained_samples.append(self.pixel_to_sample(col_counter, row_counter, intensity))
        logger.warning('There are %d samples to render' % len(constrained_samples))
        return constrained_samples


def burn_samples(dock, start, samples_to_burn):
    packet_samples = []
    parser_sample_count = len(samples_to_burn)
    for sample_counter in tqdm(range(start, parser_sample_count), desc='sending samples'):
        generated_sample = samples_to_burn[sample_counter]
        for repeat_entry in range(int(generated_sample['intensity'] * REPEATS)):
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


TRACE = False
if __name__ == '__main__':
    if TRACE:
        base_parser = BaseParser()
        a = LaserDock()
        trace_box(a, base_parser.make_samples)
    else:
        img_parser = ImageParser()
        a = LaserDock()
        samples_for_burning = img_parser.make_samples()
        starting_sample = 0
        burn_samples(a, starting_sample, samples_for_burning)
