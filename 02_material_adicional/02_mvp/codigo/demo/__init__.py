"""Puesta en pie de la demostración: levantar, poblar y capturar.

No es código de la plataforma. Es el andamio que deja el MVP en el estado
exacto que muestran las capturas del Anexo K, y existe por el veto **V2**: una
captura que no se puede rehacer no es evidencia. Con estos tres módulos,
cualquiera reconstruye las siete imágenes de `evidencias/pantallas/` desde una
base vacía y comprueba que dicen lo que dicen.

    python -m demo.servidor      # levanta el servicio en :8088 y lo deja vivo
    python -m demo.poblar        # borra la bandeja y la vuelve a llenar
    python -m demo.capturar      # rehace las seis capturas
"""
