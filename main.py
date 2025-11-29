from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pymysql
from datetime import datetime
import ssl  # Necesario para manejar la ruta del certificado SSL

# --- Configuración de Conexión a Azure MySQL Database ---
# IMPORTANTE: El usuario de Azure MySQL requiere el sufijo @nombre_del_servidor
DB_SERVER = 'centroagsapo.mysql.database.azure.com'
DB_NAME = 'dbvideojuegos'
DB_USER = 'utede'
DB_PASSWORD = 'utede2025'
DB_PORT = 3306  # Asegúrate que es un entero
# ---
# CRÍTICO: Necesitas la ruta al certificado SSL de Azure.
# Descárgalo del portal y colócalo en una ruta accesible.
# Reemplaza 'Ruta/al/certificado/DigiCertGlobalRootCA.crt' con la ruta real.
# Para el Servidor Único de Azure MySQL, suele ser el BaltimoreCyberTrustRoot.crt.pem
SSL_CERT_PATH = 'Ruta/al/certificado/DigiCertGlobalRootCA.crt'

# Inicializar FastAPI
app = FastAPI(title="QR Code Validator API")

# Modelo de datos para la solicitud (el ID que viene del QR)


class QRCodeData(BaseModel):
    qr_id: str


def get_db_connection():
    """Función para obtener la conexión a la base de datos usando PyMySQL."""
    try:
        # Configuración de SSL (OBLIGATORIO para Azure MySQL)
        # ssl_context = ssl.create_default_context(cafile=SSL_CERT_PATH)

        conn = pymysql.connect(
            host=DB_SERVER,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            port=DB_PORT
            # ssl=ssl_context
        )
        return conn
    except FileNotFoundError:
        # Esto ocurre si la ruta del certificado es incorrecta
        print("ERROR: No se encontró el certificado SSL. Asegúrate de que la ruta SSL_CERT_PATH sea correcta y el archivo exista.")
        raise HTTPException(
            status_code=500, detail="Error de Configuración SSL. Certificado no encontrado."
        )
    except pymysql.MySQLError as e:
        print(f"Error al conectar a la DB: {e}")
        # Asegúrate de revisar la configuración de Firewall de Azure.
        raise HTTPException(
            status_code=500, detail="Error de conexión a la base de datos MySQL. Revise Firewall."
        )

# explica este codigo


@app.post("/validate_qr")
async def validate_qr(data: QRCodeData):
    """
    Endpoint para validar y registrar la lectura de un código QR.
    """
    qr_id = data.qr_id.strip()

    # Intenta obtener la conexión (maneja HTTPException internamente)
    conn = get_db_connection()

    # PyMySQL usa un cursor por defecto, lo creamos
    # El diccionario cursor facilita la lectura de los resultados
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    try:
        # 1. Buscar el código en la DB
        # NOTA: Los nombres de las columnas en tu SQL ('idregistro', 'nombre', 'estado')
        # no coinciden con las usadas en tu lógica ('is_read', 'description').
        # He ajustado la lógica de la consulta para ser más coherente:

        cursor.execute(
            "SELECT idregistro, nombre, estado FROM controlinvitados WHERE idregistro = %s", (
                qr_id,)
        )
        row = cursor.fetchone()

        if not row:
            # El código QR no existe en la base de datos
            raise HTTPException(
                status_code=404, detail=f"Código QR '{qr_id}' no encontrado o inválido.")

        # Asignación basada en la estructura de tu tabla (asumiendo 'estado' es el indicador de lectura)
        id_registro = row['idregistro']
        nombre_invitado = row['nombre']
        estado_leido = row['estado']  # Asumiendo 1 = leído, 0 = no leído

        if estado_leido == 1:
            # El código ya fue leído
            return {
                "status": "warning",
                "message": f"❌ Error: El colaborador '{qr_id}' ({nombre_invitado}) YA ESTA REGISTRADO.",
                "details": {"id": qr_id, "Nombre": nombre_invitado, "read": True}
            }
        else:
            # 2. Marcar como leído
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # Formato MySQL

            # ASUMIENDO que la tabla tiene las columnas 'estado' y 'Fecha_Lectura'
            cursor.execute(
                "UPDATE controlinvitados SET estado = 1, fecharegistro = %s WHERE idregistro = %s",
                (now, qr_id)
            )
            conn.commit()

            # 3. Respuesta de éxito
            return {
                "status": "success",
                "message": f"✅ Éxito: Colaborador '{qr_id}' ({nombre_invitado}) REGISTRADO.",
                "details": {"id": qr_id, "nombre": nombre_invitado, "read": True, "date": now}
            }

    except HTTPException:
        # Re-lanza los errores 404
        raise
    except Exception as e:
        conn.rollback()
        print(f"Error en la lógica del servicio: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error interno del servidor en la transacción: {str(e)}")
    finally:
        cursor.close()
        conn.close()

# --- Ejecución Local de la API ---
# Para ejecutar localmente, usa: uvicorn main:app --reload
#if __name__ == "__main__":
#    import uvicorn
#    uvicorn.run(app, host="0.0.0.0", port=8000)


