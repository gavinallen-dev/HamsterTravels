#!/usr/bin/env python3

"""
Collects data from the sensor attached to the Raspberry Pi and saves that data to files.
"""
import sys
import time
import os, os.path
from pathlib import Path
from datetime import timedelta
import datetime
import RPi.GPIO as GPIO
import subprocess
import threading
import math
import requests
import json
import logging
# display-o-tron
import dothat.backlight as backlight
import dothat.lcd as lcd
import dothat.touch as nav
from dot3k.menu import Menu, MenuOption

# Raspberry Pi Pins
magnet_pin = 5     # this is the magnet sensor that triggers when the wheel spin
spare_pin = 7       # this pin should be left unconnected, it's used in GPIO.wait_for_edge to keep the program from ever finishing

# Raspberry Pi GPIO Setup
GPIO.setmode(GPIO.BCM)

GPIO.setup(magnet_pin, GPIO.IN, pull_up_down = GPIO.PUD_DOWN)   # set magnet pin to INPUT
GPIO.setup(spare_pin, GPIO.IN, pull_up_down = GPIO.PUD_UP)      # set spare pin to INPUT

# paths
path_root = "/home/pi/hamster/"
data_dir_live = f"{path_root}data/1_data_live/"    # Files that are currently being written to
data_dir_ready = f"{path_root}data/2_data_ready/"  # Files that are ready to be handled by send_data.py
data_dir_processed = f"{path_root}data/3_data_processed/{datetime.datetime.now().strftime('%Y%m%d')}/"
config_filename = f"{path_root}config.json"

# create process folder for today, if it doesn't exist
Path(data_dir_processed).mkdir(parents = True, exist_ok = True)

#logging
logging.basicConfig(filename = '/home/pi/hamster/error.log', level = logging.DEBUG, format = '%(asctime)s %(levelname)s %(name)s %(message)s')
logger=logging.getLogger(__name__)

# redirect all prints to the logger
#print = logger.info

config_data = {
    "distance_total": 0,
    "rotations_total": 0,
    "speed_average": 0,
    "time_total": 0,
    "distance_current": 0,
    "rotations_current": 0
}

# thingspeak
thingspeak_channel_id = {channel_id}
thingspeak_api_key = "{write_api_key}"

# Initialize hamster tracker
sprint_is_active = False
current_file_name = ''
wheel_circumference = math.pi * {wheel_circumference} # meters

def do_shutdown(doShutdown):
    # start a clean shutdown

    display_show("Starting Shutdown...", "", "", True)
    time.sleep(1)

    stop_timer(sprint_end_timer)
    stop_timer(send_files_timer)

    # stop sprint
    print("stop")
    display_show("Starting Shutdown...", "Stopping Sprint...", "", True)
    sprint_end()
    time.sleep(1)

    # send files
    print("send")
    display_show("Starting Shutdown...", "Sending Files...", "", True)
    do_send_files()
    time.sleep(1)

    write_config()
    display_show("Starting Shutdown...", "Writing Config...", "", True)
    time.sleep(1)

    if doShutdown:
        # shutdown        
        print("shutdown")
        display_show("Starting Shutdown...", "Shutting Down...", "", True)
        time.sleep(1)
        display_sleep()
        os.system("sudo shutdown -h now")
        GPIO.cleanup()
    else:
        print("don't shutdown")
        display_show("Starting Shutdown...", "Stopping Shutdown", "", True)

def magnet_ping(channel):
    print("magnet_ping")
    global sprint_end_timer
    global sprint_is_active
    global current_file_name
    global data_file

    stop_timer(sprint_end_timer)

    # If we don't have an active sprint, we need to start one and create a new file
    if not sprint_is_active:
        sprint_is_active = True
        current_file_name = 'raw_data_{}'.format(time.strftime("%Y%m%d-%H%M%S"))
        data_file = open(data_dir_live + current_file_name, 'w')
        print("Sprint Starting. Opening file: {}".format(data_file.name))
    
    values = {}
    values["time"] = time.time()

    json.dump(values, data_file)
    data_file.write("\n")

    # restart the timer
    sprint_end_timer = start_timer(sprint_end_timer_interval, sprint_end_timer_callback)

