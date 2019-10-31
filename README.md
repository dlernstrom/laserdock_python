1. `cd ~/projects`
2. `mkdir laserdock`
3. `cd laserdock`
4. Made a virtualenv manually: `virtualenv venv --python=/blehblehbleh`
5. activated it via `source venv/bin/activate`
6. `pip install -r requirements.txt`
7. found out I don't have libusb, so I homebrew installed it `brew install libusb`


## Make RPi Burner
1. Make a RPi Lite Burn
2. Enable for SSH
3. SSH into device
4. `sudo apt-get update`
5. `sudo apt-get upgrade`
6. `sudo apt-get install git screen python3-pip libopenjp2-7 libtiff5`
7. Authorize your computer with GitHub
    1. create an ssh key on your machine by typing `ssh-keygen -t rsa`; accept the defaults by keep hitting enter.
    2. print out the ssh key by typing cat ~/.ssh/id_rsa.pub
    3. copy key to your clipboard.
    4. copy/paste public key into your github settings here: https://github.com/settings/keys
    5. type in your GitHub password
7. `git clone git@github.com:dlernstrom/laserdock_python.git -o upstream`
8. `cd laserdock_python`
9. `sudo pip3 install -r requirements.txt`
10. `sudo apt-get install libusb-dev`
11. `screen -R`  Reattaches if possible, otherwise restarts
12. `sudo python3 border_parser.py`


Got this weird error once:
Traceback (most recent call last):
  File "halloween_2019.py", line 62, in <module>
    dock.burn_sample(sample)
  File "/home/pi/laserdock_python/laserdock/laser_dock.py", line 260, in burn_sample
    self.potentially_send_samples()
  File "/home/pi/laserdock_python/laserdock/laser_dock.py", line 253, in potentially_send_samples
    self.send_samples()
  File "/home/pi/laserdock_python/laserdock/laser_dock.py", line 240, in send_samples
    self.write_bulk(msg)
  File "/home/pi/laserdock_python/laserdock/laser_dock.py", line 97, in write_bulk
    self.dev[0][(1, 0)][0].write(msg)
  File "/usr/local/lib/python3.7/dist-packages/usb/core.py", line 387, in write
    return self.device.write(self, data, timeout)
  File "/usr/local/lib/python3.7/dist-packages/usb/core.py", line 948, in write
    self.__get_timeout(timeout)
  File "/usr/local/lib/python3.7/dist-packages/usb/backend/libusb1.py", line 855, in iso_write
    handler = _IsoTransferHandler(dev_handle, ep, data, timeout)
  File "/usr/local/lib/python3.7/dist-packages/usb/backend/libusb1.py", line 664, in __init__
    self.__set_packets_length(length, packet_length)
  File "/usr/local/lib/python3.7/dist-packages/usb/backend/libusb1.py", line 689, in __set_packets_length
    _lib.libusb_set_iso_packet_lengths(self.transfer, packet_length)
  File "/usr/local/lib/python3.7/dist-packages/usb/backend/libusb1.py", line 499, in libusb_set_iso_packet_lengths
    for iso_packet_desc in _get_iso_packet_list(transfer):
  File "/usr/local/lib/python3.7/dist-packages/usb/backend/libusb1.py", line 268, in _get_iso_packet_list
    list_type = _libusb_iso_packet_descriptor * transfer.num_iso_packets
ValueError: Array length must be >= 0, not -5
