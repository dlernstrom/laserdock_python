import random

from image_parser.base_parser import BaseParser


class BorderParser(BaseParser):
    def __init__(self):
        super(BorderParser, self).__init__()

        self.image_width = self.image_height = 100
        self.image_pixels = self.generate_image_pixels()
        self.image_pixel_count = len(self.image_pixels)

    def generate_image_pixels(self):
        image_pixels = []
        for x in range(self.image_width):
            image_pixels.append((x, 0, 0.2))
        for y in range(self.image_height):
            image_pixels.append((self.image_width - 1, y, 0.2))
        for x in range(self.image_width):
            image_pixels.append((self.image_width - 1 - x, self.image_height - 1, 0.2))
        for y in range(self.image_height):
            image_pixels.append((0, self.image_height - 1 - y, 0.2))
        return image_pixels
