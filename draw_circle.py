from math import cos, sin, pi

from laserdock_python.laserdock.laser_dock import LaserDock


def float_to_laserdock_xy(val):
    """The Laserdock has a resolution of 4096x4096.  This method converts a grid ranging from:
    -1<=x<=1 and -1<=y<=1
    to
    0<=x<=4095 and 0<=y<=4095
    """
    result = int(4095.0 * (val + 1.0) / 2.0)
    return result


class CircleBuffer(object):
    def __init__(self, circle_steps):
        self._current_position = 0
        self._circle_steps = circle_steps
        self._buffer_elements = circle_steps * 2
        self._buffer = self._buffer_elements * [0]
        step_f = 2.0 * pi / circle_steps

        counter = 0
        while counter < circle_steps:
            x_f = cos(counter * step_f)
            y_f = sin(counter * step_f)
            self._buffer[counter * 2] = float_to_laserdock_xy(x_f)
            self._buffer[counter * 2 + 1] = float_to_laserdock_xy(y_f)
            counter += 1

    def fill_samples(self, samples_per_packet=64):
        counter = 0
        samples = []
        while counter < samples_per_packet:
            samples.append({'x': self._buffer[2 * self._current_position],
                            'y': self._buffer[2 * self._current_position + 1],
                            'r': 100,
                            'g': 0,
                            'b': 100})
            counter += 1
            self._current_position += 1
            if self._current_position >= self._circle_steps:
                self._current_position = 0
        return samples


if __name__ == '__main__':
    a = LaserDock()
    buffer = CircleBuffer(circle_steps=3000)
    samples_per_pkt = 64
    while True:
        packet_samples = buffer.fill_samples(samples_per_packet=samples_per_pkt)
        a.send_samples(packet_samples)
