# PhoneCatalog V2 Internet

1. Descomprime el ZIP.
2. Ejecuta `INICIAR_PHONECATALOG.bat` (o `start_windows.bat`).
3. El navegador se abre automáticamente en http://127.0.0.1:5050
4. Escribe una marca y modelo exactos, por ejemplo `Samsung Galaxy A54 5G`.
5. Pulsa **BUSCAR EN INTERNET Y GUARDAR**.

El sistema busca páginas públicas en Internet, prioriza dominios oficiales del fabricante, consulta fuentes secundarias, extrae los campos técnicos que puede identificar y guarda el resultado en SQLite. También conserva las URLs y la fecha de consulta.

IMPORTANTE: las webs cambian su HTML y algunas bloquean consultas automatizadas. Por eso un campo puede quedar vacío aunque exista en Internet. La V2 no inventa esos campos: los deja sin dato para poder mejorarlos posteriormente con adaptadores específicos por fabricante/API.

La base de datos `phones.db` se crea junto al programa y crece con cada búsqueda. El botón de búsqueda local reutiliza los equipos ya descargados.
