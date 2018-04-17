#!/usr/bin/env python

try:
    import RPi.GPIO as GPIO
    nonPi = False
    print "Running on a PI, using GPIO"
except:
    nonPi = True
    print "Running in mock PI mode"

import time
import socket
import requests
from icalevents.icalevents import events

channel1        = 26
channel2        = 20
channel3        = 21
heatingState    = None
frostTemp       = 10
calendarUrl     = "http://calendar.com/dave.ics"
graphiteUrl     = "http://graphite/render/?target=data.frontroom.temp.sensor1.celcius&from=-5minutes&format=json"
graphiteServer  = "graphite"
stateOid        = "heating.state"
deltaOid        = "heating.delta"
eventOid        = "heating.event"
frostOid        = "heating.frost"
metrics         = []
if nonPi is False:
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(channel1, GPIO.OUT)
    GPIO.setup(channel2, GPIO.OUT)
    GPIO.setup(channel3, GPIO.OUT)

    # disconnect the real controller
    GPIO.output(channel1, GPIO.LOW)

def pushToGraphite(graphiteStrings):
    '''Takes an array of strings and pushes them to graphite
    '''
    print graphiteStrings 
    connection = socket.socket()
    connection.connect((graphiteServer, 2003))
    for update in graphiteStrings:
        connection.send(update)
    connection.close()


def heatingOn():
    '''Partially a wrapper to avoid running a thickarsed emulator
    and partially a nasty-arsed helper function to turn shit off/on
    '''
    heatingState = True
    metrics.append("{0} 1 {1}\n".format(stateOid, time.time()))
    if nonPi:
        return True
    # now turn on the actual heatin
    GPIO.output(channel2, GPIO.LOW)

def heatingOff():
    '''other way round
    '''
    print "heating off"
    metrics.append("{0} 0 {1}\n".format(stateOid,time.time()))
    heatingState = False 
    if nonPi:
        return True
    GPIO.output(channel2, GPIO.HIGH)

heatingEvents = events(calendarUrl)

r = requests.get(url=graphiteUrl)
currentTemp = None
if r.ok:
    rawThermData =  r.json()
    sortedDataPoints = reversed(rawThermData[0]['datapoints'])
    for datum in sortedDataPoints:
        if datum[0] is not None:
            currentTemp = datum[0]
            break
else:
    print "big fucking error mate"

for heatTime in heatingEvents:
    if heatTime.time_left().total_seconds() <= 0:
        print "heating event"
        metrics.append("{0} 1 {1}\n".format(eventOid, time.time()))
        try:
            targetTemp = float(heatTime.summary)
        except ValueError:
            targetTemp = 18.5
        # report the delta between target and actual
        metrics.append("{0} {1} {2}\n".format(deltaOid, targetTemp - currentTemp, time.time()))
        if currentTemp < targetTemp:
            heatingOn()
        else:
            heatingOff()
        # Why is this here? partially to stop rapid on/off when going through events
        # but also it means that if there is nothing, the heat defaults to off
        # which is crucial otherwise the heating would never turn off
        break
else:
    ##
    # Frost protection
    ##
    if currentTemp < frostTemp:
        print "FUCK ITS COLD"
        metrics.append("{0} 1 {1}\n".format(frostOid, time.time()))
        heatingOn()
    else:
        metrics.append("{0} 0 {1}\n".format(eventOid, time.time()))
        heatingOff()
try:
    pushToGraphite(metrics)
except Exception:
    print "Cannot push to graphite"
