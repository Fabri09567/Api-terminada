from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
import modelo  # Importamos nuestro archivo de base de datos
from fastapi import FastAPI, HTTPException, Depends, File, UploadFile, Form
from fastapi.staticfiles import StaticFiles
import os
import shutil
import uuid  # Esto es para generar nombres únicos y que las fotos no se pisen
from passlib.context import CryptContext

# 1. Crear las tablas físicas en la base de datos al encender el servidor
modelo.Base.metadata.create_all(bind=modelo.engine)

app = FastAPI(title="API Sistema de Redes y Reclamos")

# --- CONFIGURACIÓN DE FOTOS ---
CARPETA_FOTOS = "fotos_subidas"
os.makedirs(CARPETA_FOTOS, exist_ok=True) # Crea la carpeta si no existe
app.mount("/fotos", StaticFiles(directory=CARPETA_FOTOS), name="fotos")

# --- NUEVO: Habilitamos una carpeta para el frontend ---
os.makedirs("frontend", exist_ok=True)
app.mount("/web", StaticFiles(directory="frontend", html=True), name="frontend")

# 2. Función clave: Abre y cierra la base de datos en cada petición de los celulares
def get_db():
    db = modelo.SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- CONFIGURACIÓN DE SEGURIDAD (Módulo 3) ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def obtener_password_hash(password):
    """Toma la contraseña en texto y la convierte en un código indescifrable."""
    return pwd_context.hash(password)

def verificar_password(plain_password, hashed_password):
    """Compara la contraseña que tipeó el usuario con el código guardado en la base."""
    return pwd_context.verify(plain_password, hashed_password)

# ---------------------------------------------------------
# ESQUEMAS (Lo que la API exige que el celular le mande)
# ---------------------------------------------------------
class LoginRequest(BaseModel):
    username: str
    password: str

class ReclamoCreate(BaseModel):
    numero_rp: int
    mes: str
    procedencia: str

class MedicionCreate(BaseModel):
    reclamo_id: Optional[int] = None
    tipo_operacion: str
    tramo_linea: Optional[str] = None
    servicio: int
    set_numero: int
    piquete: int
    tension_r: float
    tension_s: float
    tension_t: float
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    foto_url: Optional[str] = None

class UsuarioCreate(BaseModel):
    username: str
    password: str
    rol: str = "CUADRILLA" # Por defecto creamos operarios, a menos que especifiquemos "ADMIN"

# --- ESQUEMAS DE RESPUESTA (Para enviar datos a la web) ---
class MedicionResponse(BaseModel):
    id: int
    tipo_operacion: str
    tramo_linea: Optional[str]
    servicio: int
    set_numero: int
    piquete: int
    tension_r: float
    tension_s: float
    tension_t: float
    foto_url: Optional[str]

    class Config:
        from_attributes = True

class ReclamoResponse(BaseModel):
    id: int
    numero_rp: int
    mes: str
    procedencia: str
    # ¡Acá está la clave! Le decimos que adentro del reclamo va una lista de mediciones
    mediciones: list[MedicionResponse] = [] 

    class Config:
        from_attributes = True


# ---------------------------------------------------------
# RUTAS DE LA API
# ---------------------------------------------------------

@app.get("/")
def estado_servidor():
    return {"mensaje": "El servidor de la API está funcionando correctamente."}

@app.post("/api/login")
def iniciar_sesion(datos: LoginRequest, db: Session = Depends(get_db)):
    """Verifica el usuario y la contraseña encriptada."""
    
    usuario_db = db.query(modelo.Usuario).filter(modelo.Usuario.username == datos.username).first()
    
    # Acá está la magia: Usamos verificar_password() en lugar de ==
    if not usuario_db or not verificar_password(datos.password, usuario_db.password_hash):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
        
    if not usuario_db.activo:
        raise HTTPException(status_code=403, detail="Esta cuenta ha sido desactivada")
        
    return {
        "mensaje": "Inicio de sesión exitoso", 
        "token": f"token_simulado_para_{usuario_db.username}",
        "rol": usuario_db.rol,
        "id_usuario": usuario_db.id
    }

# --- ¡NUEVA RUTA PARA GUARDAR RECLAMOS! ---
@app.post("/api/reclamos")
def crear_reclamo(reclamo: ReclamoCreate, db: Session = Depends(get_db)):
    """Guarda un nuevo Reclamo en la base de datos real."""
    nuevo_reclamo = modelo.ReclamoRP(
        numero_rp=reclamo.numero_rp,
        mes=reclamo.mes,
        procedencia=reclamo.procedencia,
        creado_por=1 # Por ahora forzamos al usuario 1 hasta que armemos el sistema de tokens reales
    )
    db.add(nuevo_reclamo)
    db.commit()
    db.refresh(nuevo_reclamo)
    
    return {
        "mensaje": "Reclamo guardado con éxito en la base de datos", 
        "id_asignado": nuevo_reclamo.id
    }


@app.get("/api/reclamos")
def obtener_reclamos(db: Session = Depends(get_db)):
    """Devuelve la lista de todos los reclamos guardados."""
    reclamos = db.query(modelo.ReclamoRP).all()
    return reclamos

# --- RUTA PARA GUARDAR MEDICIONES TÉCNICAS ---
@app.post("/api/mediciones")
def crear_medicion(medicion: MedicionCreate, db: Session = Depends(get_db)):
    """Recibe los datos técnicos de la cuadrilla y los guarda."""
    
    nueva_medicion = modelo.Medicion(
        reclamo_id=medicion.reclamo_id,
        tipo_operacion=medicion.tipo_operacion,
        tramo_linea=medicion.tramo_linea,
        servicio=medicion.servicio,
        set_numero=medicion.set_numero,
        piquete=medicion.piquete,
        tension_r=medicion.tension_r,
        tension_s=medicion.tension_s,
        tension_t=medicion.tension_t,
        latitud=medicion.latitud,
        longitud=medicion.longitud,
        foto_url=medicion.foto_url
    )
    
    db.add(nueva_medicion)
    db.commit()
    db.refresh(nueva_medicion)
    
    return {
        "mensaje": f"Medición del tramo {medicion.tramo_linea} guardada correctamente", 
        "id_medicion": nueva_medicion.id
    }

