import variables
from constants import (
    ALARM_SWITCH,
    AVR,
    DOORS,
    KITCHEN_MAIN_LIGHTS,
    LIVINGROOM_FAN,
    LIVINGROOM_LAMP,
    LIVINGROOM_TV,
    ROKU,
    SHELF_STRIP,
    THERMOSTAT,
    TV_BRIGHTNESS,
    WINDOWS,
)
from light_helper import LightHelper
from media_player_helper import MediaPlayerHelper

# Home Assistant event type that our Node Red listener is subscribed to
RTI_EVENT_KEYWORD = "rti_sync"

# The TV input that the AVR output is connected to
TV_AVR_INPUT = "HDMI-2"

TV_ANTENNA_SOURCE_NAME = "TV"

# RTI command mapped to AVR input name (Denon AVR Dynamically names inputs based on CEC)
AVR_INPUT = {"bluray": "UBP-X800", "streamer": "Roku Ultra", "pc": "8K"}

# RTI command device names mapped to HA entity_id's
# State change updates for these lights are handled in Node-RED
rti_tracked_lights = {
    "shelf_strip": SHELF_STRIP,
    "livingroom_lamp": LIVINGROOM_LAMP,
    "kitchen_main_lights": KITCHEN_MAIN_LIGHTS,
}


def fire_rti_event(payload, topic):
    """
    Use this to send data back to the RTI controller
    This fires a Home Assistant event which is picked up in the Node Red flow
    """
    event.fire(RTI_EVENT_KEYWORD, payload=payload, topic=topic)
    task.sleep(0.5)


def _thermostat_info():
    mode = state.get(THERMOSTAT)
    data = state.getattr(THERMOSTAT)
    current_temp = data["current_temperature"]
    desired_temp = data["temperature"]
    return str(mode), str(current_temp), str(desired_temp)


def send_thermostat_states():
    mode, current_temp, desired_temp = _thermostat_info()
    fire_rti_event(payload=mode, topic="thermostat_mode")
    fire_rti_event(payload=current_temp, topic="thermostat_current_temp")
    fire_rti_event(payload=desired_temp, topic="thermostat_desired_temp")


def send_security_states():
    open_doors = []
    for door in DOORS:
        if state.get(door) == "on":
            open_doors.append(state.get(f"{door}.friendly_name"))

    open_windows = []
    for window in WINDOWS:
        if state.get(window) == "on":
            open_windows.append(state.get(f"{window}.friendly_name"))

    if len(open_doors) == 0:
        open_doors = "All Doors Closed"

    if len(open_windows) == 0:
        open_windows = "All Windows Closed"

    fire_rti_event(payload=str(state.get(ALARM_SWITCH)), topic="alarm_switch")
    fire_rti_event(payload=str(open_doors), topic="open_doors")
    fire_rti_event(payload=str(open_windows), topic="open_windows")


def send_all_states():
    # RTI will request this on connection, which may be after reboot or RTI or HA
    # so we add in a delay to ensure both parties are ready
    task.sleep(5)

    tv_helper = MediaPlayerHelper()
    if tv_helper.livingroom_system_is_on():
        fire_rti_event(payload="on", topic="system_home_theater")
    else:
        fire_rti_event(payload="off", topic="system_home_theater")

    for light_id in rti_tracked_lights.values():
        device_state = state.get(light_id)
        fire_rti_event(payload=device_state, topic=light_id)

    send_thermostat_states()
    send_security_states()


def handle_fan_toggle():
    fan_state = state.get(LIVINGROOM_FAN)
    if fan_state == "on":
        fan.turn_off(entity_id=LIVINGROOM_FAN)
        return

    else:
        indoor_temp = _thermostat_info()[1]
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

    elif device == "fan":
        handle_fan_toggle()


def _update_tv_picture_mode(mode):
    if mode == "pc":
        setting_name = "picture_mode"
        new_value = "Game"

    else:
        setting_name = "picture_mode"
        new_value = "Calibrated Dark"

    # the tv will execute the command even if the value is the same
    # so this checks the assumed value before sending the command
    if variables.tv_picture_mode == new_value:
        return

    vizio.update_setting(
        entity_id=LIVINGROOM_TV,
        setting_type="picture",
        setting_name=setting_name,
        new_value=new_value,
    )
    # pyvizio does not provide picture mode feedback, so we need to track assumed state
    variables.tv_picture_mode = new_value


