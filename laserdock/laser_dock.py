import logging
import struct
import time

import usb.core
import usb.util
from tqdm import tqdm

from laserdock import constants as const

logger = logging.getLogger(__name__)


def sleep_until(time_to_wake):
    # wait here for time to be ready
    while time.monotonic() < time_to_wake:
        time_to_wait = time_to_wake - time.monotonic()
        sleep_time = min(time_to_wait, 1)
        # logger.warning('sleeping for %s', sleep_time)
        time.sleep(min(time_to_wait, 1))  # sleep the minimum of the correct time and 1 second


class LaserDock:
    intensity_differential = const.INTENSITY_DIFFERENTIAL
    intensity_minimum = const.MIN_INTENSITY

    def __init__(self):
        self.packet_samples = []
        self.dev = self.connect()
        self.get_version_major_number()
        self.get_version_minor_number()
        self.get_max_dac_rate()
        self.get_min_dac_value()
        self.get_max_dac_value()
        self.set_dac_rate(const.FPS)
        self.get_dac_rate()
        self.clear_ringbuffer()
        self.get_sample_element_count()
        self.get_iso_packet_sample_count()
        self.get_bulk_packet_sample_count()
        self.enable_output()
        self.get_output()
        self.last_packet_send_time = time.monotonic()

    @staticmethod
    def connect():
        # find our device
        dev = usb.core.find(idVendor=const.LASERDOCK_VENDOR, idProduct=const.LASERDOCK_PRODUCT)

        # was it found?
        if dev is None:
            raise ValueError('Device not found')
        c = 1
        for config in dev:
            print('config', c)
            print('Interfaces', config.bNumInterfaces)
            for i in range(config.bNumInterfaces):
                if dev.is_kernel_driver_active(i):
                    print('detaching kernel driver')
                    dev.detach_kernel_driver(i)
                print('Interface #%s' % i)
            c += 1

        # set the active configuration. With no arguments, the first configuration will be the active one
        dev.set_configuration()
        """
        def find_first_out_endpoint(endpoint):
            return usb.util.endpoint_direction(endpoint.bEndpointAddress) == usb.util.ENDPOINT_OUT

        for cfg in dev:
            print('Configuration #: %s' % str(cfg.bConfigurationValue))
            for intf in cfg:
                print('\tInterface,AltInterface: %s,%s' % (str(intf.bInterfaceNumber), str(intf.bAlternateSetting)))
                for ep in intf:
                    print('\t\tEndpoint Address: %s' % str(ep.bEndpointAddress))

        # get an endpoint instance
        cfg = dev.get_active_configuration()

        intf = cfg[(0, 0)]

        ep = usb.util.find_descriptor(intf,
                                      custom_match=find_first_out_endpoint)  # match the first OUT endpoint
        assert ep is not None
        """
        return dev

    def disconnect(self):
        usb.util.dispose_resources(self.dev)
        self.dev = None

    def write_ctrl(self, msg):
        self.dev[0][(0, 0)][0].write(msg)

    def write_bulk(self, msg):
        self.dev[0][(1, 0)][0].write(msg)

    def read_ctrl(self):
        packet_size = self.dev[0][(0, 0)][1].wMaxPacketSize
        response = self.dev[0][(0, 0)][1].read(packet_size)
        return response

    def enable_output(self):
        print('Enabling output')
        self.write_ctrl(const.COMMAND_ENABLE_OUTPUT + b'\x01')
        response = self.read_ctrl()[:4]
        command, response = struct.unpack('<HH', response)
        if command != ord(const.COMMAND_ENABLE_OUTPUT):
            raise Exception('Bad response')
        print('Response from enabling output: %s' % response)

    def disable_output(self):
        self.write_ctrl(b'\x80\x00')
        print(self.read_ctrl())

    def get_output(self):
        """guint8"""
        self.write_ctrl(const.COMMAND_GET_OUTPUT_STATE)
        response = self.read_ctrl()[:4]
        command, response = struct.unpack('<HH', response)
        if command != ord(const.COMMAND_GET_OUTPUT_STATE):
            raise Exception('Bad response')
        print('Current Output Status: %s' % response)

    def get_dac_rate(self):
        """guint32"""
        self.write_ctrl(const.COMMAND_GET_DAC_RATE)
        response = self.read_ctrl()[:4]
        command, response = struct.unpack('<HH', response)
        if command != ord(const.COMMAND_GET_DAC_RATE):
            raise Exception('Bad response')
        print('Current DAC Rate: %s' % response)

    def set_dac_rate(self, rate):
        """suint32(d->devh_ctl, 0x82, rate);"""
        print('Setting DAC Rate to %s' % rate)
        self.write_ctrl(const.COMMAND_SET_DAC_RATE + struct.pack('<I', rate))
        response = self.read_ctrl()[:4]
        command, response = struct.unpack('<HH', response)
        if command != ord(const.COMMAND_SET_DAC_RATE):
            raise Exception('Bad response')
        print('Response after setting DAC rate: %s' % response)

    def get_max_dac_rate(self):
        self.write_ctrl(const.COMMAND_GET_MAX_DAC_RATE)
        response = self.read_ctrl()[:4]
        command, response = struct.unpack('<HH', response)
        if command != ord(const.COMMAND_GET_MAX_DAC_RATE):
            raise Exception('Bad response')
        print('Max DAC Rate: %s' % response)

    def get_min_dac_value(self):
        self.write_ctrl(const.COMMAND_GET_MIN_DAC_VALUE)
        response = self.read_ctrl()[:4]
        command, response = struct.unpack('<HH', response)
        if command != ord(const.COMMAND_GET_MIN_DAC_VALUE):
            raise Exception('Bad response')
        print('Min DAC Value: %s' % response)

    def get_max_dac_value(self):
        self.write_ctrl(const.COMMAND_GET_MAX_DAC_VALUE)
        response = self.read_ctrl()[:4]
        command, response = struct.unpack('<HH', response)
        if command != ord(const.COMMAND_GET_MAX_DAC_VALUE):
            raise Exception('Bad response')
        print('Max DAC Value: %s' % response)

    def get_sample_element_count(self):
        self.write_ctrl(const.COMMAND_GET_SAMPLE_ELEMENT_COUNT)
        response = self.read_ctrl()[:4]
        command, response = struct.unpack('<HH', response)
        if command != ord(const.COMMAND_GET_SAMPLE_ELEMENT_COUNT):
            raise Exception('Bad response')
        print('get_sample_element_count: %s' % response)

    def get_iso_packet_sample_count(self):
        self.write_ctrl(const.COMMAND_GET_ISO_PACKET_SAMPLE_COUNT)
        response = self.read_ctrl()[:4]
        command, response = struct.unpack('<HH', response)
        if command != ord(const.COMMAND_GET_ISO_PACKET_SAMPLE_COUNT):
            raise Exception('Bad response')
        print('get_iso_packet_sample_count: %s' % response)

    def get_bulk_packet_sample_count(self):
        self.write_ctrl(const.COMMAND_GET_BULK_PACKET_SAMPLE_COUNT)
        response = self.read_ctrl()[:4]
        command, response = struct.unpack('<HH', response)
        if command != ord(const.COMMAND_GET_BULK_PACKET_SAMPLE_COUNT):
            raise Exception('Bad response')
        print('get_bulk_packet_sample_count: %s' % response)

    def get_version_major_number(self):
        """Return the major version number in the firmware"""
        self.write_ctrl(const.COMMAND_MAJOR_FIRMWARE)
        response = self.read_ctrl()[:4]
        command, response = struct.unpack('<HH', response)
        if command != ord(const.COMMAND_MAJOR_FIRMWARE):
            raise Exception('Bad response')
        print('Major Firmware Version: %s' % response)

    def get_version_minor_number(self):
        self.write_ctrl(const.COMMAND_MINOR_FIRMWARE)
        response = self.read_ctrl()[:4]
        command, response = struct.unpack('<HH', response)
        if command != ord(const.COMMAND_MINOR_FIRMWARE):
            raise Exception('Bad response')
        print('Minor Firmware Version: %s' % response)

    def get_ringbuffer_sample_count(self):
        self.write_ctrl(const.COMMAND_GET_RINGBUFFER_SAMPLE_COUNT)
        print(self.read_ctrl())

    def get_ringbuffer_empty_sample_count(self):
        self.write_ctrl(const.COMMAND_GET_RINGBUFFER_EMPTY_SAMPLE_COUNT)
        print(self.read_ctrl())

    def clear_ringbuffer(self):
        """suint8"""
        print('Clearing ringbuffer')
        self.write_ctrl(const.COMMAND_SET_RINGBUFFER + b'\x00')
        response = self.read_ctrl()[:4]
        command, response = struct.unpack('<HH', response)
        if command != ord(const.COMMAND_SET_RINGBUFFER):
            raise Exception('Bad response')
        print('Response from set ringbuffer command: %s' % response)

    def send_samples(self):
        # this one uses the bulk transfer
        logger.warning('sending samples')
        msg = b''
        for sample in self.packet_samples:
            msg += struct.pack('<B', sample['r'])
            msg += struct.pack('<B', sample['g'])
            msg += struct.pack('<B', sample['b'])
            msg += struct.pack('<B', 0)
            msg += struct.pack('<H', sample['x'])
            msg += struct.pack('<H', sample['y'])
        self.write_bulk(msg)
        self.last_packet_send_time = time.monotonic()
        self.packet_samples = []

    def potentially_send_samples(self):
        if len(self.packet_samples) == const.SAMPLES_PER_PACKET:
            sleep_until(self.last_packet_send_time + const.SAMPLES_PER_PACKET / const.FPS)
            self.send_samples()

    def burn_sample(self, sample):
        intensity = int(sample['intensity'] * self.intensity_differential * const.FPS + self.intensity_minimum * const.FPS)
        # logger.warning('intensity is %s, sample is:%s', intensity, sample)
        for repeat_entry in range(intensity):
            self.packet_samples.append(sample)
            self.potentially_send_samples()
