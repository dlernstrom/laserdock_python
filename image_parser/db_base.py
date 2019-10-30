import logging
import os
import sqlite3
from sqlite3 import Error

from PIL import Image
from tqdm import tqdm

from image_parser.constants import SUBSAMPLED_IMG_SIZE

logger = logging.getLogger(__name__)


class DBConnection:
    create_table_sql = ''

    def __init__(self, name):
        if os.path.exists(name):
            os.remove(name)
        self.conn = None
        try:
            self.conn = sqlite3.connect(name)
        except Error as exc_data:
            logger.exception('%s: %s', type(exc_data), exc_data)
            raise
        else:
            logger.info('%s connected', name)
        self.create_table()

    def create_table(self):
        """ create a table from the create_table_sql statement
        :param conn: Connection object
        :param create_table_sql: a CREATE TABLE statement
        :return:
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(self.create_table_sql)
            self.conn.commit()
        except Error as exc_data:
            logger.exception('%s: %s', type(exc_data), exc_data)
            raise

    def __del__(self):
        if self.conn:
            self.conn.close()


def row_to_dict(row):
    return {'xpos': row[1], 'ypos': row[2], 'intensity': row[3]}


class ImageMagnitudes(DBConnection):
    create_table_sql = """
    CREATE TABLE image_magnitude (
        id integer PRIMARY KEY,
        xpos integer NOT NULL,
        ypos integer NOT NULL,
        intensity float NOT NULL,
        left_border integer DEFAULT 0 NOT NULL,
        bottom_border integer DEFAULT 0 NOT NULL,
        right_border integer DEFAULT 0 NOT NULL,
        top_border integer DEFAULT 0 NOT NULL
    );
    """

    def populate(self, img_to_burn, border_only):
        logger.info('Populating sqlite table')
        im = Image.open(img_to_burn, 'r')
        im = im.resize(SUBSAMPLED_IMG_SIZE, Image.ANTIALIAS)
        intensities = list(im.getdata())
        img_width, img_height = SUBSAMPLED_IMG_SIZE
        for xpos in tqdm(range(img_width), desc='generating data'):
            for ypos in range(img_height):
                position = xpos + ypos * img_width
                intensity_rgb = intensities[position]
                try:
                    intensity_magnitude = intensity_rgb[0] + intensity_rgb[1] + intensity_rgb[2]
                    intensity_sum = 255.0 * 3
                except TypeError:
                    intensity_magnitude = intensity_rgb * 3
                    intensity_sum = 255.0
                magnitude = 1.0 - 1.0 * intensity_magnitude / intensity_sum
                if magnitude > 0:
                    self.insert_intensity(xpos, ypos, magnitude)
        self.conn.commit()
        if border_only:
            self.generate_border_pixels()
            self.conn.commit()

    def get_pixel_count(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM image_magnitude")
        return cursor.rowcount

    def fetch_randomized_samples(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM image_magnitude ORDER BY RANDOM()")
        row = cursor.fetchone()
        while row is not None:
            yield row_to_dict(row)
            row = cursor.fetchone()

    def get_border_samples(self):
        samples = []
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM image_magnitude WHERE left_border = 1 ORDER BY ypos")
        samples.extend([row_to_dict(row) for row in cursor.fetchall()])
        cursor.execute("SELECT * FROM image_magnitude WHERE bottom_border = 1 ORDER BY xpos")
        samples.extend([row_to_dict(row) for row in cursor.fetchall()])
        cursor.execute("SELECT * FROM image_magnitude WHERE right_border = 1 ORDER BY ypos DESC")
        samples.extend([row_to_dict(row) for row in cursor.fetchall()])
        cursor.execute("SELECT * FROM image_magnitude WHERE top_border = 1 ORDER BY xpos DESC")
        samples.extend([row_to_dict(row) for row in cursor.fetchall()])
        return samples

    def insert_intensity(self, xpos, ypos, magnitude):
        sql = """INSERT INTO image_magnitude (xpos, ypos, intensity) VALUES(?,?,?)"""
        cur = self.conn.cursor()
        cur.execute(sql, (xpos, ypos, magnitude))

    def generate_border_pixels(self):
        logger.info('Generating border pixels')
        cursor = self.conn.cursor()
        img_width, img_height = SUBSAMPLED_IMG_SIZE
        # first find topmost pixel
        cursor.execute("SELECT * FROM image_magnitude ORDER BY ypos, xpos")
        row = cursor.fetchone()
        topmost_id = row[0]
        topmost_col = row[1]
        cursor.execute("UPDATE image_magnitude SET top_border = 1 WHERE id = ?", (topmost_id,))
        # top edge, going left
        leftmost_row = row
        for xpos in tqdm(range(topmost_col, 0, -1), 'border pixels, top edge'):
            cursor.execute("SELECT * FROM image_magnitude WHERE xpos = ? ORDER BY ypos", (xpos,))
            row = cursor.fetchone()
            if row is None:
                continue
            leftmost_row = row
            cursor.execute("UPDATE image_magnitude SET top_border = 1 WHERE id = ?", (row[0],))
        # top left corner, going down
        bottommost_row = row
        for ypos in tqdm(range(leftmost_row[2], img_height), 'border pixels, left edge'):
            cursor.execute("SELECT * FROM image_magnitude WHERE ypos = ? ORDER BY xpos", (ypos,))
            row = cursor.fetchone()
            if row is None:
                continue
            bottommost_row = row
            cursor.execute("UPDATE image_magnitude SET left_border = 1 WHERE id = ?", (row[0],))
        # across the bottom, starting from the left
        rightmost_row = row
        for xpos in tqdm(range(bottommost_row[1], img_width), 'border pixels, bottom edge'):
            cursor.execute("SELECT * FROM image_magnitude WHERE xpos = ? ORDER BY ypos DESC", (xpos,))
            row = cursor.fetchone()
            if row is None:
                continue
            rightmost_row = row
            cursor.execute("UPDATE image_magnitude SET bottom_border = 1 WHERE id = ?", (row[0],))
        # up the right side
        topmost_row = row
        for ypos in tqdm(range(rightmost_row[2], 0, -1), 'border pixels, right edge'):
            cursor.execute("SELECT * FROM image_magnitude WHERE ypos = ? ORDER BY xpos DESC", (ypos,))
            row = cursor.fetchone()
            if row is None:
                continue
            topmost_row = row
            cursor.execute("UPDATE image_magnitude SET right_border = 1 WHERE id = ?", (row[0],))
