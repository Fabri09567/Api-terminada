from sqlalchemy import create_engine, Column, Integer, String, Boolean, Float, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from datetime import datetime

# --- CONFIGURACIÓN DE LA BASE DE DATOS (SQLite) ---
SQLALCHEMY_DATABASE_URL = "sqlite:///./sistema_redes.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Esta es la clase base de la que heredan todas nuestras tablas
Base = declarative_base()

# (Acá abajo dejás tus class Usuario, class ReclamoRP y class Medicion tal cual los tenías)

class Usuario(Base):
    __tablename__ = "usuarios"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True) # ¡Acá está el cambio principal!
    password_hash = Column(String)
    rol = Column(String, default="CUADRILLA") # "CUADRILLA" o "ADMIN"
    activo = Column(Boolean, default=True)

class ReclamoRP(Base):
    __tablename__ = "reclamos_rp"
    
    id = Column(Integer, primary_key=True, index=True)
    numero_rp = Column(Integer, index=True)
    mes = Column(String)
    procedencia = Column(String) # "Corresponde" o "No corresponde"
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    creado_por = Column(Integer, ForeignKey("usuarios.id"))
    
    # Esta relación hace la "magia" para que un reclamo sepa qué mediciones tiene adentro
    mediciones = relationship("Medicion", back_populates="reclamo")

class Medicion(Base):
    __tablename__ = "mediciones"
    
    id = Column(Integer, primary_key=True, index=True)
    reclamo_id = Column(Integer, ForeignKey("reclamos_rp.id"), nullable=True) # Nulo si es Campaña
    tipo_operacion = Column(String) # "Campaña", "1ra medicion", etc.
    tramo_linea = Column(String, nullable=True) # "Inicio", "Medio", "Cola"
    
    # Datos técnicos
    servicio = Column(Integer)
    set_numero = Column(Integer)
    piquete = Column(Integer)
    tension_r = Column(Float) # Float es el equivalente a Decimal en Python
    tension_s = Column(Float)
    tension_t = Column(Float)
    
    # Multimedia y GPS
    foto_url = Column(String, nullable=True)
    latitud = Column(Float, nullable=True)
    longitud = Column(Float, nullable=True)
    fecha_hora = Column(DateTime, default=datetime.utcnow)
    
    # Conexión inversa hacia el reclamo padre
    reclamo = relationship("ReclamoRP", back_populates="mediciones")