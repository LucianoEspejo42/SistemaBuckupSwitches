# Backup de Switches

Aplicación de escritorio en Python con interfaz gráfica (CustomTkinter) para gestionar backups automáticos de configuraciones de switches vía SSH y FTP.

## Características

- Conexión SSH a switches para validar credenciales.
- Validación y conexión con servidores FTP.
- Programación automática de backups mensuales.
- Edición y eliminación de switches.
- Interfaz gráfica clara y funcional.
- Gestión de tareas programadas.

## Requisitos

- Python 3.8 o superior
- Librerías:
  - `customtkinter`
  - `paramiko`
  - `ctkmessagebox`
  - `python-dateutil`

Estas se instalan automáticamente al ejecutar el programa.

## Uso

```bash
python app.py
