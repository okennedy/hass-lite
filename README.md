# hass-lite
A lightweight python3 client for [Home-Assistant](http://home-assistant.io/)

Uses websockets to connect to a Home Assistant server, mirrors state locally, and allows client applications to set up callbacks for changes to the state of specific entities.

## Usage

#### Initializing Hass Lite
Initialize a server object
```
server = Hass(host, api_token)
```

Add callbacks
```
server.add_callback('sun.sun', 
  lambda state, attributes: print(f"Sun is {state}")
)
```

#### Running the Client
Start the server with an asyncio coroutine
```
server.monitor()
```

Start the server in an asyncio event loop
```
server.run_event_loop()
```

Start the server in a new thread
```
server.start_thread()
```

#### Directly Accessing State
```
print(server["sun.sun"])
```
