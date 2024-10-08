import asyncio, binascii, math
from asyncio.tasks import sleep
import paho.mqtt.client as mqtt
import json

import signal, sys

from threading import Thread, current_thread
from bleak import BleakClient, cli

from mqtt_connection import connection

async_loop = asyncio.new_event_loop()

client = None
mqtt_client = None
connected = False



x_filtered = 0.0
y_filtered = 0.0
z_filtered = 0.0

configured_up = False
configured_down = False
start_heading_up = 0.0
start_heading_down = 0.0
current_yaw = 0.0
old_yaw = 0.0

def on_connect(client, userdata, flags, rc):
    print("Connesso al broker con codice {}".format(str(rc)))

'''
        #inizio a leggere i valori
        print("Stream avviato")
        await client.start_notify(DATA_CHAR_UUID, notification_handler)
        await asyncio.sleep(60.0)
        await client.stop_notify(DATA_CHAR_UUID)

        print("Disconnessione")
        await client.disconnect()

        mqtt_client.loop_stop()
        exit(0)
'''
'''
def notification_handler(sender, data):
    #print("\rLetto sullo stream dati: {}".format(binascii.hexlify(data)))
    pkg_len = int.from_bytes(bytes(data[1:2]), byteorder='little', signed=False)
    #print("\rLunghezza payload: {}".format(pkg_len))
    data_conversion(data)

def main_callback():

    global async_loop

    asyncio.set_event_loop(async_loop)
    try:
        asyncio.get_event_loop().run_until_complete(connection(mitch_ble_address))
    except KeyboardInterrupt:
        print("Chiusura")
        async_loop.stop()
        exit(0)
    #async_loop.run_forever()

def data_conversion(pkg):

    global x_filtered, y_filtered, z_filtered
    global current_yaw, old_yaw
    global configured_up, configured_down, start_heading_up, start_heading_down

    num_list = list(pkg)

    # gyro
    x_gyro = int.from_bytes(bytes(num_list[2:4]), byteorder='little', signed=True)*0.07*0.01745
    y_gyro = int.from_bytes(bytes(num_list[4:6]), byteorder='little', signed=True)*0.07*0.01745
    z_gyro = int.from_bytes(bytes(num_list[6:8]), byteorder='little', signed=True)*0.07*0.01745

    # axl
    #x sensibilita ) / 1000 ) x gravita
    x_axl = ((int.from_bytes(bytes(num_list[8:10]), byteorder='little', signed=True)*0.488)/1000)*9.8066
    y_axl = ((int.from_bytes(bytes(num_list[10:12]), byteorder='little', signed=True)*0.488)/1000)*9.8066
    z_axl = ((int.from_bytes(bytes(num_list[12:14]), byteorder='little', signed=True)*0.488)/1000)*9.8066

    #controllo se il bracciale e a testa in giu
    #print("Z axl: {}".format(z_axl))
    is_upside_down = (z_axl < 0)

    #controllo se il bracciale sta ruotando
    #veloce perche si sta girando
    is_turning = (y_gyro > 5.0) or (y_gyro < -5.0)

    #magn
    #il pacchetto arriva al massimo a 20 bytes
    x_mag = int.from_bytes(bytes(num_list[14:16]), byteorder='little', signed=True)*1000*1.5
    y_mag = int.from_bytes(bytes(num_list[16:18]), byteorder='little', signed=True)*1000*1.5
    z_mag = int.from_bytes(bytes(num_list[18:20]), byteorder='little', signed=True)*1000*1.5

    roll = 180 * math.atan2(x_axl, math.sqrt(y_axl**2 + z_axl**2))/math.pi
    pitch = 180 * math.atan2(y_axl, math.sqrt(x_axl**2 + z_axl**2))/math.pi
    
    if not configured_up:
        start_heading_up = 180 * math.atan2(y_mag, x_mag)/math.pi
        configured_up = True
        #configured_down = False
    else:
        if not is_turning:
            if pitch < 10.0 and pitch > -10.0:
                if roll < 10.0 and roll > -10.0:
                    old_yaw = current_yaw
                    current_yaw = 180 * math.atan2(y_mag, x_mag)/math.pi - start_heading_up 
                else:
                    current_yaw = old_yaw
            else:
                current_yaw = old_yaw
        
        if is_upside_down:
            if not configured_down:
                start_heading_down = 180 * math.atan2(-y_mag, x_mag)/math.pi
                configured_down = True
                #configured_up = False
            else:
                if not is_turning:
                    old_yaw = current_yaw
                    current_yaw = 180 * math.atan2(-y_mag, x_mag)/math.pi - start_heading_down
        #cerco di simulare lo yaw se no non se ne esce
        #uso la tecnica del giroscopio: se il giroscopio
        #si muove ad una certa velocita sull asse delle y
        #allora ruoto la base
    #print("roll {} \t pitch {}".format(roll, pitch))
        print("current yaw: {}".format(current_yaw))

        #if not is_turning:

        #    if z_gyro > 5.0 and current_yaw == 180.0:
        #        current_yaw = 0.0
        #    elif z_gyro < -5.0 and current_yaw == -180.0:
        #        current_yaw = 0.0
        #    else:
        #        if z_gyro > 12.0:
        #            if current_yaw > -180:
        #                current_yaw = current_yaw - 90.0
        #
        #        if z_gyro < -12.0:
        #            if current_yaw < 180:
        #                current_yaw = current_yaw + 90.0

    #print("Yaw: {}".format(current_yaw))
    #bisogna compensare il magnetometro nel caso in cui si ruoti
    #quando non si e sulla scrivania
    #per fare cio bisogna usare seno e coseno
    #che necessitano radianti, quindi devo convertire il pitch e il roll
    #per compensare il tilt bisogna proiettare il vettore che indica la
    #direzione sul piano xy rappresentato dalla scrivania, quello standard
    #roll_rad = roll * (2 * math.pi) / 360
    #pitch_rad = pitch * (2 * math.pi) / 360

    #provo ad applicare un filtro per ridurre il rumore
    #alpha = 0.05

    #filtered_x_mag = alpha * x_mag + (1 - alpha) * x_filtered
    #x_filtered = (filtered_x_mag)
    
    #filtered_y_mag = alpha * y_mag + (1 - alpha) * y_filtered
    #y_filtered = filtered_y_mag

    #filtered_z_mag = alpha * z_mag + (1 - alpha) * z_filtered
    #z_filtered = filtered_z_mag

    #compensated_x_mag = filtered_x_mag * math.cos(pitch_rad) + filtered_y_mag * math.sin(roll_rad) * math.sin(pitch_rad) - filtered_z_mag * math.cos(roll_rad) * math.sin(pitch_rad)
    #compensated_y_mag = filtered_y_mag * math.cos(roll_rad) + filtered_z_mag * math.sin(roll_rad)

    
    #cerco di normalizzare il valore tra -180 e 180
    #yaw = 180 * math.atan2(compensated_y_mag, compensated_x_mag)/math.pi;
    
    #print("\rPitch: {}\tRoll: {}".format(pitch, roll))
    #print("\rYaw: {2:.2f}".format(x_mag, y_mag, yaw))

    data = {
            "roll": roll,
            "pitch": pitch,
            "yaw": current_yaw,
            "is_upside_down": is_upside_down,
            "is_turning": is_turning
    }
    json_message = json.dumps(data)
    mqtt_client.publish("MITCH_readings_in", json_message)
'''

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
    '''
    main_thread = Thread(target=main_callback)
    main_thread.start()

    mqtt_client.loop_start()
    '''
main()