import asyncio
import json
from threading import Thread
from bleak import BleakClient
import paho.mqtt.client as mqtt

mitch_ble_address = "C8:49:E4:54:41:41"
CMMD_CHAR_UUID = "d5913036-2d8a-41ee-85b9-4e361aa5c8a7"
DATA_CHAR_UUID = "09bf2c52-d1d9-c0b7-4145-475964544307"

# BLE configuration values
STATE_OF_SYSTEM = 0xF8
MODE = 0x05
FREQUENCY = 0x04
LENGTH = 0x03
READ_ACCESS_BYTE = 0x82
WRITE_ACCESS_BYTE = 0x02

async_loop = asyncio.new_event_loop()

def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT broker with code {}".format(str(rc)))

def main_callback():

    global async_loop

    asyncio.set_event_loop(async_loop)
    try:
        asyncio.get_event_loop().run_until_complete(connection(mitch_ble_address))
    except KeyboardInterrupt:
        print("Shutting down")
        async_loop.stop()
        exit(0)

async def connection(address):
    global mqtt_client

    # Initialize BLE Client
    client = BleakClient(address)

    # Check if already connected, if not, try to connect
    try:
        print("Checking BLE connection status...")

        # Try to connect only if the client is not already connected
        if not client.is_connected:
            print("Not connected, attempting to connect...")
            await client.connect()
            print(f"BLE Client connected: {client.is_connected}")
        else:
            print("Already connected to BLE device.")

        # 1. Set accelerometer sensitivity (as per your original code)
        pkt = bytearray([0x41, 0x01, 0x04])
        for i in range(17):
            pkt.append(0)

        await client.write_gatt_char(CMMD_CHAR_UUID, pkt, True)
        response = await client.read_gatt_char(CMMD_CHAR_UUID)
        error = list(response)[3]
        if error == 0:
            print("Accelerometer sensitivity set successfully.")
        else:
            print(f"Error {error} setting accelerometer sensitivity.")
            await client.disconnect()
            exit(1)

        # 2. Set options (stream options like frequency, mode)
        pkt = bytearray([WRITE_ACCESS_BYTE, LENGTH, STATE_OF_SYSTEM, MODE, FREQUENCY])
        for i in range(15):
            pkt.append(0)

        await client.write_gatt_char(CMMD_CHAR_UUID, pkt, True)
        response = await client.read_gatt_char(CMMD_CHAR_UUID)
        error = list(response)[3]
        if error == 0:
            print("Stream options set successfully.")
        else:
            print(f"Error {error} setting stream options.")
            await client.disconnect()
            exit(1)

        # 3. Check for errors before streaming
        pkt = bytearray([0x89, 0x00])
        for i in range(18):
            pkt.append(0)

        await client.write_gatt_char(CMMD_CHAR_UUID, pkt, True)
        response = await client.read_gatt_char(CMMD_CHAR_UUID)
        error = list(response)[3]
        if error == 0:
            print("System check passed, starting data stream.")
        else:
            print(f"Error {error} in system check.")
            await client.disconnect()
            exit(1)

        # 4. Continuously read BLE data and publish it to MQTT
        while True:
            try:
                # Read data from the BLE device
                ble_data = await client.read_gatt_char(DATA_CHAR_UUID)

                # Convert the BLE data to a list and JSON format
                data = {
                    "ble_data": list(ble_data)
                }
                json_message = json.dumps(data)

                # Publish the data to the MQTT broker
                mqtt_client.publish("MITCH_readings_in", json_message)

                # Wait for a bit before the next read (adjust frequency as necessary)
                await asyncio.sleep(0.1)  # Adjust this delay based on your needs (50Hz = 0.02s)

            except Exception as e:
                print(f"Error while reading BLE data or publishing: {e}")
                break

    except Exception as e:
        print(f"Failed to connect or read BLE data: {e}")
        if client.is_connected:
            await client.disconnect()

def main():

    global mqtt_client

    # Set up the MQTT client
    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect

    # Connect to the MQTT broker
    server_ip_address = "localhost"
    port = 1883
    mqtt_client.connect(server_ip_address, port)

    # Publish a test message to indicate the start of data transmission
    data = {
        "test": "starting sending data"
    }
    json_message = json.dumps(data)
    mqtt_client.publish("MITCH_readings_in", json_message)

    # Start the BLE connection in a separate thread
    main_thread = Thread(target=main_callback)
    main_thread.start()

    # Start the MQTT loop to handle background MQTT operations (sending only)
    mqtt_client.loop_start()

# Start the main function
main()