def update_tv_brightness(percentage):
    input_number.set_value(entity_id=TV_BRIGHTNESS, value=percentage)


def avr_mute_toggle():
    mute_state = state.get(f"{AVR}.is_volume_muted")
    media_player.volume_mute(entity_id=AVR, is_volume_muted=not mute_state)


def tv_antenna_macro():
    try:
        if state.getattr(LIVINGROOM_TV)["source"] != TV_ANTENNA_SOURCE_NAME:
            media_player.select_source(
                entity_id=LIVINGROOM_TV, source=TV_ANTENNA_SOURCE_NAME
            )
    except KeyError:
        return  # TV is off
    except Exception as e:
        log.error(f"Error in tv_antenna_macro: {e}")


def _handle_avr_source_change(command):
    source_list = hass.states.get(AVR).attributes.get("source_list")
    if AVR_INPUT[command] in source_list:
        media_player.select_source(entity_id=AVR, source=AVR_INPUT[command])

    else:
        log.warning(f"Source not found: {AVR_INPUT[command]}")


def _avr_tv_input_minder():
    try:
        tv_input = state.getattr(LIVINGROOM_TV)["source"].upper()
        if tv_input != TV_AVR_INPUT:
            media_player.select_source(entity_id=LIVINGROOM_TV, source=TV_AVR_INPUT)
    except KeyError:  # "Source" attribte dissapears when TV is off
        return
    except Exception as e:
        log.error(f"Error in _avr_tv_input_minder: {e}")


def _handle_avr(command):
    _avr_tv_input_minder()

    if command == "mute":
        avr_mute_toggle()
        return

    elif command in ["on", "off"]:
        tv_helper = MediaPlayerHelper()
        if command == "on":
            tv_helper.livingroom_system_on()
        else:
            tv_helper.livingroom_system_off()
        return

    elif command in AVR_INPUT:
        _update_tv_picture_mode(command)
        _handle_avr_source_change(command)
        return

    # Volume commands are handled via RS232 now
    elif command in ["volup", "voldown"]:
        return

    else:
        log.warning(f"Unknown AVR command: {command}")


def _process_command_received(device, command):

    # Requested by RTI on connection established
    if device == "states" and command == "get":
        send_all_states()

    elif device == "thermostat" and command == "get":
        send_thermostat_states()

    elif device == "doorswindows" and command == "get":
        send_security_states()

    elif device == "avr" or device == "home_theater":
        _handle_avr(command)

    elif device == "tv" and "bri" in command:
        command = command.replace("bri", "")
        update_tv_brightness(int(command))

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


def _process_macro_received(device, command):
    if device == "tv" and command == "tv_antenna":
        tv_antenna_macro()
    else:
        log.warning(f"Unknown macro from RTI: macro:{device}:{command}")


@state_trigger(AVR)
@state_trigger(LIVINGROOM_TV)
def home_theater_state_changed():
    tv_helper = MediaPlayerHelper()
    if tv_helper.livingroom_system_is_on():
        fire_rti_event(payload="on", topic="system_home_theater")
    else:
        fire_rti_event(payload="off", topic="system_home_theater")


@state_trigger(LIVINGROOM_FAN)
def send_fan_state():
    speed = state.get(f"{LIVINGROOM_FAN}.percentage")
    fire_rti_event(payload=speed, topic="fan_speed")


@event_trigger("RTI_Rx")
def rti_message_received(payload=None):
    try:
        split = payload.split(":")
        mode = split[0]
        device = split[1]
        command = split[2]

        if mode == "cmd":
            _process_command_received(device, command)

        elif mode == "macro":
            _process_macro_received(device, command)

        else:
            log.warning(f"Unknown mode: {mode}")

    except Exception as e:
        log.error(f"Error processing RTI command: {e}")
