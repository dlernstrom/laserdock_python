import logging
import random

from tqdm import tqdm

from image_parser.constants import SUBSAMPLED_X_ACROSS, SUBSAMPLED_Y_UPDOWN, RED_COLOR, GREEN_COLOR, BLUE_COLOR, \
    FLIP_TOP_BOTTOM, FLIP_LEFT_RIGHT
from image_parser.db_base import ImageMagnitudes
from laserdock.constants import PROJECTOR_RESOLUTION

logger = logging.getLogger(__name__)
PROJECTOR_WIDTH = PROJECTOR_HEIGHT = PROJECTOR_RESOLUTION


def _flip_top_bottom(sample):
    sample['y'] = PROJECTOR_HEIGHT - 1 - sample['y']
    return sample


def _flip_left_right(sample):
    sample['x'] = PROJECTOR_WIDTH - 1 - sample['x']
    return sample


def image_pixel_to_projector_sample(xpos, ypos, intensity):
    proj_xpos = int(1.0 * xpos * PROJECTOR_WIDTH / SUBSAMPLED_X_ACROSS)
    proj_ypos = int(1.0 * ypos * PROJECTOR_HEIGHT / SUBSAMPLED_Y_UPDOWN)
    sample = {'r': RED_COLOR, 'g': GREEN_COLOR, 'b': BLUE_COLOR, 'x': proj_xpos, 'y': proj_ypos, 'intensity': intensity}
    if FLIP_TOP_BOTTOM:
        sample = _flip_top_bottom(sample)
    if FLIP_LEFT_RIGHT:
        sample = _flip_left_right(sample)
    return sample


class ImageParser:
    def __init__(self, img_to_burn, border_only, cache):
        self.magnitudes = ImageMagnitudes('magnitudes.db', cache)
        if not cache:
            self.magnitudes.populate(img_to_burn, border_only)
        super(ImageParser, self).__init__()

    def sample_iterator(self):
        """Filtering to samples in image, this is a generator in this implementation"""
        pixel_count = self.magnitudes.get_pixel_count()
        logger.warning('There are %s pixels to burn', pixel_count)
        sample_generator = self.magnitudes.fetch_randomized_samples()
        for sample_counter, sample_dict in zip(tqdm(range(pixel_count), desc='rendering'), sample_generator):
            yield image_pixel_to_projector_sample(sample_dict['xpos'], sample_dict['ypos'], sample_dict['intensity'])

    def get_border_samples(self):
        return [image_pixel_to_projector_sample(sample_dict['xpos'], sample_dict['ypos'], sample_dict['intensity'])
                for sample_dict in self.magnitudes.get_border_samples()]