def sprint_end():
    global sprint_is_active
    global current_file_name

    if sprint_is_active:
        print("Sprint Ending. Closing file.")
        sprint_is_active = False
        # Move the finished sprint file to the "ready" directory
        data_file.close()
        os.rename(data_dir_live + current_file_name, data_dir_ready + current_file_name)
        current_file_name = ''

def send_files():
    # the timer has triggered a send of files, so send and reschedule
    global send_files_timer
    
    stop_timer(send_files_timer)

    do_send_files()

    send_files_timer = start_timer(send_files_timer_interval, send_files_timer_callback)

def get_formatteddate_from_time(timeValue):
    return datetime.datetime.fromtimestamp(timeValue).strftime("%Y-%m-%d %H:%M:%S")

def do_send_files():
    # read all ready files and transmit data to ThingSpeak
    global request_data

    # periodically write the config so it doesn't get lost if it all goes wrong
    write_config()

    print ("checking for files")

    updates = []
    readFiles = []
    sent_times = []

    for data_file in sorted(Path(data_dir_ready).iterdir(), key=os.path.getmtime):
        if data_file.name.startswith('raw_'):

            print(f"reading file: {data_file.name}")

            # Count the number of wheel rotations in the sprint
            sprint_start_time = None
            sprint_end_time = None
            rotations = 0

            with open(data_dir_ready + data_file.name) as f:
                print("file open")
                 
                for line in f:
                    print("reading line")
                    line_json = json.loads(line)
                    print(line_json)
                    if not sprint_start_time:
                        sprint_start_time = line_json["time"]
                    
                    sprint_end_time = line_json["time"]
                    rotations = rotations + 1

            if rotations > 0:
                # convert wheel rotations to distance
                meters = rotations * wheel_circumference

                # update the config object
                config_data["rotations_total"] += rotations
                config_data["distance_total"] += meters
                config_data["distance_current"] += meters
                config_data["rotations_current"] += rotations
                config_data["speed_average"] = None;

                print(meters)
                print(config_data["distance_current"])
            
                config_data["time_total"] += round(sprint_end_time - sprint_start_time)
                #if config_data["time_total"] > 0:
                #    config_data["speed_average"] = config_data["distance_total"] / config_data["time_total"]

                # calculate average just for the sprint, there is too much inaccuracy because of the gaps within the spring period, which means that the total average alwayys tends towards 0!
                if (rotations > 5) and (sprint_end_time - sprint_start_time) > 0:
                    config_data["speed_average"] = meters / (sprint_end_time - sprint_start_time)


                # Send the data to ThingSpeak
                if not round(sprint_start_time) in sent_times:
                    sent_times.append(round(sprint_start_time))
                    updates.append({
                        'created_at': round(sprint_start_time),
                        'field1': rotations,
                        'field2': meters,
                        'field6': config_data["speed_average"],
                        'field7': config_data["rotations_total"],
                        'field8': config_data["distance_total"],
                    })

            # log the file that has been read
            readFiles.append(data_file.name)
    
    if len(updates) > 0:
        request_data = {
            'write_api_key': thingspeak_api_key,
	        'updates': updates
        }
        request_data_json = json.dumps(request_data)
        print(f"Sending to ThingSpeak: Params {request_data_json}")

        url = f"https://api.thingspeak.com/channels/{thingspeak_channel_id}/bulk_update.json"
        headers = {"Content-type": "application/json", "Accept": "text/plain"}
        r = requests.post(url, data=request_data_json, headers=headers)
        
        print(f"sent: {r.status_code} {r.text}")
        print(r)

        if (r.status_code == 200) or (r.status_code == 202):
            archive_files(readFiles)
        else:
            print(f"Failed to send data to ThingSpeak: {r.status_code} {r.text}")
            print(f"Failed to send data to ThingSpeak: {r.status_code} {r.text}")
    else:
        archive_files(readFiles)

    # Prevent us from hitting ThingSpeak's throttles
    time.sleep(15)

