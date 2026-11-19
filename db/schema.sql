CREATE TABLE IF NOT EXISTS eventos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    momento TEXT NOT NULL,          -- fecha y hora ISO 8601
    zona TEXT NOT NULL,             -- nombre de la zona vigilada
    falta_casco INTEGER NOT NULL,   -- 1 si faltaba el casco
    falta_chaleco INTEGER NOT NULL, -- 1 si faltaba el chaleco
    confianza REAL,                 -- confianza de la detección de persona
    ruta_captura TEXT,              -- imagen con la alerta
    latitud REAL,                   -- ubicación real (GPS del celular), NULL si no hay
    longitud REAL,
    precision_m REAL,               -- precisión del GPS en metros
    origen TEXT DEFAULT 'video'     -- 'video' (sistema.py) | 'app' (foto/video desde el celular)
);
CREATE INDEX IF NOT EXISTS idx_eventos_zona_momento ON eventos(zona, momento);
