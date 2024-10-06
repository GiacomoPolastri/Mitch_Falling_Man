import asyncio
import json
from threading import Thread
from bleak import BleakClient
import paho.mqtt.client as mqtt

mitch_ble_address = "C8:49:E4:54:41:41"
CMMD_CHAR_UUID = "d5913036-2d8a-41ee-85b9-4e361aa5c8a7"
DATA_CHAR_UUID = "09bf2c52-d1d9-c0b7-4145-475964544307"

#settaggio del funzionamento del bracciale
#sys tx
STATE_OF_SYSTEM = 0xF8
#attivo tutto il possibile del bracciale
MODE = 0x05
#funzionera con frequenza 50hz
FREQUENCY = 0x04
#lunghezza dei dati inviati
LENGTH = 0x03

READ_ACCESS_BYTE = 0x82
WRITE_ACCESS_BYTE = 0x02

async_loop = asyncio.new_event_loop()

def on_connect(client, userdata, flags, rc):
    print("Connesso al broker con codice {}".format(str(rc)))

def main_callback():

    global async_loop

    asyncio.set_event_loop(async_loop)
    try:
        asyncio.get_event_loop().run_until_complete(connection(mitch_ble_address))
    except KeyboardInterrupt:
        print("Chiusura")
        async_loop.stop()
        exit(0)

async def connection(address):
    global client
    global connected
    global mqtt_client

    client = BleakClient(address)
    print("Client connesso: {}".format(client.is_connected))
    #da fare nel caso in cui la connessione non sia 
    #avvenuta subito ma devo aspettare in modo asincrono
    #il mitch che si connetta
    if not client.is_connected:
        await client.connect()
        print("Client connesso: {}".format(client.is_connected))
        connected = client.is_connected

        #set sensibilita di axl
        pkt = bytearray([0x41, 0x01, 0x04])
        for i in range(17):
            pkt.append(0)

        await client.write_gatt_char(CMMD_CHAR_UUID, pkt, True)
        response = await client.read_gatt_char(CMMD_CHAR_UUID)
        error = list(response)[3]
        if(error == 0):
            print("Set valori accelerometro fatto...")
        else:
            print("Errore {} nel settaggio dei valori di axl".format(error))
            await client.disconnect()
            exit(1)

        #set delle opzioni
        #protocollo tlv, lunghezza totale 20 byte
        pkt = bytearray([WRITE_ACCESS_BYTE, LENGTH, STATE_OF_SYSTEM, MODE, FREQUENCY])
        for i in range(15):
            pkt.append(0)

        await client.write_gatt_char(CMMD_CHAR_UUID, pkt, True)
        response = await client.read_gatt_char(CMMD_CHAR_UUID)
        error = list(response)[3]
        if(error == 0):
            print("Set dello stream fatto...")
        else:
            print("Errore {} nel settaggio dello stream".format(error))
            print(response)
            await client.disconnect()
            exit(1)

        #check di errori prima di iniziare
        pkt = bytearray([0x89, 0x00])
        for i in range(18):
            pkt.append(0)

        await client.write_gatt_char(CMMD_CHAR_UUID, pkt, True)
        response = await client.read_gatt_char(CMMD_CHAR_UUID)
        error = list(response)[3]
        if(error == 0):
            print("Il check-up non ha rilavato problemi, avvio dello stream...")
        else:
            print("Errore {} nel check-up".format(error))
            await client.disconnect()
            exit(1)

def main():

    global mqtt_client

    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect

    server_ip_address = "localhost"
    port = 1883

    mqtt_client.connect(server_ip_address, port)
    data = {
            "test": "starting sending data"
    }
    json_message = json.dumps(data)
    mqtt_client.publish("MITCH_readings_in", json_message)

    main_thread = Thread(target=main_callback)
    main_thread.start()

    mqtt_client.loop_start()
    

main()