def archive_files(readFiles):
    # copy all read files to the processed folder

    if len(readFiles) > 0:
        print(readFiles)
        print("archiving sent files")

    # Move finished files to the "processed" directory
    for data_file in readFiles:
        print(f"Moving file {data_dir_ready}{data_file} to {data_dir_processed}{data_file}")
        os.rename(data_dir_ready + data_file, data_dir_processed + data_file)

def stop_timer(timer):
    # stop a timer

    if timer is not None:
        timer.cancel()

def start_timer(interval, callback):
    # start and return a timer

    timer = threading.Timer(interval, callback)
    timer.daemon = True
    timer.start()

    return timer

def read_config():
    # load the total rotations and average speed from the config
    global config_data

    # check if config file exists
    if os.path.isfile(config_filename):
        # load config
        with open(config_filename) as config_file:
            config_data = json.load(config_file)

    config_data["distance_current"] = 0
    config_data["rotations_current"] = 0

def write_config():
    # save  the total rotations and average speed from the config
    global config_data

    # write config to file
    with open(config_filename, 'w') as config_file:
        json.dump(config_data, config_file, indent = 4)

# MENU ACTIONS

class MenuActions(MenuOption):
    def __init__(self, action):
        self.last_update = self.millis()
        self.action = action
        MenuOption.__init__(self)

    def cleanup(self):
        print ('menu cleanup')

    def begin(self):
        print ('menu begin')
        if self.action == "display_sleep":
            display_sleep()
        elif self.action == "action_Shutdown":
            action_Shutdown()
        elif self.action == "display_CurrentRotations":
            display_CurrentRotations()
        elif self.action == "display_CurrentDistance":
            display_CurrentDistance()
        elif self.action == "display_TotalDistance":
            display_TotalDistance()
        elif self.action == "display_TotalRotations":
            display_TotalRotations()
        elif self.action == "display_AverageSpeed":
            display_AverageSpeed()
        elif self.action == "display_LiveFiles":
            display_LiveFiles()
        elif self.action == "display_ReadyFiles":
            display_ReadyFiles()
        elif self.action == "display_ProcessedFiles":
            display_ProcessedFiles()
        elif self.action == "display_Files":
            display_Files()
    
def action_Shutdown():
    # do an actual shutdown
    do_shutdown(True)

def display_sleep():
    # turn the screen off
    print ("sleep")
    display_show("", "", "", False)

def display_show(text1, text2, text3, light):
    print ("display_show")
    
    if light:
        backlight.rgb(0, 100, 0)
    else:
        backlight.off()

    menu.write_row(0, text1)
    menu.write_row(1, text2)
    menu.write_row(2, text3)

def file_count(path):
    return len([name for name in os.listdir(path) if os.path.isfile(os.path.join(path, name))])

def display_CurrentRotations():
    display_show("Current Rotations", str(config_data["rotations_current"]), "", True)

def display_CurrentDistance():
    display_show("Current Distance", str(config_data["distance_current"]), "", True)

def display_TotalDistance():
    display_show("Total Distance", str(config_data["distance_total"]), "", True)

def display_TotalRotations():
    display_show("Total  Rotations", str(config_data["rotations_total"]), "", True)

def display_AverageSpeed():
    display_show("Average Speed", str(config_data["speed_average"]), "", True)

def display_LiveFiles():
    display_show("Live File Count", str(file_count(data_dir_live)), "", True)

def display_ReadyFiles():
    display_show("Ready  File Count", str(file_count(data_dir_ready)), "", True)

def display_ProcessedFiles():
    display_show("Prc File Count", str(file_count(data_dir_processed)), "", True)

