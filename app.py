import subprocess
import sys

def instalar_si_falta(paquete, nombre_import=None):
    try:
        if nombre_import:
            __import__(nombre_import)
        else:
            __import__(paquete)
    except ImportError:
        print(f"Instalando {paquete}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", paquete])

# Instalar automáticamente si falta
instalar_si_falta("customtkinter")
instalar_si_falta("python-dateutil", "dateutil")
instalar_si_falta("paramiko")
instalar_si_falta("ctkmessagebox", "CTkMessagebox")  # El nombre del paquete puede variar


import customtkinter as ctk
import tkinter as tk
from tkinter import scrolledtext
from dateutil.relativedelta import relativedelta
import paramiko
from ftplib import FTP
import threading
import time
import datetime
import json
import re
from CTkMessagebox import CTkMessagebox
import os

# Configuración de tema
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

SWITCHES_FILE = "switches.json"
TASKS_FILE = "tareas_programadas.json"

def guardar_json(data, filename):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

def cargar_json(filename):
    if os.path.exists(filename):
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
                if filename == TASKS_FILE and not isinstance(data, list):
                    return []
                if filename == SWITCHES_FILE and not isinstance(data, dict):
                    return {}
                return data
        except json.JSONDecodeError:
            return [] if filename == TASKS_FILE else {}
    return [] if filename == TASKS_FILE else {}


class BackupSwitchApp:

    def __init__(self, root):
        self.root = root
        self.root.title("Backup de Switches - Configuración")
        self.root.geometry("1200x600+350+20")
        self.root.resizable(True, True)
        
        # Variables para almacenar datos
        self.ssh_client = None
        self.switch_data = {}
        self.ftp_data = {}
        self.switches = cargar_json(SWITCHES_FILE)
        self.scheduled_tasks = cargar_json(TASKS_FILE)
        self.selected_location = None  # Para almacenar la ubicación seleccionada
        self.selected_location_delated = None
        
        # Mapeo de ubicaciones a códigos de directorio
        self.location_codes = {
            "San Juan": "SJU",
            "Jachal": "JAL",
            "Gualcamayo": "GUA"
        }
        
        # Crear interfaz base
        self.create_interface()

    def create_interface(self):
        # Configuración principal con dos paneles
        self.main_frame = ctk.CTkFrame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Panel izquierdo (terminal)
        self.terminal_frame = ctk.CTkFrame(self.main_frame, corner_radius=10)
        self.terminal_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Título del terminal
        self.terminal_label = ctk.CTkLabel(self.terminal_frame, text="Terminal SSH", font=("Roboto", 16, "bold"))
        self.terminal_label.pack(pady=5)
        
        # Área de texto para el terminal
        self.terminal = scrolledtext.ScrolledText(self.terminal_frame, bg="#111111", fg="#00FF00", 
                                                font=("Consolas", 11), wrap=tk.WORD)
        self.terminal.pack(fill=tk.BOTH, expand=True, padx=8, pady=5)
        self.terminal.config(state=tk.DISABLED)  # Solo lectura
        
        # Panel derecho (interacción)
        self.control_frame = ctk.CTkFrame(self.main_frame, corner_radius=10, width=350)
        self.control_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        
        # Configuración de grid
        self.main_frame.grid_columnconfigure(0, weight=7)  # Terminal toma más espacio
        self.main_frame.grid_columnconfigure(1, weight=3)  # Panel de control
        self.main_frame.grid_rowconfigure(0, weight=1)
        
        # Mostrar menú principal
        self.show_main_menu()
        
        # Iniciar hilo para verificar tareas programadas
        self.start_task_checker_thread()

    def show_main_menu(self):
        # Limpiar panel derecho
        for widget in self.control_frame.winfo_children():
            widget.destroy()
            
        # Crear menú principal
        menu_label = ctk.CTkLabel(self.control_frame, text="Menú Principal", 
                                font=("Roboto", 18, "bold"))
        menu_label.pack(pady=(20, 25))
        
        # Opción 1: Agregar información del switch
        add_switch_btn = ctk.CTkButton(self.control_frame, text="Agregar información del switch", font=("Roboto", 12, "bold"),
                                    command=self.show_location_selection, height=45)
        add_switch_btn.pack(pady=10, padx=30, fill=tk.X)
        
        # Opción 2: Eliminar switch
        delete_switch_btn = ctk.CTkButton(self.control_frame, text="Eliminar switch", font=("Roboto", 12, "bold"),
                                        command=lambda: self.show_location_selection(action="delete"), height=45)
        delete_switch_btn.pack(pady=10, padx=30, fill=tk.X)
        
        # Opción 3: Editar switch
        edit_switch_btn = ctk.CTkButton(self.control_frame, text="Editar switch", font=("Roboto", 12, "bold"),
                                        command=lambda: self.show_location_selection(action="edit"), height=45)
        edit_switch_btn.pack(pady=10, padx=30, fill=tk.X)
        
        # Opción 4: Ver tareas programadas
        tasks_btn = ctk.CTkButton(self.control_frame, text="Ver tareas programadas", font=("Roboto", 12, "bold"),
                                command=self.show_scheduled_tasks_window, height=45)
        tasks_btn.pack(pady=10, padx=30, fill=tk.X)




