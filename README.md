# HomeAssistant_RTI_Remote
Integrating RTI control systems and RTI remotes as extensions of Home Assistant

## Reason
- Home Assistant is an incredible FOSS home control system that works with almost everything, but it is just software.
- RTI makes incredible hardware, especially Home Theater oriented remotes, but their control system is proprietary and has been surpassed by Home Assistant in my opinion.
- Samsung discontinued their Harmony remote line in 2021, the previous favourite hardware remote owned by Home Assistant users.  As of 2024, there has not been a mass produced direct replacement for Harmony.

This project is my soloution to the above.  Use RTI hardware with Home Assistant Software for the best of both worlds.

## Disclaimers

- Not affiliated with Home Assistant or RTI Control company.

- This project is purely academic, and may not be practical for most people.

- This not a "driver", "integration" or "addon" for either system.  Without access to the RTI SDK, which requires special approval from RTI, there's no way to make the two systems sync up in a way that 'just works' out of the box.

- RTI systems can only be programmed by authorized parties.

### Architecture

To showcase the power of choice that comes with Home Assistant, this project uses a combination of Node-Red and Pyscript to interact with the RTI hardware.

RTI is programmed in a GUI program called "Integration Designer".  We can not write actual code in Integration Designer, so the first step was to find a built-in driver that we can make use of.  I chose to use two "Two Way Strings" drivers: one for Tx and one for Rx.