def display_Files():
    display_show("Live - Rdy - Prc", str(file_count(data_dir_live)) + " - " + str(file_count(data_dir_ready)) + " - " + str(file_count(data_dir_processed)), "", True)

def menu_redraw():
    menu.redraw()

# initialise timers
sprint_end_timer = None
sprint_end_timer_interval = 5
sprint_end_timer_callback = sprint_end

send_files_timer = None
send_files_timer_interval = 10 * 60     # 10 minutes
send_files_timer_callback = send_files

menu_redraw_timer = None
menu_redraw_timer_interval = 1           # 1 second
menu_redraw_timer_callback = menu_redraw

# GPIO events

GPIO.add_event_detect(magnet_pin, GPIO.RISING, callback = magnet_ping, bouncetime = 300) 

# timers

send_files_timer = start_timer(send_files_timer_interval, send_files_timer_callback)

menu_redraw_timer = start_timer(menu_redraw_timer_interval, menu_redraw_timer_callback)

# load from config
read_config()

class BacklightIdleTimeout(MenuOption):
    def __init__(self, backlight):
        self.backlight = backlight
        self.r = 0
        self.g = 100
        self.b = 0
        MenuOption.__init__(self)

    def setup(self, config):
        self.config = config

        self.r = int(self.get_option('Backlight', 'r', 0))
        self.g = int(self.get_option('Backlight', 'g', 100))
        self.b = int(self.get_option('Backlight', 'b', 0))

    def cleanup(self):
        print("Idle timeout expired. Turning on backlight!")
        self.backlight.rgb(self.r, self.g, self.b)

    def begin(self):
        print("Idle timeout triggered. Turning off backlight!")
        self.backlight.rgb(0, 0, 0)
        display_show("", "", "", False)

backlight_idle = BacklightIdleTimeout(backlight)

# Initialize display-o-tron
menu = Menu(
    {
        'Display': {
            'Files': MenuActions("display_Files"),
            'Current Rotations': MenuActions("display_CurrentRotations"),
            'Current Distance': MenuActions("display_CurrentDistance"),
            'Total Distance': MenuActions("display_TotalDistance"),
            'Total Rotations': MenuActions("display_TotalRotations"),
            'Average Speed': MenuActions("display_AverageSpeed"),
            'Live Files': MenuActions("display_LiveFiles"),
            'Ready Files': MenuActions("display_ReadyFiles"),
            'Processed Files': MenuActions("display_ProcessedFiles")
        },
        'Shutdown': MenuActions("action_Shutdown")
    },
    lcd,  # Draw to dot3k.lcd
    idle_handler = backlight_idle,
    idle_time = 10
)

backlight_idle.setup(menu.config)

def wake_screen():
    menu.redraw()
    backlight.rgb(0, 100, 0)

@nav.on(nav.UP)
def handle_up(ch, evt):
    wake_screen()
    menu.up()

@nav.on(nav.CANCEL)
def handle_cancel(ch, evt):
    wake_screen()
    menu.cancel()

@nav.on(nav.DOWN)
def handle_down(ch, evt):
    wake_screen()
    menu.down()

@nav.on(nav.LEFT)
def handle_left(ch, evt):
    wake_screen()
    menu.left()

@nav.on(nav.RIGHT)
def handle_right(ch, evt):
    wake_screen()
    menu.right()

@nav.on(nav.BUTTON)
def handle_button(ch, evt):
    wake_screen()
    menu.select()

def my_except_hook(exctype, value, traceback):
    if exctype == KeyboardInterrupt:
        print ("KeyboardInterrupt")
        do_shutdown(False)
    else:
        logger.critical("Uncaught exception", exc_info=(exctype, value, traceback))

        print("Cleaning up")
        do_shutdown(False)
        sys.__excepthook__(exctype, value, traceback)

sys.excepthook = my_except_hook

print("Waiting for falling edge on unconnected pin")  
wake_screen()
menu.run()  # start the menu
menu_on = True
GPIO.wait_for_edge(spare_pin, GPIO.FALLING)  
print("This should never happen" )

