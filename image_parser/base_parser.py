import logging

from tqdm import tqdm

from image_parser.constants import RED_COLOR, GREEN_COLOR, BLUE_COLOR, FLIP_TOP_BOTTOM, FLIP_LEFT_RIGHT
from laserdock.constants import PROJECTOR_RESOLUTION

logger = logging.getLogger(__name__)


class BaseParser(object):
    flip_top_bottom = FLIP_TOP_BOTTOM
    flip_left_right = FLIP_LEFT_RIGHT

    def __init__(self):
        self.projector_width = self.projector_height = PROJECTOR_RESOLUTION

        self.image_width = self.image_height = PROJECTOR_RESOLUTION
        self.image_pixels = []
        self.image_pixel_count = len(self.image_pixels)

    def image_coord_to_proj_coord(self, x, y):
        projector_x = int(1.0 * self.projector_width * x / self.image_width)
        projector_y = int(1.0 * self.projector_height * y / self.image_height)
        return projector_x, projector_y

    def _flip_top_bottom(self, sample):
        sample['y'] = self.projector_height - 1 - sample['y']
        return sample

    def _flip_left_right(self, sample):
        sample['x'] = self.projector_width - 1 - sample['x']
        return sample

    def image_pixel_to_projector_sample(self, xpos, ypos, intensity):
        proj_x, proj_y = self.image_coord_to_proj_coord(xpos, ypos)
        sample = {'r': RED_COLOR, 'g': GREEN_COLOR, 'b': BLUE_COLOR, 'x': proj_x, 'y': proj_y, 'intensity': intensity}
        if FLIP_TOP_BOTTOM:
            sample = self._flip_top_bottom(sample)
        if FLIP_LEFT_RIGHT:
            sample = self._flip_left_right(sample)
        return sample

    def make_samples(self):
        """Filtering to samples in image, this is a generator in this implementation"""
        constrained_samples = []

        for sample_counter in tqdm(range(self.image_pixel_count), desc='making samples'):
            generated_pixel = self.image_pixels[sample_counter]
            sample = self.image_pixel_to_projector_sample(generated_pixel[0], generated_pixel[1],
                                                          intensity=generated_pixel[2])
            constrained_samples.append(sample)
        logger.warning('There are %d samples to render' % len(constrained_samples))
        return constrained_samples
