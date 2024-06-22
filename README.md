# HomeAssistant_RTI_Remote
Integrating RTI control systems and RTI remotes as extensions of Home Assistant

## Reason
- Home Assistant is an incredible FOSS home control system that works with almost everything, but it is just software.
- RTI makes incredible hardware, especially Home Theater oriented remotes, but their control system is proprietary and has been surpassed by Home Assistant in my opinion.
- Samsung discontinued their Harmony remote line in 2021, the previous favourite hardware remote owned by Home Assistant users.  As of 2024, there has not been a mass produced direct replacement for Harmony.

This project is my soloution to the above.  Use RTI hardware with Home Assistant Software for the best of both worlds.

## Disclaimers

- Not affiliated with Home Assistant or RTI Control company.

- This project is purely academic, it may not be practical for actual use.

- This not a "driver", "integration" or "addon" for either system.  Without access to the RTI SDK, which requires special approval from RTI, there's no way to make the two systems sync up in a way that 'just works' out of the box.

- RTI systems can only be programmed by authorized parties.

## Architecture

- To showcase the power of choice that comes with Home Assistant, this project uses a combination of Node-Red and Pyscript to interact with the RTI hardware.  Please see `rti.py` for the Pyscript file.

- Most of the time, we want to send commands from RTI to Home Assistant, then have Home Assistant send back data such as device states.  The reverse is also possible which allows us to use RTI's extensive IR or RS232 library and hardware in Home Assistant.

RTI is programmed in a GUI program called "Integration Designer".  We can not write actual code in Integration Designer, so the first step was to find a built-in driver that we can make use of.  I chose to use two "Two Way Strings" drivers: one for Tx and one for Rx.
https://driverstore.rticontrol.com/driver/rti-two-way-strings

To interact with the RTI system, I setup TCP listeners and senders in Node Red on two different ports.
![nodered](https://github.com/mefranklin6/HomeAssistant_RTI_Remote/assets/125914321/2f01a7b0-7757-4f8d-8ed4-7df1ecf6dfb9)

### From RTI to HA
In RTI, we edit the Driver Properties of our Tx "Two Way String" driver and manually make strings that can be easially interperted by the code we write on the Home Assistant side.
I chose `mode:device:action` as a format.

For example:
```
cmd:kitchen_main_lights:on
```
will turn on my kitchen lights.  That gets mapped to a button on a "lighting" page on the remote so RTI sends that string whenever the button is pressed.

This is mapped in the Two-Way Strings driver as:
```
TX (Command) String 1 Name      | kitchen lights on
Command String 1 Paramater Type | No paramater
Command String 1                | cmd:kitchen_main_lights:on
```

Any data received from the RTI processor simply gets turned into an "Event" in Home Assistant by the "Fire Event Node". 

![eventfire](https://github.com/mefranklin6/HomeAssistant_RTI_Remote/assets/125914321/52f1dc86-c2e3-435e-969d-c9561f40305e)

We then subscribe to these events in Pyscript and can process them
```python
@event_trigger("RTI_Rx")
def your_function_here
  # process here
```

Ideally, you would filter the data in Node Red first using function nodes, then fire more granular events using specific topics for Pyscript functions to subscribe to, but I find it faster to have one Pyscript listener and to write the filtering in python.  Please see `rti.py` for examples.

### From HA to RTI
Data is sent back to the RTI processor using another "Two-Way Strings" driver.  I chose the format of `device:state:suffix`.  This function node takes the Home Assistant event and formats it as such:
![strformat](https://github.com/mefranklin6/HomeAssistant_RTI_Remote/assets/125914321/1cf8de5c-217d-4517-9431-c0192f1bea9c)


The RTI driver does not like periods so `light.kitchen_main_lights` entity ID gets converted to `light_kitchen_main_lights` string before being sent.  You can simply have a `State Changed` node listening in Node Red like I have for lights, or you can fire "rti_sync" events in Pyscript that get picked up by the Pyscript event listener node as such:

```python
@state_trigger(LIVINGROOM_FAN)
def send_fan_state(**kwargs):
    speed = state.getattr(LIVINGROOM_FAN)["percentage"]
    event.fire("rti_sync", payload=speed, topic="fan_speed")
```

Then in Integration Designer, you edit the Two-Way Strings driver as such.
```
RX String 1 Name               | fan speed state
RX String 1                    | fan
RX String Variable Type        | Standard (String and Integer variables)
RX String 1 Prefix             | fan_speed:
RX String 1 Suffix             | :state
Rx String 7 Integer Multiplier | 1
```

Please see the RTI documentation for further driver information.



