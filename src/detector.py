"""Lógica de visión: clases del modelo y regla que asocia el equipo a cada persona."""
HELMET, JACKET, PERSON = 0, 1, 2


def centro(b):
    return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2


def asociado_casco(p, c):
    """El centro del casco cae en el tercio superior de la caja de la persona."""
    x1, y1, x2, y2 = p
    cx, cy = centro(c)
    return x1 <= cx <= x2 and y1 <= cy <= y1 + (y2 - y1) / 3


def asociado_chaleco(p, c):
    """El centro del chaleco cae entre el 30 % y el 75 % de la altura de la persona."""
    x1, y1, x2, y2 = p
    h = y2 - y1
    cx, cy = centro(c)
    return x1 <= cx <= x2 and y1 + 0.3 * h <= cy <= y1 + 0.75 * h


def faltas_persona(persona, cascos, chalecos):
    """Devuelve (falta_casco, falta_chaleco) para una caja de persona."""
    return (not any(asociado_casco(persona, c) for c in cascos),
            not any(asociado_chaleco(persona, c) for c in chalecos))


def separar(res):
    """Separa los resultados de YOLO en cascos, chalecos y personas (con confianza)."""
    cajas = res.boxes.xyxy.cpu().numpy()
    clases = res.boxes.cls.cpu().numpy().astype(int)
    confs = res.boxes.conf.cpu().numpy()
    cascos = [b for b, c in zip(cajas, clases) if c == HELMET]
    chalecos = [b for b, c in zip(cajas, clases) if c == JACKET]
    personas = [(b, cf) for b, c, cf in zip(cajas, clases, confs) if c == PERSON]
    return cascos, chalecos, personas


def equipo_con_conf(res):
    """Cascos y chalecos como listas de (caja, confianza), para dibujar su etiqueta."""
    cajas = res.boxes.xyxy.cpu().numpy()
    clases = res.boxes.cls.cpu().numpy().astype(int)
    confs = res.boxes.conf.cpu().numpy()
    return ([(b, float(c)) for b, k, c in zip(cajas, clases, confs) if k == HELMET],
            [(b, float(c)) for b, k, c in zip(cajas, clases, confs) if k == JACKET])
