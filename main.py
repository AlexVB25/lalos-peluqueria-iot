from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from fastapi.responses import FileResponse

from pydantic import BaseModel

from datetime import datetime



import firebase_admin

from firebase_admin import credentials, messaging



import json
import base64

import os





app = FastAPI(

    title="Peluqueria IoT",

    version="1.0"

)





# =========================================================

# FIREBASE ADMIN

# =========================================================



firebase_b64 = os.getenv("FIREBASE_SERVICE_ACCOUNT_B64")

if firebase_b64:
    firebase_info = json.loads(
        base64.b64decode(firebase_b64).decode("utf-8")
    )
    cred = credentials.Certificate(firebase_info)
else:
    cred = credentials.Certificate(
        "firebase-service-account.json"
    )

firebase_admin.initialize_app(cred)





# =========================================================

# VARIABLES GLOBALES

# =========================================================



eventos = []

conexiones = []



TOKENS_FILE = os.getenv("TOKENS_FILE", "tokens.json")





estado_dispositivos = {

    "pir": True,

    "timbre": True

}

# =========================================================
# ESTADO ESP32 / HEARTBEAT
# =========================================================

estado_esp32 = {
    "ssid": "",
    "ip": "",
    "rssi": 0,
    "ultima_conexion": None
}

ESP32_TIMEOUT_SEGUNDOS = 25






# =========================================================

# MODELOS

# =========================================================



class Evento(BaseModel):

    tipo: str





class TokenFCM(BaseModel):

    token: str





class EstadoDispositivo(BaseModel):

    dispositivo: str

    activo: bool


class EstadoESP32(BaseModel):
    ssid: str
    ip: str
    rssi: int






# =========================================================

# TOKENS FCM

# =========================================================



def cargar_tokens():



    if not os.path.exists(TOKENS_FILE):

        return []



    try:



        with open(

            TOKENS_FILE,

            "r",

            encoding="utf-8"

        ) as archivo:



            return json.load(archivo)



    except Exception as e:



        print(

            "Error cargando tokens:",

            e

        )



        return []





def guardar_tokens():

    try:

        carpeta_tokens = os.path.dirname(TOKENS_FILE)

        if carpeta_tokens:
            os.makedirs(
                carpeta_tokens,
                exist_ok=True
            )

        with open(

            TOKENS_FILE,

            "w",

            encoding="utf-8"

        ) as archivo:



            json.dump(

                tokens_fcm,

                archivo,

                indent=2

            )



    except Exception as e:



        print(

            "Error guardando tokens:",

            e

        )





tokens_fcm = list(

    dict.fromkeys(

        cargar_tokens()

    )

)



guardar_tokens()





# =========================================================

# PAGINA PRINCIPAL

# =========================================================



@app.get("/")

def inicio():



    return FileResponse(

        "index.html"

    )





# =========================================================

# SERVICE WORKER

# =========================================================



@app.get("/firebase-messaging-sw.js")

def firebase_service_worker():



    return FileResponse(

        "firebase-messaging-sw.js",

        media_type="application/javascript"

    )





# =========================================================

# HISTORIAL

# =========================================================



@app.get("/api/eventos")

def obtener_eventos():



    return eventos





@app.delete("/api/eventos")

def eliminar_historial():



    eventos.clear()



    print("")

    print("==============================")

    print("HISTORIAL ELIMINADO")

    print("==============================")



    return {

        "ok": True,

        "mensaje": "Historial eliminado"

    }





# =========================================================

# CONTROL PIR / TIMBRE

# =========================================================



@app.get("/api/estado-dispositivos")

def obtener_estado_dispositivos():



    return estado_dispositivos





@app.post("/api/estado-dispositivos")

def cambiar_estado_dispositivo(

    datos: EstadoDispositivo

):



    if datos.dispositivo not in estado_dispositivos:



        return {

            "ok": False,

            "mensaje": "Dispositivo no valido"

        }





    estado_dispositivos[

        datos.dispositivo

    ] = datos.activo





    estado_texto = (

        "ACTIVO"

        if datos.activo

        else

        "APAGADO"

    )





    print(

        f">>> {datos.dispositivo.upper()} "

        f"-> {estado_texto}"

    )





    return {

        "ok": True,

        "estado": estado_dispositivos

    }





# =========================================================

# REGISTRAR TOKEN

# =========================================================



# =========================================================
# ESTADO DEL ESP32
# =========================================================

@app.post("/api/esp32/status")
async def recibir_estado_esp32(estado: EstadoESP32):

    estado_esp32["ssid"] = estado.ssid
    estado_esp32["ip"] = estado.ip
    estado_esp32["rssi"] = estado.rssi
    estado_esp32["ultima_conexion"] = datetime.now()

    print(
        f">>> ESP32 ONLINE | "
        f"WiFi: {estado.ssid} | "
        f"IP: {estado.ip} | "
        f"RSSI: {estado.rssi} dBm"
    )

    return {"ok": True}


@app.get("/api/esp32/status")
async def obtener_estado_esp32():

    ultima_conexion = estado_esp32["ultima_conexion"]

    if ultima_conexion is None:
        return {
            "conectado": False,
            "ssid": "",
            "ip": "",
            "rssi": 0,
            "calidad": "Sin datos",
            "segundos_desde_ultimo_reporte": None
        }

    segundos = (
        datetime.now() - ultima_conexion
    ).total_seconds()

    conectado = segundos < ESP32_TIMEOUT_SEGUNDOS
    rssi = estado_esp32["rssi"]

    if rssi >= -50:
        calidad = "Excelente"
    elif rssi >= -60:
        calidad = "Buena"
    elif rssi >= -70:
        calidad = "Regular"
    else:
        calidad = "Débil"

    return {
        "conectado": conectado,
        "ssid": estado_esp32["ssid"],
        "ip": estado_esp32["ip"],
        "rssi": rssi,
        "calidad": calidad,
        "segundos_desde_ultimo_reporte": round(segundos, 1)
    }


