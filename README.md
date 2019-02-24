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
6. `sudo apt-get install git`
7. Authorize your computer with GitHub
    1. create an ssh key on your machine by typing `ssh-keygen -t rsa`; accept the defaults by keep hitting enter.
    2. print out the ssh key by typing cat ~/.ssh/id_rsa.pub
    3. copy key to your clipboard.
    4. copy/paste public key into your github settings here: https://github.com/settings/keys
    5. type in your GitHub password
7. `git clone git@github.com:dlernstrom/laserdock_python.git -o upstream`
8. `sudo apt-get install python3-pip`
9. `cd laserdock_python`
10. `sudo pip3 install -r requirements.txt`
11. `sudo apt-get install libusb-dev`