# --- RUTA PARA CREAR USUARIOS (Cuadrillas o Admins) ---
@app.post("/api/usuarios")
def crear_usuario(usuario: UsuarioCreate, db: Session = Depends(get_db)):
    """Crea una nueva cuenta encriptando la contraseña."""
    
    usuario_existente = db.query(modelo.Usuario).filter(modelo.Usuario.username == usuario.username).first()
    if usuario_existente:
        raise HTTPException(status_code=400, detail="El nombre de usuario ya está en uso")
    
    # 1. Aplicamos la fórmula a la contraseña que ingresó el administrador
    contrasena_encriptada = obtener_password_hash(usuario.password)
    
    # 2. Guardamos el hash, NUNCA el texto plano
    nuevo_usuario = modelo.Usuario(
        username=usuario.username,
        password_hash=contrasena_encriptada, 
        rol=usuario.rol
    )
    
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)
    
    return {
        "mensaje": f"Usuario {nuevo_usuario.username} creado exitosamente con rol {nuevo_usuario.rol}",
        "id_usuario": nuevo_usuario.id
    }

# --- RUTA PARA LEER UN EXPEDIENTE COMPLETO ---
@app.get("/api/reclamos/{reclamo_id}", response_model=ReclamoResponse)
def obtener_reclamo_completo(reclamo_id: int, db: Session = Depends(get_db)):
    """Trae la ficha completa de un reclamo junto con todas sus mediciones vinculadas."""
    
    # Buscamos el reclamo por su ID
    reclamo = db.query(modelo.ReclamoRP).filter(modelo.ReclamoRP.id == reclamo_id).first()
    
    if not reclamo:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")
        
    return reclamo

# --- RUTA PARA SUBIR FOTOS Y CLASIFICARLAS (Módulo 2 Actualizado) ---
@app.post("/api/fotos")
def subir_fotos_medicion(
    servicio: int = Form(...),
    piquete: int = Form(...),
    foto_general: UploadFile = File(...), # 1ra - Obligatoria
    foto_equipo: UploadFile = File(...),  # 2da - Obligatoria
    foto_piquete: UploadFile = File(...), # 3ra - Obligatoria
    foto_observacion: UploadFile = File(None) # 4ta - Opcional (por eso tiene None)
):
    """
    Recibe las fotos de la cuadrilla, crea las carpetas por número de servicio 
    y gestiona la subcarpeta de anomalías si hay observaciones.
    """
    
    # 1. Crear la carpeta principal con el número de SERVICIO
    carpeta_servicio = os.path.join(CARPETA_FOTOS, str(servicio))
    os.makedirs(carpeta_servicio, exist_ok=True)
    
    # Función interna rápida para guardar cada foto sin repetir código
    def guardar_foto(archivo: UploadFile, carpeta_destino: str, prefijo: str):
        extension = archivo.filename.split(".")[-1]
        nombre_unico = f"{prefijo}_{uuid.uuid4().hex[:6]}.{extension}"
        ruta_fisica = os.path.join(carpeta_destino, nombre_unico)
        
        with open(ruta_fisica, "wb") as buffer:
            shutil.copyfileobj(archivo.file, buffer)
            
        return ruta_fisica, nombre_unico

    # 2. Guardar las 3 fotos OBLIGATORIAS en la carpeta del servicio
    ruta_gen, nom_gen = guardar_foto(foto_general, carpeta_servicio, "general")
    ruta_eq, nom_eq = guardar_foto(foto_equipo, carpeta_servicio, "equipo")
    ruta_piq, nom_piq = guardar_foto(foto_piquete, carpeta_servicio, "piquete")
    
    # Preparamos los links que la API le va a devolver al celular para que guarde en la BD
    links_respuesta = {
        "foto_general": f"/fotos/{servicio}/{nom_gen}",
        "foto_equipo":  f"/fotos/{servicio}/{nom_eq}",
        "foto_piquete": f"/fotos/{servicio}/{nom_piq}"
    }

    # 3. Lógica si la cuadrilla manda la 4ta foto (Observación)
    if foto_observacion:
        # Armar el nombre de la carpeta (Ej: piquete515623_observaciones)
        nombre_carpeta_obs = f"piquete{piquete}_observaciones"
        carpeta_obs = os.path.join(carpeta_servicio, nombre_carpeta_obs)
        
        # Crear esa subcarpeta
        os.makedirs(carpeta_obs, exist_ok=True)
        
        # Guardar la 4ta foto adentro de esa subcarpeta
        ruta_obs, nom_obs = guardar_foto(foto_observacion, carpeta_obs, "observacion")
        
        # ¡La magia! Copiamos la 1ra y la 3ra foto automáticamente a esta carpeta
        shutil.copy(ruta_gen, carpeta_obs)
        shutil.copy(ruta_piq, carpeta_obs)
        
        # Agregamos el link de la observación a la respuesta
        links_respuesta["foto_observacion"] = f"/fotos/{servicio}/{nombre_carpeta_obs}/{nom_obs}"
        links_respuesta["mensaje_alerta"] = f"Se creó el expediente de observación para el piquete {piquete}"

    return {
        "mensaje": "Fotos procesadas y organizadas correctamente",
        "urls": links_respuesta
    }