@app.post("/api/register-token")

def registrar_token(

    datos: TokenFCM

):



    token = datos.token.strip()



    if not token:



        return {

            "ok": False,

            "mensaje": "Token vacio"

        }





    if token not in tokens_fcm:



        tokens_fcm.append(

            token

        )



        guardar_tokens()



        print("")

        print("==============================")

        print("NUEVO DISPOSITIVO REGISTRADO")

        print(

            "Total:",

            len(tokens_fcm)

        )

        print("==============================")



        return {

            "ok": True,

            "mensaje": "Dispositivo registrado",

            "total": len(tokens_fcm)

        }





    return {

        "ok": True,

        "mensaje":

            "El dispositivo ya estaba registrado",

        "total": len(tokens_fcm)

    }





# =========================================================

# ENVIAR PUSH

# =========================================================



def enviar_push(tipo: str):



    if tipo == "persona_detectada":



        titulo = "Persona detectada"



        cuerpo = (

            "Hay alguien en la entrada "

            "de la peluqueria."

        )





    elif tipo == "timbre_presionado":



        titulo = "Timbre"



        cuerpo = (

            "Hay una persona esperando afuera."

        )





    else:



        titulo = "Peluqueria IoT"

        cuerpo = "Nuevo evento detectado."





    if len(tokens_fcm) == 0:



        print(

            "No hay dispositivos registrados."

        )



        return





    tokens_invalidos = []





    for token in tokens_fcm:



        mensaje = messaging.Message(



            notification=messaging.Notification(

                title=titulo,

                body=cuerpo

            ),



            token=token

        )





        try:



            respuesta = messaging.send(

                mensaje

            )



            print(

                "PUSH ENVIADO:",

                respuesta

            )





        except Exception as e:



            print(

                "ERROR ENVIANDO PUSH:",

                e

            )





            texto_error = str(

                e

            ).lower()





            if (

                "registration-token-not-registered"

                in texto_error

                or

                "not found"

                in texto_error

            ):



                tokens_invalidos.append(

                    token

                )





    for token in tokens_invalidos:



        if token in tokens_fcm:



            tokens_fcm.remove(

                token

            )





    if tokens_invalidos:



        guardar_tokens()





# =========================================================

# EVENTOS DEL ESP32

# =========================================================



@app.post("/api/event")

async def recibir_evento(

    evento: Evento

):



    # -----------------------------------------------------

    # IGNORAR PIR SI ESTA APAGADO

    # -----------------------------------------------------



    if (

        evento.tipo

        == "persona_detectada"

        and

        not estado_dispositivos["pir"]

    ):



        print(

            ">>> PIR APAGADO: "

            "evento ignorado"

        )



        return {

            "ok": True,

            "ignorado": True,

            "motivo": "pir_apagado"

        }





    # -----------------------------------------------------

    # IGNORAR TIMBRE SI ESTA APAGADO

    # -----------------------------------------------------



    if (

        evento.tipo

        == "timbre_presionado"

        and

        not estado_dispositivos["timbre"]

    ):



        print(

            ">>> TIMBRE APAGADO: "

            "evento ignorado"

        )



        return {

            "ok": True,

            "ignorado": True,

            "motivo": "timbre_apagado"

        }





    # -----------------------------------------------------

    # EVENTO VALIDO

    # -----------------------------------------------------



    ahora = datetime.now().strftime(

        "%H:%M:%S"

    )





    nuevo_evento = {

        "tipo": evento.tipo,

        "hora": ahora

    }





    eventos.insert(

        0,

        nuevo_evento

    )





    # Mantener maximo 10 eventos

    if len(eventos) > 10:



        eventos.pop()





    print("")

    print("==============================")

    print("EVENTO RECIBIDO")

    print(

        "Tipo:",

        evento.tipo

    )

    print(

        "Hora:",

        ahora

    )

    print(

        "Total eventos:",

        len(eventos)

    )

    print("==============================")





    # Push

    enviar_push(

        evento.tipo

    )





    # WebSocket

    conexiones_muertas = []





    for websocket in conexiones:



        try:



            await websocket.send_json(

                nuevo_evento

            )



        except:



            conexiones_muertas.append(

                websocket

            )





    for websocket in conexiones_muertas:



        if websocket in conexiones:



            conexiones.remove(

                websocket

            )





    return {

        "ok": True,

        "tipo": evento.tipo,

        "hora": ahora

    }





# =========================================================

# WEBSOCKET

# =========================================================



@app.websocket("/ws")

async def websocket_endpoint(

    websocket: WebSocket

):



    await websocket.accept()



    conexiones.append(

        websocket

    )





    print(

        ">>> PAGINA WEB CONECTADA"

    )





    try:



        while True:



            await websocket.receive_text()





    except WebSocketDisconnect:



        print(

            ">>> PAGINA WEB DESCONECTADA"

        )





    except Exception as e:



        print(

            "ERROR WEBSOCKET:",

            e

        )





    finally:



        if websocket in conexiones:



            conexiones.remove(

                websocket

            )