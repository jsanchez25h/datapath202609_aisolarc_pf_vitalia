# Imagen del servicio de la mesa de preautorización.
#
# Una sola imagen sirve la API y la interfaz: `api/principal.py` monta `app_mesa`
# en /app como estáticos, así que no hay un segundo despliegue de front que se
# pueda quedar desalineado con el backend que lo alimenta.
#
# Lo que NO viaja en la imagen son las credenciales. `comun/config.py` lee
# `variables.sh` solo si existe, y lo hace con `os.environ.setdefault`: el
# entorno real siempre gana. En Cloud Run ese archivo no está y las claves
# entran como variables inyectadas desde Secret Manager.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Las dependencias van en su propia capa: el código cambia en cada despliegue,
# `requirements.txt` casi nunca, y reinstalar spaCy en cada build cuesta minutos.
COPY requirements.txt ./
RUN pip install -r requirements.txt \
 && python -m spacy download es_core_news_sm

COPY . .

# Cloud Run inyecta PORT y espera 0.0.0.0. Un solo trabajador: el caché
# semántico y los disyuntores del MCP viven en memoria del proceso, y con dos
# trabajadores el panel contaría la mitad de los aciertos.
ENV PORT=8080
CMD exec uvicorn api.principal:app --host 0.0.0.0 --port ${PORT} --workers 1