#FuNCIONES PARA EDITAR SW

    def show_edit_switch_form(self):
        """Muestra el formulario para seleccionar qué editar: switch individual o zona completa"""
        # Limpiar panel derecho
        for widget in self.control_frame.winfo_children():
            widget.destroy()
        
        # Verificar si hay switches registrados
        if not self.switches:
            no_switches_label = ctk.CTkLabel(self.control_frame, text="No hay switches registrados", 
                                        font=("Roboto", 14))
            no_switches_label.pack(pady=30)
            
            back_btn = ctk.CTkButton(self.control_frame, text="Volver", 
                                command=self.show_main_menu, fg_color="gray")
            back_btn.pack(pady=10, padx=30, fill=tk.X)
            return
        
        # Crear formulario de edición
        form_label = ctk.CTkLabel(self.control_frame, text=f"Editar Switches - {self.selected_location_delated}", 
                                font=("Roboto", 16, "bold"))
        form_label.pack(pady=(20, 15))
        
        # Obtener switches de la ubicación seleccionada
        location_switches = []
        for key, data in self.switches.items():
            if data['switch_data']['location'] == self.selected_location_delated:
                location_switches.append((key, data))
        
        if not location_switches:
            no_switches_label = ctk.CTkLabel(self.control_frame, 
                                        text=f"No hay switches registrados en {self.selected_location_delated}", 
                                        font=("Roboto", 12))
            no_switches_label.pack(pady=20)
            
            back_btn = ctk.CTkButton(self.control_frame, text="Volver", 
                                command=lambda: self.show_location_selection(True), fg_color="gray")
            back_btn.pack(pady=10, padx=30, fill=tk.X)
            return
        
        # Opción 1: Editar todos los switches de la zona
        if len(location_switches) > 1:
            edit_all_btn = ctk.CTkButton(self.control_frame, 
                                    text=f"Editar todos los switches de {self.selected_location_delated}", 
                                    font=("Roboto", 12, "bold"),
                                    command=self.show_bulk_edit_form, 
                                    height=45)
            edit_all_btn.pack(pady=10, padx=30, fill=tk.X)
            
            # Separador
            separator = ctk.CTkLabel(self.control_frame, text="o selecciona un switch individual:", font=("Roboto", 13))
            separator.pack(pady=5)
        
        # Crear lista de switches individuales para editar
        switch_frame = ctk.CTkScrollableFrame(self.control_frame, height=250)
        switch_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        for key, data in location_switches:
            switch_row = ctk.CTkFrame(switch_frame)
            switch_row.pack(fill=tk.X, padx=5, pady=5)
            
            # Mostrar IP y usuario actual
            ip = data['switch_data']['ip']
            user = data['switch_data']['user']
            
            switch_label = ctk.CTkLabel(switch_row, text=f"IP: {ip} - Usuario: {user}", anchor="w")
            switch_label.pack(side=tk.LEFT, padx=10, pady=5, fill=tk.X, expand=True)
            
            edit_btn = ctk.CTkButton(switch_row, text="Editar", width=80,
                                command=lambda k=key: self.show_individual_edit_form(k),
                                fg_color="orange", hover_color="#FF8C00")
            edit_btn.pack(side=tk.RIGHT, padx=10, pady=5)
        
        # Botón para volver
        back_btn = ctk.CTkButton(self.control_frame, text="Volver", 
                            command=lambda: self.show_location_selection("edit"), fg_color="gray")
        back_btn.pack(pady=20, padx=30, fill=tk.X)

    def show_bulk_edit_form(self):
        """Formulario para editar todos los switches de una zona"""
        # Limpiar panel derecho
        for widget in self.control_frame.winfo_children():
            widget.destroy()
        
        # Crear formulario de edición masiva
        form_label = ctk.CTkLabel(self.control_frame, 
                                text=f"Editar todos los switches de {self.selected_location_delated}", 
                                font=("Roboto", 16, "bold"))
        form_label.pack(pady=(20, 15))
        
        # Información
        info_label = ctk.CTkLabel(self.control_frame, 
                                text="Los campos vacíos no se modificarán", 
                                font=("Roboto", 10),
                                text_color="gray")
        info_label.pack(pady=5)
        
        # Campo de usuario
        user_frame = ctk.CTkFrame(self.control_frame, fg_color="transparent")
        user_frame.pack(fill=tk.X, padx=20, pady=10)
        
        user_label = ctk.CTkLabel(user_frame, text="Nuevo Usuario:", width=120)
        user_label.pack(side=tk.LEFT, padx=5)
        
        self.bulk_user_entry = ctk.CTkEntry(user_frame, placeholder_text="Dejar vacío para no cambiar")
        self.bulk_user_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Campo de contraseña
        password_frame = ctk.CTkFrame(self.control_frame, fg_color="transparent")
        password_frame.pack(fill=tk.X, padx=20, pady=10)
        
        password_label = ctk.CTkLabel(password_frame, text="Nueva Contraseña:", width=120)
        password_label.pack(side=tk.LEFT, padx=5)
        
        self.bulk_password_entry = ctk.CTkEntry(password_frame, show="*", placeholder_text="Dejar vacío para no cambiar")
        self.bulk_password_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Campo de contraseña enable
        enable_frame = ctk.CTkFrame(self.control_frame, fg_color="transparent")
        enable_frame.pack(fill=tk.X, padx=20, pady=10)
        
        enable_label = ctk.CTkLabel(enable_frame, text="Nuevo Enable Pass:", width=120)
        enable_label.pack(side=tk.LEFT, padx=5)
        
        self.bulk_enable_entry = ctk.CTkEntry(enable_frame, show="*", placeholder_text="Dejar vacío para no cambiar")
        self.bulk_enable_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Lista de switches que serán afectados
        affected_frame = ctk.CTkFrame(self.control_frame)
        affected_frame.pack(fill=tk.X, padx=20, pady=10)
        
        affected_label = ctk.CTkLabel(affected_frame, text="Switches que serán modificados:", font=("Roboto", 12, "bold"))
        affected_label.pack(pady=5)
        
        # Obtener switches de la ubicación
        location_switches = []
        for key, data in self.switches.items():
            if data['switch_data']['location'] == self.selected_location_delated:
                location_switches.append(data['switch_data']['ip'])
        
        switches_text = ", ".join(location_switches)
        switches_label = ctk.CTkLabel(affected_frame, text=switches_text, font=("Roboto", 10))
        switches_label.pack(pady=5, padx=10)
        
        # Botón para aplicar cambios
        apply_btn = ctk.CTkButton(self.control_frame, text="Aplicar Cambios", 
                                command=self.apply_bulk_edit,
                                fg_color="green", hover_color="#006400")
        apply_btn.pack(pady=15, padx=30, fill=tk.X)
        
        # Botón para volver
        back_btn = ctk.CTkButton(self.control_frame, text="Cancelar", 
                            command=self.show_edit_switch_form, fg_color="gray")
        back_btn.pack(pady=10, padx=30, fill=tk.X)

    def show_individual_edit_form(self, switch_key):
        """Formulario para editar un switch individual"""
        # Limpiar panel derecho
        for widget in self.control_frame.winfo_children():
            widget.destroy()
        
        # Obtener datos actuales del switch
        switch_data = self.switches[switch_key]['switch_data']
        
        # Crear formulario de edición individual
        form_label = ctk.CTkLabel(self.control_frame, 
                                text=f"Editar Switch {switch_data['ip']}", 
                                font=("Roboto", 16, "bold"))
        form_label.pack(pady=(20, 15))
        
        # Mostrar ubicación
        location_label = ctk.CTkLabel(self.control_frame, 
                                    text=f"Ubicación: {switch_data['location']}", 
                                    font=("Roboto", 12))
        location_label.pack(pady=5)
        
        # Campo de usuario (prellenado con valor actual)
        user_frame = ctk.CTkFrame(self.control_frame, fg_color="transparent")
        user_frame.pack(fill=tk.X, padx=20, pady=10)
        
        user_label = ctk.CTkLabel(user_frame, text="Usuario:", width=100)
        user_label.pack(side=tk.LEFT, padx=5)
        
        self.edit_user_entry = ctk.CTkEntry(user_frame)
        self.edit_user_entry.insert(0, switch_data['user'])
        self.edit_user_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Campo de contraseña
        password_frame = ctk.CTkFrame(self.control_frame, fg_color="transparent")
        password_frame.pack(fill=tk.X, padx=20, pady=10)
        
        password_label = ctk.CTkLabel(password_frame, text="Contraseña:", width=100)
        password_label.pack(side=tk.LEFT, padx=5)
        
        self.edit_password_entry = ctk.CTkEntry(password_frame, show="*")
        self.edit_password_entry.insert(0, switch_data['password'])
        self.edit_password_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Campo de contraseña enable
        enable_frame = ctk.CTkFrame(self.control_frame, fg_color="transparent")
        enable_frame.pack(fill=tk.X, padx=20, pady=10)
        
        enable_label = ctk.CTkLabel(enable_frame, text="Enable Pass:", width=100)
        enable_label.pack(side=tk.LEFT, padx=5)
        
        self.edit_enable_entry = ctk.CTkEntry(enable_frame, show="*")
        self.edit_enable_entry.insert(0, switch_data.get('enable_password', ''))
        self.edit_enable_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Botón para validar conexión con nuevos datos
        validate_btn = ctk.CTkButton(self.control_frame, text="Validar y Guardar Cambios", 
                                command=lambda: self.validate_and_save_individual_edit(switch_key))
        validate_btn.pack(pady=15, padx=30, fill=tk.X)
        
        # Botón para volver
        back_btn = ctk.CTkButton(self.control_frame, text="Cancelar", 
                            command=self.show_edit_switch_form, fg_color="gray")
        back_btn.pack(pady=10, padx=30, fill=tk.X)

    def apply_bulk_edit(self):
        """Aplica los cambios a todos los switches de la zona"""
        # Obtener nuevos valores
        new_user = self.bulk_user_entry.get().strip()
        new_password = self.bulk_password_entry.get()
        new_enable = self.bulk_enable_entry.get()
        
        # Verificar que al menos un campo tenga contenido
        if not any([new_user, new_password, new_enable]):
            CTkMessagebox(title="Error", message="Debe especificar al menos un campo para modificar", icon="cancel")
            return
        
        # Confirmar cambios
        changes = []
        if new_user:
            changes.append(f"Usuario: {new_user}")
        if new_password:
            changes.append("Contraseña: [NUEVA]")
        if new_enable:
            changes.append("Enable Pass: [NUEVA]")
        
        changes_text = "\n".join(changes)
        
        result = CTkMessagebox(title="Confirmar Cambios Masivos", 
                            message=f"Se aplicarán los siguientes cambios a todos los switches de {self.selected_location_delated}:\n\n{changes_text}\n\n¿Continuar?",
                            icon="question", 
                            option_1="Sí", 
                            option_2="No")
        
        if result.get() == "No":
            return
        
        # Aplicar cambios a todos los switches de la ubicación
        switches_updated = 0
        switches_failed = 0
        
        for key, data in self.switches.items():
            if data['switch_data']['location'] == self.selected_location_delated:
                try:
                    # Actualizar solo los campos especificados
                    if new_user:
                        self.switches[key]['switch_data']['user'] = new_user
                    if new_password:
                        self.switches[key]['switch_data']['password'] = new_password
                    if new_enable:
                        self.switches[key]['switch_data']['enable_password'] = new_enable
                    
                    # Actualizar también las tareas programadas para este switch
                    for task in self.scheduled_tasks:
                        if (task["switch_data"]["ip"] == data['switch_data']['ip'] and 
                            task["switch_data"]["location"] == data['switch_data']['location']):
                            if new_user:
                                task["switch_data"]["user"] = new_user
                            if new_password:
                                task["switch_data"]["password"] = new_password
                            if new_enable:
                                task["switch_data"]["enable_password"] = new_enable
                    
                    switches_updated += 1
                    self.write_to_terminal(f"Switch {data['switch_data']['ip']} actualizado correctamente")
                    
                except Exception as e:
                    switches_failed += 1
                    self.write_to_terminal(f"Error al actualizar switch {data['switch_data']['ip']}: {str(e)}")
        
        # Guardar cambios
        guardar_json(self.switches, SWITCHES_FILE)
        guardar_json(self.scheduled_tasks, TASKS_FILE)
        
        # Mostrar resultado
        message = f"Actualización masiva completada:\n\n"
        message += f"Switches actualizados: {switches_updated}\n"
        if switches_failed > 0:
            message += f"Switches con errores: {switches_failed}"
        
        CTkMessagebox(title="Actualización Completada", message=message, icon="check")
        
        # Volver al menú principal
        self.show_main_menu()

    def validate_and_save_individual_edit(self, switch_key):
        """Valida la conexión con los nuevos datos y guarda los cambios"""
        # Obtener nuevos datos
        new_user = self.edit_user_entry.get().strip()
        new_password = self.edit_password_entry.get()
        new_enable = self.edit_enable_entry.get()
        
        # Validar campos básicos
        if not all([new_user, new_password]):
            CTkMessagebox(title="Error", message="Usuario y contraseña son obligatorios", icon="cancel")
            return
        
        # Obtener datos actuales del switch
        current_data = self.switches[switch_key]['switch_data'].copy()
        
        # Crear datos temporales para validación
        temp_data = current_data.copy()
        temp_data.update({
            'user': new_user,
            'password': new_password,
            'enable_password': new_enable if new_enable else new_password
        })
        
        self.write_to_terminal(f"Validando nuevas credenciales para {temp_data['ip']}...")
        
        # Validar conexión en segundo plano
        self.temp_edit_data = {
            'switch_key': switch_key,
            'new_data': temp_data
        }
        
        threading.Thread(target=self._validate_edit_connection).start()

    def _validate_edit_connection(self):
        """Valida la conexión SSH con las nuevas credenciales"""
        try:
            switch_key = self.temp_edit_data['switch_key']
            new_data = self.temp_edit_data['new_data']
            
            # Crear conexión SSH para validar
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            self.write_to_terminal(f"Conectando a {new_data['ip']} con nuevas credenciales...")
            ssh_client.connect(
                new_data['ip'], 
                username=new_data['user'], 
                password=new_data['password'],
                timeout=10
            )
            
            # Verificar acceso básico
            stdin, stdout, stderr = ssh_client.exec_command("show version | include uptime")
            output = stdout.read().decode('utf-8')
            error = stderr.read().decode('utf-8')
            
            ssh_client.close()
            
            if error:
                raise Exception(f"Error de acceso: {error}")
            
            self.write_to_terminal("Nuevas credenciales validadas correctamente")
            
            # Guardar cambios si la validación fue exitosa
            self.root.after(0, lambda: self._save_individual_edit(switch_key, new_data))
            
        except Exception as e:
            error_msg = str(e)
            self.write_to_terminal(f"Error de validación: {error_msg}")
            self.root.after(0, lambda: CTkMessagebox(title="Error de Validación", 
                                                message=f"No se pudo conectar con las nuevas credenciales: {error_msg}", 
                                                icon="cancel"))

    def _save_individual_edit(self, switch_key, new_data):
        """Guarda los cambios del switch individual después de la validación exitosa"""
        try:
            # Actualizar datos del switch
            self.switches[switch_key]['switch_data'].update({
                'user': new_data['user'],
                'password': new_data['password'],
                'enable_password': new_data['enable_password']
            })
            
            # Actualizar también las tareas programadas para este switch
            for task in self.scheduled_tasks:
                if (task["switch_data"]["ip"] == new_data['ip'] and 
                    task["switch_data"]["location"] == new_data['location']):
                    task["switch_data"]["user"] = new_data['user']
                    task["switch_data"]["password"] = new_data['password']
                    task["switch_data"]["enable_password"] = new_data['enable_password']
            
            # Guardar cambios
            guardar_json(self.switches, SWITCHES_FILE)
            guardar_json(self.scheduled_tasks, TASKS_FILE)
            
            self.write_to_terminal(f"Switch {new_data['ip']} actualizado correctamente")
            
            # Mostrar mensaje de éxito
            CTkMessagebox(title="Éxito", 
                        message=f"Switch {new_data['ip']} actualizado correctamente", 
                        icon="check")
            
            # Volver al menú principal
            self.show_main_menu()
            
        except Exception as e:
            self.write_to_terminal(f"Error al guardar cambios: {str(e)}")
            CTkMessagebox(title="Error", message=f"Error al guardar cambios: {str(e)}", icon="cancel")

    def show_location_selection(self, action="add"):
        # Limpiar panel derecho
        for widget in self.control_frame.winfo_children():
            widget.destroy()
        
        # Determinar el título basado en la acción
        titles = {
            "add": "Seleccionar Ubicación",
            "delete": "Seleccionar Ubicación para Eliminar",
            "edit": "Seleccionar Ubicación para Editar"
        }
        
        # Crear formulario de selección de ubicación
        form_label = ctk.CTkLabel(self.control_frame, text=titles.get(action, "Seleccionar Ubicación"), 
                                font=("Roboto", 16, "bold"))
        form_label.pack(pady=(20, 15))
        
        # Botones para cada ubicación
        sju_btn = ctk.CTkButton(self.control_frame, text="San Juan", 
                            command=lambda: self.set_location_and_continue("San Juan", action),
                            font=("Roboto", 12, "bold"), height=45)
        sju_btn.pack(pady=10, padx=30, fill=tk.X)
        
        gua_btn = ctk.CTkButton(self.control_frame, text="Gualcamayo", 
                            command=lambda: self.set_location_and_continue("Gualcamayo", action),
                            font=("Roboto", 12, "bold"), height=45)
        gua_btn.pack(pady=10, padx=30, fill=tk.X)
        
        jal_btn = ctk.CTkButton(self.control_frame, text="Jachal", 
                            command=lambda: self.set_location_and_continue("Jachal", action),
                            font=("Roboto", 12, "bold"), height=45)
        jal_btn.pack(pady=10, padx=30, fill=tk.X)
        
        # Botón para volver
        back_btn = ctk.CTkButton(self.control_frame, text="Cancelar", 
                                command=self.show_main_menu, fg_color="gray")
        back_btn.pack(pady=10, padx=30, fill=tk.X)

    def set_location_and_continue(self, location, action):
        if action == "delete":
            self.selected_location_delated = location
            self.write_to_terminal(f"Ubicación seleccionada para eliminar switch: {location}")
            self.show_delete_switch_form()
        elif action == "edit":
            self.selected_location_delated = location
            self.write_to_terminal(f"Ubicación seleccionada para editar switch: {location}")
            self.show_edit_switch_form()
        else:  # action == "add"
            self.selected_location = location
            self.write_to_terminal(f"Ubicación seleccionada: {location}")
            self.show_switch_form()



    def show_switch_form(self):
        # Limpiar panel derecho
        for widget in self.control_frame.winfo_children():
            widget.destroy()
                
        # Crear formulario de switch
        form_label = ctk.CTkLabel(self.control_frame, text=f"Información del Switch - {self.selected_location}", 
                                font=("Roboto", 16, "bold"))
        form_label.pack(pady=(20, 15))
        
        # Campos para la información del switch
        ip_frame = ctk.CTkFrame(self.control_frame, fg_color="transparent")
        ip_frame.pack(fill=tk.X, padx=20, pady=5)
        
        ip_label = ctk.CTkLabel(ip_frame, text="IP del Switch:", width=100)
        ip_label.pack(side=tk.LEFT, padx=5)
        
        self.ip_entry = ctk.CTkEntry(ip_frame)
        self.ip_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Campo de usuario
        user_frame = ctk.CTkFrame(self.control_frame, fg_color="transparent")
        user_frame.pack(fill=tk.X, padx=20, pady=5)
        
        user_label = ctk.CTkLabel(user_frame, text="Usuario:", width=100)
        user_label.pack(side=tk.LEFT, padx=5)
        
        self.user_entry = ctk.CTkEntry(user_frame)
        self.user_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Campo de contraseña
        password_frame = ctk.CTkFrame(self.control_frame, fg_color="transparent")
        password_frame.pack(fill=tk.X, padx=20, pady=5)
        
        password_label = ctk.CTkLabel(password_frame, text="Contraseña:", width=100)
        password_label.pack(side=tk.LEFT, padx=5)
        
        self.password_entry = ctk.CTkEntry(password_frame, show="*")
        self.password_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Campo de contraseña enable (opcional)
        enable_frame = ctk.CTkFrame(self.control_frame, fg_color="transparent")
        enable_frame.pack(fill=tk.X, padx=20, pady=5)
        
        enable_label = ctk.CTkLabel(enable_frame, text="Enable Pass:", width=100)
        enable_label.pack(side=tk.LEFT, padx=5)
        
        self.enable_entry = ctk.CTkEntry(enable_frame, show="*")
        self.enable_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Botón para validar conexión
        validate_btn = ctk.CTkButton(self.control_frame, text="Validar Conexión", 
                                    command=self.validate_switch_connection)
        validate_btn.pack(pady=15, padx=30, fill=tk.X)
        
        # Botón para volver
        back_btn = ctk.CTkButton(self.control_frame, text="Cancelar", 
                                command=self.show_location_selection, fg_color="gray")
        back_btn.pack(pady=10, padx=30, fill=tk.X)

    def write_to_terminal(self, text):
        # Método para escribir en el terminal con marca de tiempo
        timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        message = f"{timestamp} {text}\n"
        
        # Actualizar en el hilo principal
        def update_terminal():
            self.terminal.config(state=tk.NORMAL)
            self.terminal.insert(tk.END, message)
            self.terminal.see(tk.END)  # Desplazar al final
            self.terminal.config(state=tk.DISABLED)
        
        # Ejecutar en el hilo principal si estamos en otro hilo
        if threading.current_thread() is threading.main_thread():
            update_terminal()
        else:
            self.root.after(0, update_terminal)

    def validate_switch_connection(self):
        # Obtener datos del formulario
        ip = self.ip_entry.get().strip()
        user = self.user_entry.get().strip()
        password = self.password_entry.get()
        enable_pass = self.enable_entry.get()
        
        # Validar campos básicos
        if not all([ip, user, password]):
            CTkMessagebox(title="Error", message="IP, usuario y contraseña son obligatorios", icon="cancel")
            return
        
        # Comprobar si el switch ya existe en esta ubicación
        switch_key = f"{self.selected_location}_{ip}"
        if switch_key in self.switches:
            result = CTkMessagebox(title="Switch Existente", 
                              message=f"Este switch ya está configurado para {self.selected_location}. ¿Desea actualizarlo?",
                              icon="question", 
                              option_1="Sí", 
                              option_2="No")
            if result.get() == "No":
                return

        # Guardar datos temporalmente
        self.switch_data = {
            "ip": ip,
            "user": user,
            "password": password,
            "enable_password": enable_pass,  # Si no hay enable, usar la contraseña normal
            "location": self.selected_location,
            "location_code": self.location_codes[self.selected_location]
        }
        
        # Intentar conexión en segundo plano
        self.write_to_terminal(f"Conectando al switch en {self.selected_location}... Por favor espere.")
        threading.Thread(target=self._connect_to_switch).start()

    def _connect_to_switch(self):
        try:
            # Cerrar cliente SSH anterior si existe
            if self.ssh_client:
                self.ssh_client.close()
                    
            # Crear nueva conexión SSH
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
            # Conectar al switch
            self.write_to_terminal(f"Intentando conectar a {self.switch_data['ip']}...")
            self.ssh_client.connect(
                self.switch_data['ip'], 
                username=self.switch_data['user'], 
                password=self.switch_data['password'],
                timeout=10
            )
                
            # Verificar modo enable
            self.write_to_terminal("Conexión SSH establecida.")
            self.write_to_terminal("Probando acceso privilegiado...")
                
            # Usar comando básico para verificar acceso
            stdin, stdout, stderr = self.ssh_client.exec_command("show version | include uptime")
            output = stdout.read().decode('utf-8')
            error = stderr.read().decode('utf-8')
                
            if error:
                self.root.after(0, lambda: CTkMessagebox(title="Error", 
                                                    message=f"Error de acceso: {error}", 
                                                    icon="cancel"))
                return
                
            self.write_to_terminal(f"Respuesta del switch: {output}")
            self.write_to_terminal("Conexión validada correctamente.")
                
            # Continuar con el formulario FTP
            self.root.after(0, self.show_ftp_form)
                
        except Exception as e:
            error_msg = str(e)
            self.write_to_terminal(f"Error de conexión: {error_msg}")
            self.root.after(0, lambda: CTkMessagebox(title="Error de Conexión", 
                                                message=f"No se pudo conectar al switch: {error_msg}", 
                                                icon="cancel"))

    def show_ftp_form(self):
        # Limpiar panel derecho
        for widget in self.control_frame.winfo_children():
            widget.destroy()
                
        # Crear formulario de FTP
        form_label = ctk.CTkLabel(self.control_frame, text="Información del Servidor FTP", 
                                font=("Roboto", 16, "bold"))
        form_label.pack(pady=(20, 15))
        
        # Campos para la información del FTP
        ftp_ip_frame = ctk.CTkFrame(self.control_frame, fg_color="transparent")
        ftp_ip_frame.pack(fill=tk.X, padx=20, pady=5)
        
        ftp_ip_label = ctk.CTkLabel(ftp_ip_frame, text="IP del Servidor:", width=100)
        ftp_ip_label.pack(side=tk.LEFT, padx=5)
        
        self.ftp_ip_entry = ctk.CTkEntry(ftp_ip_frame)
        self.ftp_ip_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        # Establecer valor predeterminado para IP
        self.ftp_ip_entry.insert(0, "10.90.1.98")
        
        # Campo de usuario FTP
        ftp_user_frame = ctk.CTkFrame(self.control_frame, fg_color="transparent")
        ftp_user_frame.pack(fill=tk.X, padx=20, pady=5)
        
        ftp_user_label = ctk.CTkLabel(ftp_user_frame, text="Usuario FTP:", width=100)
        ftp_user_label.pack(side=tk.LEFT, padx=5)
        
        self.ftp_user_entry = ctk.CTkEntry(ftp_user_frame)
        self.ftp_user_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        # Establecer valor predeterminado para usuario
        self.ftp_user_entry.insert(0, "user1")
        
        # Campo de contraseña FTP
        ftp_password_frame = ctk.CTkFrame(self.control_frame, fg_color="transparent")
        ftp_password_frame.pack(fill=tk.X, padx=20, pady=5)
        
        ftp_password_label = ctk.CTkLabel(ftp_password_frame, text="Contraseña:", width=100)
        ftp_password_label.pack(side=tk.LEFT, padx=5)
        
        self.ftp_password_entry = ctk.CTkEntry(ftp_password_frame, show="*")
        self.ftp_password_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        # Establecer valor predeterminado para contraseña
        self.ftp_password_entry.insert(0, "1234")
        
        # Botón para validar conexión FTP
        validate_btn = ctk.CTkButton(self.control_frame, text="Validar Conexión FTP", 
                                command=self.validate_ftp_connection)
        validate_btn.pack(pady=15, padx=30, fill=tk.X)
        
        # Botón para volver
        back_btn = ctk.CTkButton(self.control_frame, text="Atrás", 
                                command=self.show_switch_form, fg_color="gray")
        back_btn.pack(pady=10, padx=30, fill=tk.X)

    def validate_ftp_connection(self):
        # Obtener datos del formulario FTP
        ftp_ip = self.ftp_ip_entry.get().strip()
        ftp_user = self.ftp_user_entry.get().strip()
        ftp_password = self.ftp_password_entry.get()
        
        # Validar campos
        if not all([ftp_ip, ftp_user, ftp_password]):
            CTkMessagebox(title="Error", message="Todos los campos FTP son obligatorios", icon="cancel")
            return
        
        # Guardar datos temporalmente
        self.ftp_data = {
            "server": ftp_ip,
            "user": ftp_user,
            "password": ftp_password
        }
        
        # Intentar conexión FTP en segundo plano
        self.write_to_terminal("Conectando al servidor FTP... Por favor espere.")
        threading.Thread(target=self._connect_to_ftp).start()

    def _connect_to_ftp(self):
        try:
            self.write_to_terminal(f"Intentando conectar al servidor FTP {self.ftp_data['server']}...")
            
            # Intentar conexión FTP
            #ftp = FTP_TLS()
            #ftp.connect(self.ftp_data['server'])
            #ftp.auth() #Establesco canal seguro
            #ftp.prot_p() #Protege el canal de datos 
            ftp = FTP(self.ftp_data['server'])
            ftp.login(self.ftp_data['user'], self.ftp_data['password'])
            
            # Verificar conexión listando directorio raíz
            files = ftp.nlst()
            self.write_to_terminal(f"Conexión FTP establecida. Contenido de directorio: {len(files)} archivos")

            
            # Obtener el código de ubicación
            location_code = f"{self.switch_data["location_code"]}"  # SJU, GUA o JAL
            
            # Verificar/crear la carpeta de ubicación
            try:
                ftp.cwd(location_code)
                self.write_to_terminal(f"Directorio '{location_code}' encontrado")
            except:
                self.write_to_terminal(f"Directorio '{location_code}' no encontrado, creándolo...")
                ftp.mkd(location_code)
                ftp.cwd(location_code)
                
            # Obtener último octeto de la IP para nombrar el subdirectorio
            ip_parts = self.switch_data['ip'].split('.')
            last_octet = ip_parts[-1]
            
            # Verificar/crear la carpeta del octeto
            try:
                ftp.cwd(last_octet)
                self.write_to_terminal(f"Directorio '{last_octet}' encontrado")
            except:
                self.write_to_terminal(f"Directorio '{last_octet}' no encontrado, creándolo...")
                ftp.mkd(last_octet)
                ftp.cwd(last_octet)
                
            # Verificar/crear la carpeta BKP-Mensual
            try:
                ftp.cwd("BKP-Mensual")
                self.write_to_terminal("Directorio 'BKP-Mensual' encontrado")
            except:
                self.write_to_terminal("Directorio 'BKP-Mensual' no encontrado, creándolo...")
                ftp.mkd("BKP-Mensual")
                ftp.cwd("BKP-Mensual")
                
            # Cerrar conexión FTP
            ftp.quit()
            
            # Clave única para este switch (combinación de ubicación e IP)
            switch_key = f"{self.switch_data['location']}_{self.switch_data['ip']}"
            
            # Comprobar si el switch ya existe
            if switch_key in self.switches:
                # Eliminar tareas programadas anteriores para este switch
                for task in self.scheduled_tasks[:]:
                    if task["switch_data"]["ip"] == self.switch_data["ip"] and \
                       task["switch_data"]["location"] == self.switch_data["location"]:
                        self.scheduled_tasks.remove(task)
                        self.write_to_terminal(f"Tarea programada anterior para {switch_key} eliminada")
            
            # Guardar los datos del switch en el diccionario
            self.switches[switch_key] = {
                'switch_data': self.switch_data.copy(),
                'ftp_data': self.ftp_data.copy()
            }

            guardar_json(self.switches, SWITCHES_FILE)
            
            # Programar backup mensual automático
            self.schedule_monthly_backup(self.switch_data.copy(), self.ftp_data.copy())
            
            # Mostrar mensaje de éxito y volver al menú principal
            def show_success_and_return():
                CTkMessagebox(title="Éxito", 
                             message=f"Switch {self.switch_data['ip']} en {self.switch_data['location']} " +
                                     f"agregado correctamente.\nSe ha programado un backup mensual automático.", 
                             icon="check")
                self.show_main_menu()
                
            # Programar la función combinada
            self.root.after(0, show_success_and_return)
                
        except Exception as e:
            error_msg = str(e)
            self.write_to_terminal(f"Error de conexión FTP: {error_msg}")
            self.root.after(0, lambda: CTkMessagebox(title="Error de Conexión FTP", 
                                                message=f"No se pudo conectar al servidor FTP: {error_msg}", 
                                                icon="cancel"))

    def schedule_monthly_backup(self, switch_data, ftp_data):
        """Programa una tarea de backup para ejecutarse en el día 5 de cada mes"""
        # Obtener la fecha del próximo mes (primer día a las 3:00 AM)
        now = datetime.datetime.now()

        next_month = (now + relativedelta(months=1)).replace(day=5, hour=3, minute=0, second=0, microsecond=0)
        
        # Identificador único para esta tarea (ubicación + IP)
        task_id = f"{switch_data['location']}_{switch_data['ip']}"
        
        # Crear la tarea programada
        task = {
            "id": task_id,
            "time": next_month.strftime("%Y-%m-%d %H:%M:%S"),
            "switch_data": switch_data,
            "ftp_data": ftp_data,
            "recurring": "monthly"  # Indicar que es una tarea recurrente mensual
        }
        
        self.scheduled_tasks.append(task)
        guardar_json(self.scheduled_tasks, TASKS_FILE)
        self.write_to_terminal(f"Backup mensual programado para {switch_data['ip']} en {switch_data['location']} - " +
                              f"Próxima ejecución: {next_month.strftime('%Y-%m-%d %H:%M')}")

    def show_delete_switch_form(self):
        # Limpiar panel derecho
        for widget in self.control_frame.winfo_children():
            widget.destroy()
        
        # Verificar si hay switches registrados
        if not self.switches:
            no_switches_label = ctk.CTkLabel(self.control_frame, text="No hay switches registrados", 
                                        font=("Roboto", 14))
            no_switches_label.pack(pady=30)
            
            back_btn = ctk.CTkButton(self.control_frame, text="Volver", 
                                command=self.show_main_menu, fg_color="gray")
            back_btn.pack(pady=10, padx=30, fill=tk.X)
            return
        
        # Crear formulario de eliminación
        form_label = ctk.CTkLabel(self.control_frame, text="Eliminar Switch", 
                                font=("Roboto", 16, "bold"))
        form_label.pack(pady=(20, 15))
        
        # Crear lista de switches disponibles
        switch_frame = ctk.CTkScrollableFrame(self.control_frame, height=300)
        switch_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        for key, data in self.switches.items():
            if data['switch_data']['location'] == self.selected_location_delated:
                switch_row = ctk.CTkFrame(switch_frame)
                switch_row.pack(fill=tk.X, padx=5, pady=5)
                
                # Mostrar IP y ubicación
                location = data['switch_data']['location']
                ip = data['switch_data']['ip']
                
                switch_label = ctk.CTkLabel(switch_row, text=f"{location} - IP: {ip}", anchor="w")
                switch_label.pack(side=tk.LEFT, padx=10, pady=5, fill=tk.X, expand=True)
                
                delete_btn = ctk.CTkButton(switch_row, text="Eliminar", width=80,
                                        command=lambda k=key: self.delete_switch(k),
                                        fg_color="darkred", hover_color="#8B0000")
                delete_btn.pack(side=tk.RIGHT, padx=10, pady=5)
        
        # Botón para volver
        back_btn = ctk.CTkButton(self.control_frame, text="Volver", 
                            command= lambda: self.show_location_selection("delete"), fg_color="gray")
        back_btn.pack(pady=20, padx=30, fill=tk.X)

    def delete_switch(self, switch_key):
        try:
            # Obtener los datos del switch antes de eliminarlo
            switch_data = self.switches[switch_key]['switch_data']
            ip = switch_data['ip']
            location = switch_data['location']
            
            # Eliminar el switch del diccionario
            del self.switches[switch_key]

            guardar_json(self.switches, SWITCHES_FILE)
            
            # Eliminar tareas programadas asociadas a este switch
            for task in self.scheduled_tasks[:]:  # Usar copia para iterar
                if task["switch_data"]["ip"] == ip and task["switch_data"]["location"] == location:
                    self.scheduled_tasks.remove(task)

            #Guardamos los datos en el JSON
            guardar_json(self.scheduled_tasks, TASKS_FILE)

            
            self.write_to_terminal(f"Switch {ip} en {location} eliminado correctamente")
            
            # Mostrar mensaje de confirmación
            CTkMessagebox(title="Éxito", message=f"Switch {ip} en {location} eliminado correctamente", icon="check")
            
            # Refrescar la vista
            self.show_delete_switch_form()
            
        except Exception as e:
            self.write_to_terminal(f"Error al eliminar switch: {str(e)}")
            CTkMessagebox(title="Error", message=f"Error al eliminar switch: {str(e)}", icon="cancel")

    def show_scheduled_tasks_window(self):
        # Crear ventana independiente para mostrar tareas programadas
        tasks_window = ctk.CTkToplevel(self.root)
        tasks_window.title("Tareas Programadas")
        tasks_window.geometry("800x500")  # Aumenté la altura para el control de ordenamiento
        tasks_window.resizable(False, False)
        tasks_window.grab_set()  # Hacer modal
        
        # Título
        tasks_label = ctk.CTkLabel(tasks_window, text="Tareas Programadas", font=("Roboto", 16, "bold"))
        tasks_label.pack(pady=(20, 10))
        
        # Marco para los controles (filtro y ordenamiento)
        controls_frame = ctk.CTkFrame(tasks_window)
        controls_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        # Marco para el filtro de ubicación
        filter_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        filter_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Etiqueta para el filtro
        filter_label = ctk.CTkLabel(filter_frame, text="Filtrar por ubicación:", font=("Roboto", 12, 'bold'))
        filter_label.pack(side=tk.LEFT, padx=(10, 5))
        
        # Variable para almacenar la selección
        selected_location = tk.StringVar(value="Todas")
        
        # Lista de ubicaciones disponibles
        locations = ["Todas", "San Juan", "Jachal", "Gualcamayo"]
        
        # Crear ComboBox para seleccionar la ubicación
        location_dropdown = ctk.CTkComboBox(filter_frame, values=locations, variable=selected_location, width=150, state="readonly")
        location_dropdown.pack(side=tk.LEFT, padx=5)
        
        # Marco para el ordenamiento
        sort_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        sort_frame.pack(side=tk.RIGHT, padx=5)
        
        # Etiqueta para ordenamiento
        sort_label = ctk.CTkLabel(sort_frame, text="Ordenar por IP:", font=("Roboto", 12, 'bold'))
        sort_label.pack(side=tk.LEFT, padx=(10, 5))
        
        # Variable para el orden
        sort_order = tk.StringVar(value="Ascendente")
        
        # ComboBox para el orden
        sort_dropdown = ctk.CTkComboBox(sort_frame, values=["Ascendente", "Descendente"], variable=sort_order, width=120, state="readonly")
        sort_dropdown.pack(side=tk.LEFT, padx=5)
        
        # Botón para aplicar filtro y ordenamiento
        apply_btn = ctk.CTkButton(
            controls_frame, 
            text="Aplicar", 
            command=lambda: update_tasks_list(tasks_frame, selected_location.get(), sort_order.get())
        )
        apply_btn.pack(side=tk.RIGHT, padx=10)
        
        # Variable para mantener referencia al marco de tareas
        tasks_list_frame = None
        
        # Función para extraer el último octeto de una IP
        def get_last_octet(ip_string):
            try:
                # Dividir la IP por puntos y obtener el último elemento
                octets = ip_string.split('.')
                if len(octets) == 4:
                    return int(octets[-1])
                else:
                    return 0  # Valor por defecto si la IP no es válida
            except (ValueError, IndexError):
                return 0  # Valor por defecto en caso de error
        
        # Función interna para actualizar la lista de tareas según el filtro y ordenamiento
        def update_tasks_list(frame, selected_loc, sort_ord):
            # Limpiar el marco previo si existe
            for widget in frame.winfo_children():
                widget.destroy()
            
            # Verificar si hay tareas programadas
            if not self.scheduled_tasks:
                no_tasks_label = ctk.CTkLabel(frame, text="No hay tareas programadas", font=("Roboto", 12))
                no_tasks_label.pack(pady=20)
                return
            
            # Mostrar encabezados
            header_frame = ctk.CTkFrame(frame)
            header_frame.pack(fill=tk.X, padx=5, pady=5)
            
            ip_label = ctk.CTkLabel(header_frame, text="IP Switch", width=100, font=("Roboto", 12, "bold"))
            ip_label.pack(side=tk.LEFT, padx=10)
            
            time_label = ctk.CTkLabel(header_frame, text="Fecha/Hora", width=150, font=("Roboto", 12, "bold"))
            time_label.pack(side=tk.LEFT, padx=10)
            
            type_label = ctk.CTkLabel(header_frame, text="Tipo", width=80, font=("Roboto", 12, "bold"))
            type_label.pack(side=tk.LEFT, padx=10)
            
            location_label = ctk.CTkLabel(header_frame, text="Ubicación", width=100, font=("Roboto", 12, "bold"))
            location_label.pack(side=tk.LEFT, padx=10)
            
            # Filtrar tareas por ubicación
            filtered_tasks = []
            for i, task in enumerate(self.scheduled_tasks):
                location = task["switch_data"].get("location", "Desconocida")
                if selected_loc == "Todas" or location == selected_loc:
                    filtered_tasks.append((i, task))
            
            if not filtered_tasks:
                no_filtered_tasks = ctk.CTkLabel(frame, text=f"No hay tareas programadas para {selected_loc}", font=("Roboto", 12))
                no_filtered_tasks.pack(pady=20)
                return
            
            # Ordenar las tareas filtradas por el último octeto de la IP
            reverse_order = (sort_ord == "Descendente")
            filtered_tasks.sort(key=lambda x: get_last_octet(x[1]["switch_data"]["ip"]), reverse=reverse_order)
            
            # Mostrar cada tarea filtrada y ordenada
            for idx, (task_index, task) in enumerate(filtered_tasks):
                task_frame = ctk.CTkFrame(frame)
                task_frame.pack(fill=tk.X, padx=5, pady=5)
                
                # IP del switch
                task_ip = task["switch_data"]["ip"]
                ip_info = ctk.CTkLabel(task_frame, text=task_ip, width=100)
                ip_info.pack(side=tk.LEFT, padx=10)
                
                # Fecha y hora programada
                try:
                    if isinstance(task["time"], str):
                        task_dt = datetime.datetime.strptime(task["time"], "%Y-%m-%d %H:%M:%S")
                    else:
                        task_dt = task["time"]
                    task_time = task_dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    task_time = str(task["time"])
                
                time_info = ctk.CTkLabel(task_frame, text=task_time, width=150)
                time_info.pack(side=tk.LEFT, padx=10)
                
                # Tipo de tarea (única o recurrente)
                task_type = "Mensual" if task.get("recurring") == "monthly" else "Única"
                type_info = ctk.CTkLabel(task_frame, text=task_type, width=80)
                type_info.pack(side=tk.LEFT, padx=10)
                
                # Ubicación del switch
                task_loc = task["switch_data"].get("location", "Desconocida")
                loc_info = ctk.CTkLabel(task_frame, text=task_loc, width=100)
                loc_info.pack(side=tk.LEFT, padx=10)
                
                # Botón para eliminar tarea
                delete_btn = ctk.CTkButton(
                    task_frame, 
                    text="Eliminar", 
                    width=80,
                    command=lambda t_idx=task_index: self.delete_task_from_window(t_idx, tasks_window),
                    fg_color="darkred", 
                    hover_color="#8B0000"
                )
                delete_btn.pack(side=tk.RIGHT, padx=10)
        
        # Crear marco desplazable para las tareas
        tasks_frame = ctk.CTkScrollableFrame(tasks_window)
        tasks_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Conectar el método de actualización
        self.update_tasks_list = update_tasks_list
        
        # Cargar inicialmente todas las tareas ordenadas de forma ascendente
        update_tasks_list(tasks_frame, "Todas", "Ascendente")
        
        # Botón para cerrar
        close_btn = ctk.CTkButton(tasks_window, text="Cerrar", command=tasks_window.destroy)
        close_btn.pack(pady=20, padx=50)

    def delete_task_from_window(self, task_index, window):
        try:
            # Verificar índice
            if 0 <= task_index < len(self.scheduled_tasks):
                task = self.scheduled_tasks[task_index]
                if isinstance(task["time"], str):
                    task_dt = datetime.datetime.strptime(task["time"], "%Y-%m-%d %H:%M:%S")
                else:
                    task_dt = task["time"]
                task_dt = datetime.datetime.strptime(task["time"], "%Y-%m-%d %H:%M:%S")
                task_time = task_dt.strftime("%Y-%m-%d %H:%M:%S")
                task_ip = task["switch_data"]["ip"]
                
                # Eliminar tarea
                self.scheduled_tasks.pop(task_index)
                guardar_json(self.scheduled_tasks, TASKS_FILE)
                
                # Mostrar confirmación
                self.write_to_terminal(f"Tarea para {task_ip} programada para {task_time} eliminada.")
                
                # Actualizar la ventana
                window.destroy()
                self.show_scheduled_tasks_window()
            else:
                raise IndexError("Índice de tarea fuera de rango")
        except Exception as e:
            CTkMessagebox(title="Error", message=f"Error al eliminar tarea: {str(e)}", icon="cancel")

    def generar_nombre_backup_desde_switch(self, shell, ftp, ftp_path, hostname="SWITCH"):
        """
        Genera el nombre del archivo de backup utilizando múltiples métodos 
        para obtener el hostname del switch
        """
        
        def clean_output(text):
            """Limpia caracteres de control ANSI y otros caracteres especiales"""
            import re
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            text = ansi_escape.sub('', text)
            text = ''.join(c if ord(c) >= 32 or c in '\r\n\t' else '' for c in text)
            return text
        
        # Limpiar buffer inicial
        if shell.recv_ready():
            shell.recv(65535)
        
        # MÉTODO 1: Intentar con show running-config | include hostname
        try:
            self.write_to_terminal("Intentando obtener hostname con comando include...")
            shell.send("show running-config | include hostname\n")
            time.sleep(2)
            hostname_output = shell.recv(65535).decode('utf-8', errors='ignore')
            hostname_output_clean = clean_output(hostname_output)
            
            self.write_to_terminal(f"Salida del comando hostname: {hostname_output_clean}")
            
            # Verificar si hay error de sintaxis
            if "Invalid input" not in hostname_output_clean and "%" not in hostname_output_clean:
                # Patrones mejorados para buscar hostname
                hostname_patterns = [
                    r"hostname\s+([A-Za-z0-9_.-]+)",  # Patrón principal
                    r"^hostname\s+(\S+)",             # Patrón al inicio de línea
                    r"hostname\s*=\s*(\S+)",          # Formato con =
                    r"hostname:\s*(\S+)"              # Formato con :
                ]
                
                hostname_found = False
                for pattern in hostname_patterns:
                    hostname_match = re.search(pattern, hostname_output_clean, re.IGNORECASE | re.MULTILINE)
                    if hostname_match:
                        extracted_hostname = hostname_match.group(1).strip()
                        # Validar que el hostname extraído no sea la palabra "hostname" misma
                        if extracted_hostname.lower() != "hostname" and len(extracted_hostname) > 0:
                            hostname = extracted_hostname
                            hostname_found = True
                            self.write_to_terminal(f"Hostname extraído exitosamente: {hostname}")
                            break
                
                if not hostname_found:
                    # Intentar extraer del prompt si aparece
                    prompt_match = re.search(r"([A-Za-z0-9_-]+)[>#]", hostname_output_clean)
                    if prompt_match:
                        extracted_hostname = prompt_match.group(1).strip()
                        if extracted_hostname.lower() not in ["hostname", "switch"]:
                            hostname = extracted_hostname
                            self.write_to_terminal(f"Hostname extraído del prompt: {hostname}")
                        else:
                            raise Exception("Hostname extraído del prompt no es válido")
                    else:
                        raise Exception("No se pudo extraer hostname válido")
            else:
                self.write_to_terminal("El comando 'include' no es soportado, probando método alternativo...")
                raise Exception("Comando include no soportado")
                
        except Exception as e:
            self.write_to_terminal(f"Método 1 falló: {str(e)}")
            
            # MÉTODO 2: Obtener configuración completa y buscar hostname
            try:
                self.write_to_terminal("Obteniendo configuración completa...")
                shell.send("show running-config\n")
                time.sleep(2)
                
                config_output = ""
                timeout = time.time() + 30
                
                while time.time() < timeout:
                    if shell.recv_ready():
                        chunk = shell.recv(65535).decode('utf-8', errors='ignore')
                        clean_chunk = clean_output(chunk)
                        config_output += clean_chunk
                        
                        # Manejar paginación
                        if "--More--" in chunk or "(q)uit" in chunk:
                            shell.send(' ')
                            time.sleep(1)
                        elif '#' in clean_chunk and len(clean_chunk.strip()) < 50:
                            break
                        
                        # Si ya encontramos hostname, no necesitamos más
                        hostname_match = re.search(r"hostname\s+([A-Za-z0-9_.-]+)", clean_chunk, re.IGNORECASE)
                        if hostname_match and hostname_match.group(1).lower() != "hostname":
                            break
                    else:
                        time.sleep(0.5)
                
                # Buscar hostname en la configuración con patrones mejorados
                hostname_patterns = [
                    r"hostname\s+([A-Za-z0-9_.-]+)",
                    r"^hostname\s+(\S+)",
                    r"hostname\s*=\s*(\S+)",
                    r"hostname:\s*(\S+)"
                ]
                
                hostname_found = False
                for pattern in hostname_patterns:
                    hostname_match = re.search(pattern, config_output, re.IGNORECASE | re.MULTILINE)
                    if hostname_match:
                        extracted_hostname = hostname_match.group(1).strip()
                        if extracted_hostname.lower() != "hostname" and len(extracted_hostname) > 0:
                            hostname = extracted_hostname
                            hostname_found = True
                            self.write_to_terminal(f"Hostname encontrado en configuración: {hostname}")
                            break
                
                if not hostname_found:
                    raise Exception("No se encontró hostname válido en configuración")
                    
            except Exception as e2:
                self.write_to_terminal(f"Método 2 falló: {str(e2)}")
                
                # MÉTODO 3: Extraer del prompt actual
                try:
                    self.write_to_terminal("Intentando extraer hostname del prompt...")
                    shell.send("\n")
                    time.sleep(1)
                    prompt_output = shell.recv(65535).decode('utf-8', errors='ignore')
                    prompt_output_clean = clean_output(prompt_output)
                    
                    # Patrones mejorados para el prompt
                    prompt_patterns = [
                        r"([A-Za-z0-9_.-]+)[>#]\s*$",
                        r"([A-Za-z0-9_.-]+)[>#]",
                        r"\r\n([A-Za-z0-9_.-]+)[>#]"
                    ]
                    
                    hostname_found = False
                    for pattern in prompt_patterns:
                        prompt_match = re.search(pattern, prompt_output_clean)
                        if prompt_match:
                            extracted_hostname = prompt_match.group(1).strip()
                            if extracted_hostname.lower() not in ["hostname", "switch"] and len(extracted_hostname) > 0:
                                hostname = extracted_hostname
                                hostname_found = True
                                self.write_to_terminal(f"Hostname extraído del prompt: {hostname}")
                                break
                    
                    if not hostname_found:
                        raise Exception("No se pudo extraer hostname válido del prompt")
                        
                except Exception as e3:
                    self.write_to_terminal(f"Método 3 falló: {str(e3)}")
                    
                    # MÉTODO 4: Intentar show version
                    try:
                        self.write_to_terminal("Intentando con show version...")
                        shell.send("show version\n")
                        time.sleep(3)
                        version_output = shell.recv(65535).decode('utf-8', errors='ignore')
                        version_output_clean = clean_output(version_output)
                        
                        # Buscar diferentes patrones en show version
                        patterns = [
                            r"System Name[:\s]+([^\r\n\s]+)",
                            r"Device name[:\s]+([^\r\n\s]+)",
                            r"([A-Za-z0-9_.-]+)\s+uptime",
                            r"Switch\s+([A-Za-z0-9_.-]+)"
                        ]
                        
                        hostname_found = False
                        for pattern in patterns:
                            match = re.search(pattern, version_output_clean, re.IGNORECASE)
                            if match:
                                extracted_hostname = match.group(1).strip()
                                if extracted_hostname.lower() not in ["hostname", "switch"] and len(extracted_hostname) > 0:
                                    hostname = extracted_hostname
                                    hostname_found = True
                                    self.write_to_terminal(f"Hostname encontrado en version: {hostname}")
                                    break
                        
                        if not hostname_found:
                            raise Exception("No se encontró hostname válido en show version")
                            
                    except Exception as e4:
                        self.write_to_terminal(f"Todos los métodos fallaron, usando hostname por defecto: {hostname}")

        # Verificar que el hostname es válido
        if not hostname or hostname.lower() in ["switch", "hostname"]:
            self.write_to_terminal("Hostname no válido, usando valor por defecto")
            hostname = "SWITCH"

        # Obtener fecha y hora del switch
        try:
            shell.send("show clock\n")
            time.sleep(2)
            clock_output = shell.recv(65535).decode('utf-8', errors='ignore')
            clock_output_clean = clean_output(clock_output)
            self.write_to_terminal(f"Salida del reloj: {clock_output_clean}")
            
            # Patrones mejorados para diferentes formatos de fecha
            clock_patterns = [
                # Formato: 10:30:45.123 UTC Mon Dec 11 2023
                r"(\d{2}):(\d{2}):(\d{2})\.(\d{3})\s+\w+\s+\w+\s+(\w+)\s+(\d{1,2})\s+(\d{4})",
                # Formato: 10:30:45 UTC Mon Dec 11 2023  
                r"(\d{2}):(\d{2}):(\d{2})\s+\w+\s+\w+\s+(\w+)\s+(\d{1,2})\s+(\d{4})",
                # Formato: *10:30:45.123 UTC Mon Dec 11 2023
                r"\*(\d{2}):(\d{2}):(\d{2})\.(\d{3})\s+\w+\s+\w+\s+(\w+)\s+(\d{1,2})\s+(\d{4})",
                # Formato simple: 10:30:45
                r"(\d{2}):(\d{2}):(\d{2})"
            ]
            
            timestamp = None
            for pattern in clock_patterns:
                clock_match = re.search(pattern, clock_output_clean)
                if clock_match:
                    groups = clock_match.groups()
                    if len(groups) >= 7:  # Formato completo con milisegundos
                        hora, minuto, segundo, milisegundos, mes, dia, anio = groups
                        timestamp = f"{mes}-{dia}-{hora}-{minuto}-{segundo}.{milisegundos}"
                    elif len(groups) >= 6:  # Formato completo sin milisegundos
                        hora, minuto, segundo, mes, dia, anio = groups
                        timestamp = f"{mes}-{dia}-{hora}-{minuto}-{segundo}.000"
                    elif len(groups) >= 3:  # Solo hora
                        hora, minuto, segundo = groups[:3]
                        ahora = datetime.datetime.now()
                        mes = ahora.strftime("%b")
                        dia = ahora.strftime("%d")
                        timestamp = f"{mes}-{dia}-{hora}-{minuto}-{segundo}.000"
                    break
            
            if not timestamp:
                raise Exception("No se pudo parsear la fecha del switch")
                
        except Exception as e:
            self.write_to_terminal(f"Error al obtener fecha del switch: {str(e)}, usando fecha local")
            ahora = datetime.datetime.now()
            timestamp = ahora.strftime("%b-%d-%H-%M-%S.%f")[:-3]

        base_nombre = f"{hostname}-{timestamp}"

        # Verificar archivos existentes para secuencia
        try:
            ftp.cwd(ftp_path)
            archivos = ftp.nlst()
            
            # Encontrar la secuencia más alta existente
            max_secuencia = 0
            for archivo in archivos:
                # Buscar archivos que empiecen con el hostname
                if archivo.startswith(hostname):
                    seq_match = re.search(r'-(\d+)$', archivo)
                    if seq_match:
                        secuencia = int(seq_match.group(1))
                        max_secuencia = max(max_secuencia, secuencia)
            
            secuencia = max_secuencia + 1
            
        except Exception as e:
            self.write_to_terminal(f"Error al listar archivos FTP: {str(e)}")
            secuencia = 1
        
        # Generar nombre final
        nombre_final = f"{base_nombre}-{secuencia}"
        self.write_to_terminal(f"Nombre del archivo generado: {nombre_final}")
        return nombre_final

    def execute_backup(self, switch_data, ftp_data):
        """Ejecuta un backup utilizando los datos proporcionados de switch y FTP"""

        # Creamos una nueva conexión SSH con los datos proporcionados
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            # Registrar inicio de backup
            self.write_to_terminal(f"Iniciando backup para {switch_data['ip']} ({switch_data.get('location', 'desconocido')})")
            
            ssh_client.connect(
                switch_data['ip'], 
                username=switch_data['user'], 
                password=switch_data['password'],
                timeout=15
            )
            
            # Establecer sesión de shell
            shell = ssh_client.invoke_shell()
            shell.settimeout(15)
            time.sleep(2)
            shell.recv(65535)  # Limpiar buffer inicial
            
            # Función para limpiar caracteres de control ANSI y otros caracteres especiales
            def clean_output(text):
                # Eliminar códigos de escape ANSI (colores, formato, etc.)
                import re
                ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                text = ansi_escape.sub('', text)
                
                # Eliminar caracteres de control no imprimibles
                text = ''.join(c if ord(c) >= 32 or c in '\r\n\t' else '' for c in text)
                return text
            
            # Entrar en modo privilegiado
            shell.send('enable\n')
            time.sleep(1)
            
            output = clean_output(shell.recv(65535).decode('utf-8', errors='ignore'))
            if 'Password:' in output:
                shell.send(f"{switch_data['enable_password']}\n")
                time.sleep(1)
                clean_output(shell.recv(65535).decode('utf-8', errors='ignore'))
            
            # Obtener último octeto para crear directorio
            ip_parts = switch_data['ip'].split('.')
            last_octet = ip_parts[-1]
            
            # Configurar ruta en servidor FTP
            ftp_path = f"/{switch_data['location_code']}/{last_octet}/BKP-Mensual"
            
            # Conectar al servidor FTP para preparar directorio
            ftp = FTP(ftp_data['server'])
            ftp.login(ftp_data['user'], ftp_data['password'])
            
            # Crear estructura de directorios en FTP
            partes = ftp_path.strip('/').split('/')
            ruta_actual = ''
            for parte in partes:
                ruta_actual += f'/{parte}'
                try:
                    ftp.cwd(ruta_actual)
                except:
                    ftp.mkd(ruta_actual)
                    ftp.cwd(ruta_actual)
            
            # Generar nombre de archivo basado en hostname y fecha/hora
            nombre_archivo = self.generar_nombre_backup_desde_switch(shell, ftp, ftp_path)
            ftp.quit()
            
            # Registrar información del comando

            print(f"Nombre del archivo: {nombre_archivo}")
            self.write_to_terminal(f"Ejecutando backup a {ftp_path}/{nombre_archivo}...")
            
            # Ejecutar comando de copia de forma más clara
            copy_command = f'copy running-config ftp://{ftp_data["user"]}:{ftp_data["password"]}@{ftp_data["server"]}{ftp_path}/{nombre_archivo}\n'
            shell.send(copy_command)
            print(copy_command)
            time.sleep(3)
            
            # Manejo interactivo con limpieza de caracteres
            output = ""
            timeout = time.time() + 60
            
            while time.time() < timeout:
                if shell.recv_ready():
                    chunk = shell.recv(65535).decode('utf-8', errors='ignore')
                    clean_chunk = clean_output(chunk)
                    output += clean_chunk
                    
                    # Solo escribir al terminal si el chunk limpio contiene información útil
                    if clean_chunk.strip():
                        self.write_to_terminal(f"Progreso: {clean_chunk.strip()}")
                    
                    # Responder a diferentes prompts
                    if 'Address or name of remote host' in clean_chunk:
                        shell.send('\n')
                        time.sleep(1)
                    elif 'Destination filename' in clean_chunk:
                        shell.send('\n')  
                        time.sleep(1)
                    # Detectar señales de finalización
                    elif any(signal in clean_chunk for signal in ['bytes copied', '!', 'OK', 'successful', 'completed']):
                        time.sleep(2)  # Esperar para recibir todo
                        break
                
                time.sleep(0.5)
            
            # Obtener cualquier salida restante
            while shell.recv_ready():
                chunk = shell.recv(65535).decode('utf-8', errors='ignore')
                clean_chunk = clean_output(chunk)
                output += clean_chunk
                if clean_chunk.strip():
                    self.write_to_terminal(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Progreso: {clean_chunk.strip()}")
            
            # Cerrar sesión shell
            shell.close()
            ssh_client.close()
            
            # Verificación de éxito
            success_indicators = [
                'bytes copied', 'OK', 'successful', 'completed', '!',
                'copied', 'transferred', 'Upload complete'
            ]
            
            if any(indicator in output for indicator in success_indicators):
                self.write_to_terminal(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Backup completado exitosamente para {switch_data['ip']}")
                return True
            else:
                # Verificar si el archivo existe en el servidor FTP
                try:
                    verification_ftp = FTP(ftp_data['server'])
                    verification_ftp.login(ftp_data['user'], ftp_data['password'])
                    verification_ftp.cwd(ftp_path)
                    
                    files = verification_ftp.nlst()
                    verification_ftp.quit()
                    
                    if nombre_archivo in files:
                        self.write_to_terminal(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Archivo encontrado en FTP aunque no se recibió confirmación clara. Considerando exitoso.")
                        return True
                    else:
                        raise Exception("No se pudo confirmar la copia al servidor FTP y el archivo no existe")
                except Exception as e:
                    raise Exception(f"No se pudo confirmar la copia al servidor FTP. Error secundario al verificar: {str(e)}")
        
        except Exception as e:
            # Asegurar que las conexiones se cierren en caso de error
            if 'shell' in locals() and shell:
                shell.close()
            if 'ssh_client' in locals() and ssh_client:
                ssh_client.close()
            raise e

    def start_task_checker_thread(self):

        def check_tasks():
            while True:
                now = datetime.datetime.now()
                tasks_to_remove = []  # Lista para almacenar tareas a eliminar
                tasks_executed = set()  # Conjunto para evitar ejecutar la misma tarea más de una vez por ciclo
                
                for i, task in enumerate(self.scheduled_tasks):
                    task_id = f"{task['switch_data']['ip']}_{task.get('time')}"
                    
                    if task_id in tasks_executed:
                        continue  # Evitar procesar la misma tarea más de una vez en el mismo ciclo
                    
                    if isinstance(task["time"], str):
                        task_time = datetime.datetime.strptime(task["time"], "%Y-%m-%d %H:%M:%S")
                    else:
                        task_time = task["time"]
                        
                    if now >= task_time:
                        self.write_to_terminal(f"Ejecutando tarea programada para {task['switch_data']['ip']} ubicado en {task['switch_data']['location']}...")
                        try:
                            self.execute_backup(task["switch_data"], task["ftp_data"])
                            self.write_to_terminal("Backup programado completado exitosamente.")
                            
                            # Si es una tarea recurrente mensual, reprogramarla
                            if task.get("recurring") == "monthly":
                                # Reprogramar para el 5 del mes siguiente a las 03:00 AM
                                next_month = now + relativedelta(months=1)
                                next_run = next_month.replace(day=5, hour=3, minute=0, second=0, microsecond=0)

                                # Actualizamos directamente la lista original
                                self.scheduled_tasks[i]["time"] = next_run.strftime("%Y-%m-%d %H:%M:%S")
                                self.write_to_terminal(f"Tarea mensual reprogramada para {next_run.strftime('%Y-%m-%d %H:%M')}")
                            else:
                                # Si no es recurrente, marcar para eliminar
                                tasks_to_remove.append(i)
                            
                            # Marcar como ejecutada en este ciclo
                            tasks_executed.add(task_id)
                                
                        except Exception as e:
                            self.write_to_terminal(
                                f"Error al ejecutar backup programado: {str(e)}. Se reintentará en el próximo ciclo."
                            )
                
                # Eliminar tareas marcadas (en orden inverso para no afectar los índices)
                for index in sorted(tasks_to_remove, reverse=True):
                    del self.scheduled_tasks[index]
                    
                # Guardar el estado actualizado de las tareas
                guardar_json(self.scheduled_tasks, TASKS_FILE)
                
                time.sleep(30)  # Revisa cada 30 segundos
        
        threading.Thread(target=check_tasks, daemon=True).start()

if __name__ == "__main__":
    
    root = ctk.CTk()
    app = BackupSwitchApp(root)
    
    # Iniciar thread para verificar tareas programadas
    #app.start_task_checker_thread()
    
    root.mainloop()