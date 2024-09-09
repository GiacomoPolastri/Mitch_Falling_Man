import asyncio
import binascii
import math
from asyncio.tasks import sleep
import paho.mqtt.client as mqtt  # type: ignore
import json
import signal
import sys
from threading import Thread, current_thread
from bleak import BleakClient, cli  # type: ignore

# Indirizzo BLE del dispositivo Mitch
mitch_ble_address = "C8:49:E4:54:41:41"
CMMD_CHAR_UUID = "d5913036-2d8a-41ee-85b9-4e361aa5c8a7"
DATA_CHAR_UUID = "09bf2c52-d1d9-c0b7-4145-475964544307"

# Loop asincrono globale
async_loop = asyncio.new_event_loop()

# Variabili globali per la connessione MQTT e stato del dispositivo
client = None
mqtt_client = None
connected = False

# Costanti per l'accesso ai dati
READ_ACCESS_BYTE = 0x82
WRITE_ACCESS_BYTE = 0x02

# Filtri per i dati degli assi
x_filtered = 0.0
y_filtered = 0.0
z_filtered = 0.0

# Stato di configurazione iniziale
configured_up = False
configured_down = False
start_heading_up = 0.0
start_heading_down = 0.0
current_yaw = 0.0
old_yaw = 0.0

# Costanti di configurazione del bracciale
STATE_OF_SYSTEM = 0xF8  # Stato del sistema
MODE = 0x05             # Modalità operativa
FREQUENCY = 0x04        # Frequenza di funzionamento (50Hz)
LENGTH = 0x03           # Lunghezza dei dati inviati


def on_connect(client, userdata, flags, rc):
    """Callback per la connessione MQTT."""
    print("Connesso al broker con codice {}".format(str(rc)))


def start_mqtt_client():
    """Avvia il client MQTT e si connette al broker."""
    global mqtt_client
    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect
    mqtt_client.connect("localhost", 1883, 60)
    mqtt_client.loop_start()
    print("Client MQTT avviato e connesso al broker.")


def stop_mqtt_client():
    """Ferma il client MQTT."""
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    print("Client MQTT disconnesso.")


def publish_data(topic, payload):
    """Pubblica i dati filtrati sul broker MQTT."""
    mqtt_client.publish(topic, json.dumps(payload))
    print(f"Dati pubblicati su {topic}: {payload}")


async def connect_to_device(address):
    """Gestisce la connessione al dispositivo BLE."""
    global client, connected

    client = BleakClient(address)
    print("Tentativo di connessione al dispositivo BLE...")
    
    if not client.is_connected:
        await client.connect()
        connected = client.is_connected
        print("Client connesso: {}".format(connected))

        # Configurazione della sensibilità dell'accelerometro
        await configure_accelerometer()


async def configure_accelerometer():
    """Configura i parametri di sensibilità dell'accelerometro."""
    pkt = bytearray([0x41, 0x01, 0x04] + [0] * 17)
    await client.write_gatt_char(CMMD_CHAR_UUID, pkt, True)
    
    response = await client.read_gatt_char(CMMD_CHAR_UUID)
    error = list(response)[3]
    
    if error == 0:
        print("Set valori accelerometro fatto...")
    else:
        print("Errore {} nel settaggio dei valori di axl".format(error))
        await client.disconnect()


def process_raw_data(raw_data):
    """Elabora i dati grezzi dal dispositivo BLE."""
    x = int.from_bytes(raw_data[0:2], byteorder='little')
    y = int.from_bytes(raw_data[2:4], byteorder='little')
    z = int.from_bytes(raw_data[4:6], byteorder='little')
    return x, y, z


def filter_data(x, y, z):
    """Applica un filtro ai dati grezzi degli assi."""
    global x_filtered, y_filtered, z_filtered
    alpha = 0.1
    x_filtered = alpha * x + (1 - alpha) * x_filtered
    y_filtered = alpha * y + (1 - alpha) * y_filtered
    z_filtered = alpha * z + (1 - alpha) * z_filtered
    return x_filtered, y_filtered, z_filtered


async def read_device_data():
    """Legge i dati dal dispositivo BLE e li filtra."""
    raw_data = await client.read_gatt_char(DATA_CHAR_UUID)
    x, y, z = process_raw_data(raw_data)
    x_filtered, y_filtered, z_filtered = filter_data(x, y, z)
    return x_filtered, y_filtered, z_filtered


async def process_and_publish_data():
    """Elabora i dati dal dispositivo e li pubblica su MQTT."""
    while connected:
        x_filtered, y_filtered, z_filtered = await read_device_data()
        payload = {
            "x_filtered": x_filtered,
            "y_filtered": y_filtered,
            "z_filtered": z_filtered,
        }
        publish_data("MITCH_readings_in", payload)


def signal_handler(sig, frame):
    """Gestisce i segnali di interruzione e termina il programma."""
    print('Interruzione ricevuta, chiusura in corso...')
    asyncio.run(stop_program())
    sys.exit(0)


async def stop_program():
    """Ferma il programma disconnettendo il dispositivo e fermando MQTT."""
    global connected
    if connected:
        await client.disconnect()
        connected = False
    stop_mqtt_client()


# Imposta il signal handler per il SIGINT
signal.signal(signal.SIGINT, signal_handler)

# Inizio della connessione e avvio del ciclo di lettura/pubblicazione dati
async def main():
    start_mqtt_client()
    await connect_to_device(mitch_ble_address)
    await process_and_publish_data()

if __name__ == "__main__":
    asyncio.run(main())