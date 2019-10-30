import random
from PIL import Image

from image_parser.base_parser import BaseParser
from image_parser.constants import SUBSAMPLED_IMG_SIZE


class ImageParser(BaseParser):
    def __init__(self, img_to_burn):
        im = Image.open(img_to_burn, 'r')
        self.im = im.resize(SUBSAMPLED_IMG_SIZE, Image.ANTIALIAS)
        self.pixel_intensities = list(self.im.getdata())
        self.full_intensity_sum = 255 * 3

        super(ImageParser, self).__init__()

        self.image_width, self.image_height = SUBSAMPLED_IMG_SIZE
        self.image_pixels = self.generate_image_pixels()
        self.image_pixel_count = len(self.image_pixels)
        # let's randomize them for this test
        # random.shuffle(self.image_pixels)

    def generate_image_pixels(self):
        image_pixels = []
        for xcounter in range(self.image_width):
            for ycounter in range(self.image_height):
                position = xcounter + ycounter * self.image_width
                intensity = self.get_intensity(position)
                if intensity < 0.5:
                    continue
                image_pixels.append((xcounter, ycounter, intensity))
        return image_pixels

    def get_intensity(self, sample_counter):
        """This method returns the combined intensity of the rgb values and returns the scaling factor"""
        intensity_rgb = self.pixel_intensities[sample_counter]
        try:
            intensity_magnitude = intensity_rgb[0] + intensity_rgb[1] + intensity_rgb[2]
        except TypeError:
            intensity_magnitude = intensity_rgb * 3
        return 1.0 - 1.0 * intensity_magnitude / self.full_intensity_sum
