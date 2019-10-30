LASERDOCK_VENDOR = 0x1fc9
LASERDOCK_PRODUCT = 0x04d8

"""
These are some random notes I took along the way when understanding what
the combination of intensity (repeats) and resolution did to me
REPEATS = 100000  # plywood, 4096x4096 (skipped every few rows and columns for speed)
REPEATS = 10000  # 2x6, 4096x4096 (skipped every few rows and columns for speed)
REPEATS = 500  # 2x6, no skipping row/col, every pixel # this was too dark, IMO, see creeper
REPEATS = 500  # Poplar, no skipping row/col, every pixel 4096x4096, linear test (100 not enough)
At a repeat of 500 and the poplar Linear grayscale test, I realize I'm getting too much bleed-over.  I think the
cleanest way to assess how much is to do a subsampling of the (4096x4096) image and treat it like a 100x100 or
something.  Additionally, if I randomly burn the 1,000 pixels (100x100), then the burn intensity from one pixel will not
affect the burn intensity of the next pixel.  I believe I will fake an image that is an intensity scale from 0 -> 100%
in both the x and y direction.  REPEAT will set the full darkness for me.

REPEATS = 100000  # Poplar, no skipping row/col, linear test 100x100
"""

# Since we are burning wood, we have found that the wood doesn't even scar until about 25% of the intensity has occurred
# so we are treating 25,000 as unburned (white) and 100,000 as burned (black).
# this means that we can say that:
# 100% * INTENSITY_DIFFERENTIAL + MIN_INTENSITY == 100,000
# 0% * INTENSITY_DIFFERENTIAL + MIN_INTENSITY == 25,000
# By running the numbers this way, little bits of grey will show up quite nicely
INTENSITY_DIFFERENTIAL = 4000 # 75000  # difference between 0% and 100% in the grayscaling
MIN_INTENSITY = 0 # 25000

COMMAND_ENABLE_OUTPUT = b'\x80'
COMMAND_GET_OUTPUT_STATE = b'\x81'
COMMAND_SET_DAC_RATE = b'\x82'
COMMAND_GET_DAC_RATE = b'\x83'
COMMAND_GET_MAX_DAC_RATE = b'\x84'
COMMAND_GET_SAMPLE_ELEMENT_COUNT = b'\x85'
COMMAND_GET_ISO_PACKET_SAMPLE_COUNT = b'\x86'
COMMAND_GET_MIN_DAC_VALUE = b'\x87'
COMMAND_GET_MAX_DAC_VALUE = b'\x88'
COMMAND_GET_RINGBUFFER_SAMPLE_COUNT = b'\x89'
COMMAND_GET_RINGBUFFER_EMPTY_SAMPLE_COUNT = b'\x8A'
COMMAND_MAJOR_FIRMWARE = b'\x8B'
COMMAND_MINOR_FIRMWARE = b'\x8C'
COMMAND_SET_RINGBUFFER = b'\x8D'
COMMAND_GET_BULK_PACKET_SAMPLE_COUNT = b'\x8E'
SAMPLES_PER_PACKET = 64
PROJECTOR_RESOLUTION = 4096
