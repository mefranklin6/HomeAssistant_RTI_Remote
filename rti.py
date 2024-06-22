"""Example Pyscript file to interact with RTI hardware"""

from media_player_helper import MediaPlayerHelper
from light_helper import LightHelper
from constants import (
    AVR,
    LIVINGROOM_FAN,
    THERMOSTAT,
    SHELF_STRIP,
    LIVINGROOM_LAMP,
    KITCHEN_MAIN_LIGHTS,
    LIVINGROOM_TV,
    WINDOWS,
    DOORS,
    ALARM_SWITCH,
)


# RTI command mapped to AVR input name (AVR Dynamically names inputs based on CEC)
avr_input = {"bluray": "UBP-X800", "streamer": "Roku Ultra", "pc": "8K"}

# RTI command device names mapped to HA entity_id's
# State change updates for these lights are handled in Node-RED
rti_tracked_lights = {
    "shelf_strip": SHELF_STRIP,
    "livingroom_lamp": LIVINGROOM_LAMP,
    "kitchen_main_lights": KITCHEN_MAIN_LIGHTS,
}


def thermostat_info():
    mode = state.get(THERMOSTAT)
    data = state.getattr(THERMOSTAT)
    current_temp = data["current_temperature"]
    desired_temp = data["temperature"]
    return str(mode), str(current_temp), str(desired_temp)


def send_thermostat_states():
    mode, current_temp, desired_temp = thermostat_info()
    event.fire("rti_sync", payload=mode, topic="thermostat_mode")
    task.sleep(0.5)
    event.fire("rti_sync", payload=current_temp, topic="thermostat_current_temp")
    task.sleep(0.5)
    event.fire("rti_sync", payload=desired_temp, topic="thermostat_desired_temp")


def send_security_states():
    open_doors = []
    for door in DOORS:
        if state.get(door) == "on":
            open_doors.append(state.getattr(door)["friendly_name"])

    open_windows = []
    for window in WINDOWS:
        if state.get(window) == "on":
            open_windows.append(state.getattr(window)["friendly_name"])

    if len(open_doors) == 0:
        open_doors = "All Doors Closed"

    if len(open_windows) == 0:
        open_windows = "All Windows Closed"

    event.fire("rti_sync", payload=str(state.get(ALARM_SWITCH)), topic="alarm_switch")
    task.sleep(0.5)
    event.fire("rti_sync", payload=str(open_doors), topic="open_doors")
    task.sleep(0.5)
    event.fire("rti_sync", payload=str(open_windows), topic="open_windows")


def send_all_states():
    # RTI will request this on connection, which may be after reboot or RTI or HA
    # so we add in a delay to ensure both parties are ready
    task.sleep(5)

    tv_helper = MediaPlayerHelper()
    if tv_helper.livingroom_system_is_on():
        task.sleep(0.5)
        event.fire("rti_sync", payload="on", topic="system_home_theater")
    else:
        task.sleep(0.5)
        event.fire("rti_sync", payload="off", topic="system_home_theater")

    for light_id in rti_tracked_lights.values():
        task.sleep(0.5)
        device_state = state.get(light_id)
        event.fire("rti_sync", payload=device_state, topic=light_id)

    task.sleep(0.5)
    send_thermostat_states()
    task.sleep(0.5)
    send_security_states()


def handle_fan_call():
    fan_state = state.get(LIVINGROOM_FAN)
    if fan_state == "on":
        fan.turn_off(entity_id=LIVINGROOM_FAN)
        return

    else:
        indoor_temp = thermostat_info()[1]
        indoor_temp = int(indoor_temp)
        if indoor_temp > 80:
            speed = 100
        elif indoor_temp > 75:
            speed = 75
        else:
            speed = 50

        fan.set_percentage(entity_id=LIVINGROOM_FAN, percentage=speed)


def handle_toggle_command(device):
    if device in rti_tracked_lights.keys():
        ha_entity = rti_tracked_lights[device]
        if ha_entity.startswith("light"):
            light.toggle(entity_id=rti_tracked_lights[device])
        elif ha_entity.startswith("switch"):
            switch.toggle(entity_id=rti_tracked_lights[device])

    if device == "fan":
        handle_fan_call()


def handle_avr(command):
    if command == "volup":
        media_player.volume_up(entity_id=AVR)
        return

    if command == "voldown":
        media_player.volume_down(entity_id=AVR)
        return

    if command == "mute":
        mute_state = state.getattr(AVR)["is_volume_muted"]
        media_player.volume_mute(entity_id=AVR, is_volume_muted=not mute_state)
        return

    if command in ["on", "off"]:
        tv_helper = MediaPlayerHelper()
        if command == "on":
            tv_helper.livingroom_system_on()
        else:
            tv_helper.livingroom_system_off()
        return

    source_list = hass.states.get(AVR).attributes.get("source_list")

    if command in avr_input:
        if avr_input[command] in source_list:
            media_player.select_source(entity_id=AVR, source=avr_input[command])
        else:
            log.warning(f"Source not found: {avr_input[command]}")
    else:
        log.warning(f"Unknown input command: {command}")


def process_command_received(device, command):

    # Requested by RTI on connection established
    if device == "states" and command == "get":
        send_all_states()

    elif device == "thermostat" and command == "get":
        send_thermostat_states()

    elif device == "doorswindows" and command == "get":
        send_security_states()

    elif device == "avr" or device == "home_theater":
        handle_avr(command)

    elif command == "light_preset":
        if device == "alloff":
            light_helper = LightHelper()
            light_helper.all_lights_off()

        if device == "bedtime":
            service.call("pyscript", "bedtime")

    elif command == "toggle":
        handle_toggle_command(device)

    else:
        log.warning(f"Unknown command from RTI: cmd:{device}:{command}")


@state_trigger(AVR)
@state_trigger(LIVINGROOM_TV)
def home_theater_state_changed(**kwargs):
    tv_helper = MediaPlayerHelper()
    if tv_helper.livingroom_system_is_on():
        event.fire("rti_sync", payload="on", topic="system_home_theater")
    else:
        event.fire("rti_sync", payload="off", topic="system_home_theater")


@state_trigger(LIVINGROOM_FAN)
def send_fan_state(**kwargs):
    speed = state.getattr(LIVINGROOM_FAN)["percentage"]
    event.fire("rti_sync", payload=speed, topic="fan_speed")


@event_trigger("RTI_Rx")
def rti_message_received(**kwargs):
    try:
        payload = kwargs["payload"]

        split = payload.split(":")
        mode = split[0]
        device = split[1]
        command = split[2]

        if mode == "cmd":
            process_command_received(device, command)
        else:
            log.warning(f"Unknown mode: {mode}")

    except Exception as e:
        log.error(f"Error processing RTI command: {e}")
