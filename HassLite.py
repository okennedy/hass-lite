#!/bin/env python3

import asyncio
import asyncws
import json
from threading import Thread
from os.path import expanduser

class Hass:
  def __init__(self, host, token):
    self.host = host
    self.token = token
    self.websocket = None
    self.msg_id = 1
    self.handlers = {}
    self.state = {}
    self.global_callbacks = []

  def __getitem__(self, entity):
    return self.state[entity]
  
  def add_callback(self, callback, entity = None):
    if entity == None:
      self.global_callbacks += [callback]
    else:
      if entity not in self.state:
        self.state[entity] = HassEntity(None, None)
      self.state[entity].add_callback(callback)

  @asyncio.coroutine
  def send_json(self, msg):
    yield from self.websocket.send(json.dumps(msg))

  @asyncio.coroutine
  def send_command(self, msg, handler = None):
    command_id = self.msg_id
    self.msg_id += 1
    msg = { 
      "id" : command_id,
      **msg
    }
    if handler != None:
      self.handlers[command_id] = handler
    yield from self.send_json(msg)

  @asyncio.coroutine
  def login(self):
    yield from self.send_json({
        "type" : "auth",
        "api_password" : self.token
      })

  def process_state_record(self, record, skip_insert_if_exists = False):
    entity = record["entity_id"]
    state = record["state"]
    attributes = record.get("attributes", None)
    if entity not in self.state:
      self.state[entity] = HassEntity(state, attributes)
    elif not skip_insert_if_exists or self.state[entity].state == None: 
      self.state[entity].update(state, attributes)
    for cb in self.global_callbacks:
      cb(entity, self.state[entity])

  def delete_state(self, entity):
    if entity in self.state:
      del self.state[entity]

  def handle_event(self, event):
    event_type = event["event_type"]
    if event_type == "state_changed": 
      new_state = event["data"]["new_state"]
      if new_state == None:
        self.delete_state(event["data"]["entity_id"])
      else:
        self.process_state_record(new_state)
    else:
      print(event)

  @asyncio.coroutine
  def subscribe_events(self):
    yield from self.send_command({
        "type": "subscribe_events"
      })

  def finish_load_state(self, state):
    for record in state:
      self.process_state_record(record, skip_insert_if_exists = True)

  @asyncio.coroutine
  def load_state(self):
    yield from self.send_command({
        "type": "get_states"
      }, 
      lambda result: self.finish_load_state(result)
    )

  @asyncio.coroutine
  def maintain(self):
    if self.websocket == None:
      self.websocket = yield from asyncws.connect(self.host)
    while True:
      msg = yield from self.websocket.recv()
      if msg is None:
        self.websocket = None
        break
      msg = json.loads(msg)
      event = msg["type"]
      if event == "auth_required":
        yield from self.login()
      elif event == "auth_ok":
        yield from self.subscribe_events()
        yield from self.load_state()
      elif event == "auth_invalid":
        raise Exception(event["message"])
      elif event == "event":
        self.handle_event(msg["event"])
      elif event == "result":
        if msg["success"] == True:
          handler = self.handlers.get(msg["id"], None)
          if handler != None:
            handler(msg["result"])
        else:
          print(event)

  def run_event_loop(self, loop = asyncio.get_event_loop()):
    loop.run_until_complete(self.maintain())
    loop.close()

  def run_threaded_event_loop(self):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    self.run_event_loop(loop)

  def start_thread(self):
    try:
      thread = Thread(
        target = self.run_threaded_event_loop
      )
      thread.daemon = True
      thread.start()
    except Exception as e:
      import traceback
      print(traceback.format_exc())
      exit(-1)

class HassEntity:
  def __init__(self, state, attributes):
    self.state = state
    self.attributes = attributes
    self.callbacks = []

  def state(self):
    return self.state

  def attributes(self):
    return self.attributes

  def update(self, state, attributes = None):
    self.state = state;
    if attributes != None:
      self.attributes = attributes
    for cb in self.callbacks:
      cb(self.state, self.attributes)

  def add_callback(self, callback):
    self.callbacks += [callback]

if __name__ == "__main__":
  with open(expanduser("~/.hass_api")) as config_file:
    config = json.load(config_file)
    state = Hass(config["host"], config["api_key"])
    add_callback = lambda entity, fmt: (
      state.add_callback(
        lambda state, attributes: print(fmt.format(state = state, attributes = attributes)),
        entity = entity
      ))
    if "callbacks" in config:
      for cb in config["callbacks"]:
        add_callback(cb["entity_id"], cb["format_string"])
    # state.run_event_loop()
    state.start_thread()
