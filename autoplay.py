#!/usr/bin/env python2
# -*- coding: utf-8 -*-
'''
Keeps your MPD playlist filled with music you like

Dependencies : python-mpd
               pysqlite
'''

import os.path
import mpd
import random
import sqlite3
import time
import io
import sys
from socket import error as socketerror

## Config
server = "localhost"
port = 6600
password = False # Set to False if none
dbfile = "~/music/.autodb"
trigger = 8 # A new song will be added when the playlist
            #  has less songs than this
            #  You can set this to 0 if you only want the stats
playtime = 70 # Percentage of a song that must be played before
              #  play count is incremented
mintime = 25 # Minimum length of a track for it
             #  to be considered a song
flood_delay = 12*60 # Minutes to wait before adding the same song again
delay = 0.8 # Make this higher if hogging cpu (not likely) 
tries = 3 # Retry connecting this many times

debug = False
logfile = "/tmp/autoplay.log"
## /Config

enc = sys.getfilesystemencoding()

## Functions
def log(msg, stdout=False):
  """Logs to file, and optionally to stdout. Obvious enough"""
  if stdout or debug:
    print msg
  logio.write(unicode(msg, enc)+"\n")

def reconnect(i=1):
  if i == tries:
    log("Could not connect to server D:", stdout=True)
    exit(1)
  log("Tried "+str(i)+" times")
  try:
    client.connect(server, port)
  except socketerror:
    reconnect(i+1)


def addsong():
  """Adds a semi-random song to the playlist"""
  rand = random.uniform(-0.1, 1.5)
  cursor.execute("select * from songs where karma>? and time < ?",
    (rand, int(time.time()-(60*(flood_delay-trigger*3)))))
  data = cursor.fetchall()
  if data == []:
    addsong()
  else:
    songdata = random.choice(data)
    newkarma = karma(songdata, 2)
    cursor.execute(
      "update songs set added=?, karma=?, time=? where file=?",
      (songdata[2]+1, newkarma, int(time.time()), songdata[0],)
    )
    db.commit()
    log(("Adding song "+songdata[0]+" - Karma = "+
      str(songdata[3])+" - Karma limit = "+str(rand)).encode(enc))
    client.add(songdata[0])

def getsong(songfile):
  """Retrieve song data from DB"""
  cursor.execute("select * from songs where file=?", (songfile,))
  data = cursor.fetchone()
  if data == None:
    cursor.execute("insert into songs values (?, 0, 0, 0.5, 0)",
      (songfile,))
    data = (songfile, 0, 0, 0.5, 0)
  return data

def karma(songdata, which=0):
  """Returns karma for a song"""
  listened = float(songdata[1])
  added = float(songdata[2])

  if which == 1:
    listened += 1
  elif which == 2:
    added += 1

  if listened == 0:
    listened = 0.1
  if added == 0:
    added = 0.1
  return listened/added

def listened(songdata):
  newkarma = karma(songdata, 1)
  cursor.execute(
    "update songs set listened=?, karma=?, time=? where file=?",
    (songdata[1]+1, newkarma, int(time.time()), songdata[0])
  )
  log(("Listened to "+songdata[0]+" - Karma = "+
    str(newkarma)+" - Listens = "+str(songdata[1]+1)).encode(enc))
  db.commit()
## /Functions

db = sqlite3.connect(os.path.expanduser(dbfile))
cursor = db.cursor()

random.seed()
client = mpd.MPDClient()

logio = io.open(logfile, "at", buffering=1)
log("\n\nStarted "+str(time.time())+"\n")

log("Connecting...")
try:
  client.connect(server, port)
except socketerror:
  reconnect()

if password:
  try:
    client.password(password)
  except mpd.CommandError:
    log("Wrong password?", stdout=True)
    exit(2)

log("Updating database...")
cursor.execute("create table if not exists songs(\
  file text, listened int, added int, karma real, time int\
  );")
stale = []
for song in cursor.execute("select file from songs"):
  if not os.path.isfile("/home/codl/music/" + song[0]):
    stale.append(song[0])
for song in stale:
  cursor.execute("delete from songs where file=?", (song,))
db.commit()
for song in client.list("file"):
  nothing = getsong(unicode(song, enc))
db.commit()
log("OK! :)")
armed = 1

while __name__ == "__main__":
  if client.status()["consume"] == "0":
    cursongid = client.status()["songid"]
    for song in client.playlistid():
      if song["id"] == cursongid:
        plistlength = int(song["pos"]) + trigger
      
  else:
    plistlength = trigger

  while len(client.playlist()) < plistlength:
    addsong()
  if client.status()['state'] == "play":
    times = client.status()['time'].split(":")
    pos = int(times[0])
    end = int(times[1])
    if armed == 1 and (end > mintime) and (pos > playtime*end/100):
      armed = 0 # Disarm until the next song
      listened(getsong(unicode(client.currentsong()["file"], enc)))
      songid = (client.currentsong()["id"])

    if armed == 0 and not songid == client.currentsong()["id"]: 
      armed = 1
  
  time.sleep(delay)

# vim: tw=70 ts=2 sw=2
