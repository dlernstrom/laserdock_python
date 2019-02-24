import random

from image_parser.base_parser import BaseParser
from image_parser.constants import SUBSAMPLED_IMG_SIZE


class PixelGradientTest(BaseParser):
    def __init__(self):
        super(PixelGradientTest, self).__init__()

        self.image_width, self.image_height = SUBSAMPLED_IMG_SIZE
        self.image_pixels = self.generate_image_pixels()
        self.image_pixel_count = len(self.image_pixels)
        # let's randomize them for this test
        random.shuffle(self.image_pixels)

    def generate_image_pixels(self):
        image_pixels = []
        for x in range(self.image_width):
            for y in range(self.image_height):
                image_pixels.append((x, y, 1.0 * (x + y) / (self.image_width + self.image_height)))
        return image_pixels
