# Registro de Resolución de Problemas y Bugs Conocidos (Troubleshooting)

Este documento registra los bloqueos más complejos encontrados en el desarrollo de **SygurDot** y explica las soluciones definitivas implementadas en el código base, sirviendo como guía histórica y técnica.

---

## Incidente: Congelamiento Total y "Mouse en forma de X" tras `startx` en ASUS VivoBook 15 (Tiger Lake + NVIDIA MX350, Kernel 6.12+)

### Descripción de los Síntomas
1. Al ejecutar `startx`, el sistema lograba mostrar el Wallpaper y arrancar Polybar. Sin embargo, Polybar **no actualizaba sus módulos** (quedándose vacío en CPU, RAM, etc) y el proceso consumía un enorme pico del procesamiento de la máquina.
2. El cursor del mouse se transformaba en una **"X" gigante (crosshair)**, ignorando los temas predeterminados, y además **ningún atajo de teclado (`sxhkd`) funcionaba**, dejando el entorno completamente congelado.
3. Único indicio vital: al hacer clic sostenido con la "X" sobre la pantalla vacía y arrastrar un rectángulo de selección, la Polybar recobraba la vida y actualizaba su reloj **por un solo segundo**, antes de re-congelarse.
4. Todo esto ocurría acompañado de un historial previo de errores graves de kernel (`Timeout waiting for PHY ready`) al momento de arrancar la laptop.

### Anatomía del Problema (El Efecto Dominó)
La investigación en vivo a través de SSH reveló que el fallo no era uno, sino **tres bugs críticos independientes operando al mismo tiempo**, cada uno camuflando al otro:

#### 1. El Bug del "BOM de Windows" y el Secuestrador de Pantalla (ImageMagick)
* **La Causa:** Los scripts de monitoreo creados en Python (`system-monitor.py` y `bspwm-dynamic.py`) habían sido editados previamente usando un editor de código en Windows. Windows guardó estos archivos inyectándoles silenciosamente un carácter fantasma de codificación al inicio del archivo: un **UTF-8 BOM (`\xef\xbb\xbf`)** y saltos de línea CRLF.
* **El Efecto:** Al llegar a Linux, el kernel detectaba estos bytes fantasmas y por consiguiente consideraba corrupto el "Shebang" (`#!/usr/bin/env python3`), negándose a ejecutar el archivo utilizando Python. Ante la falla, la terminal estándar de Linux (`/bin/sh`) intentó procesar el archivo a la fuerza y leyó la línea principal del código Python: `import sys`. Totalmente fuera de contexto, para Linux, **`import` es una herramienta binaria del utilitario `ImageMagick`**, cuya única función es cambiar el cursor a una forma de cruz (`X`) para capturar la pantalla esperando a que el usuario dibuje un rectángulo con el ratón. Al dibujar el cuadro, Polybar destrababa pero pasaba a la siguiente instrucción `import subprocess`, repitiendo el proceso y "congelando" las entradas de Xorg infinitamente.
* **La Solución:** Se reingenierizó la etapa final del instalador (`install.sh`). Ahora somete de manera automática al repositorio completo a un lavado quirúrgico nativo utilizando un motor de expresiones `Perl` avanzado y `Sed`. Todo rastro de BOM o CRLF importado de otros sistemas es eliminado y destrozado de la clonación cruda **antes** de que el binario tome derechos de ejecución.

#### 2. Deadlock KMS Interno (`nvidia-drm modeset=1`)
* **La Causa:** Intentando optimizar la arquitectura híbrida sólida para soportar pantallas y portátiles modernas de alto desempeño (ej. HP Victus con NVIDIA RTX 4000/5000), se introdujo en el instalador la política universal de inyectar el apoderamiento KMS al Kernel: `options nvidia-drm modeset=1`.
* **El Efecto:** En equipos de la generación Intel Iris (como la ASUS VivoBook), cuyo conector físico de panel reside completamente en la gráfica integrada, esta inyección obligaba a NVIDIA a usurpar permisos en segundo plano interrumpiendo las consultas de la API gráfica principal (`DRM/KMS`). Cuando utilitarios como `xrandr` o `bspwm` intentaban consultar los monitores, el canal DRM generaba un *deadlock* (choque letal) bloqueando absolutamente X11 tras bambalinas.
* **La Solución:** Lógica dinámica en tiempo real. Ahora el instalador sondea los puertos PCI de la computadora e identifica específicamente a la familia conflictiva Tiger Lake (`9A49, 9A40...`). De detectarse, rechaza forzosamente al bloque KMS asumiendo correctamente un Offload puro por software nativo de NVIDIA, mientras cuida y sigue desplegándolo de manera óptima en ordenadores como el HP Victus y arquitecturas contemporáneas sin generar trabas.

#### 3. El Conflicto Dual del Kernel 6.12 (`xe` vs `i915`)
* **La Causa:** A partir del núcleo/kernel 6.12+ (Debian Trixie), se intentó forzar experimentalmente en Linux el uso de un nuevo módulo (`xe`) paralelo al ya funcional módulo clásico de Intel para gráficas (`i915`). 
* **El Efecto:** Al ejecutarse ambos en simultáneo, formaban un "Kernel Panic" luchando por apoderarse del `intel_tc_port_lock` (El controlador interno logístico de los puertos Thunderbolt / Display). Al intentar solucionar este combate con parámetros rígidos de arranque del bootloader en el pasado, se bloqueó ciegamente el canal energético de la pantalla (`i915.enable_dc=0`), causando los aterradores desconectes físicos directos por *Timeout*.
* **La Solución:** Intervención aséptica aislada en el `install.sh`. Toda mitigación agresiva sobre la energía de Linux GRUB fue abandonada. De la única traba requerida y vital hoy por hoy, `install.sh` se encargará condicionalmente de aplicar silenciosamente listado negro (`blacklist xe`) exclusivamente al percatarse de gráficas y arquitecturas Intel en esta generación. Ni más ni menos, garantizando un booteo en armonía, donde solo un Módulo a la vez reclama el control.

---

## Incidente: Fallo de Inicialización y Bloqueo de Xorg con NVIDIA Blackwell (RTX 5050 Laptop) y Ryzen AI (Debian Trixie, Kernel 6.12+)

### Descripción de los Síntomas
1. El usuario intentaba abrir la utilidad `nvidia-settings` (NVIDIA X Server Settings) pero esta fallaba, se colgaba o no detectaba la tarjeta de video.
2. El entorno gráfico general carecía de aceleración por hardware o directamente fallaba al intentar arrancar `startx`.
3. Al inspeccionar vía comandos o SSH, el proceso de NVIDIA (`nvidia-smi`) se quedaba colgado en estado de sueño ininterrumpible ("D state") y los logs del kernel (`dmesg`) arrojaban errores severos como `RmInitAdapter failed` y conflictos de memoria con el firmware de la GPU.

### Anatomía del Problema (El Choque Generacional)
Este incidente fue el resultado particular de combinar el procesador más nuevo de AMD (Ryzen AI 5 340, arquitectura Zen 5) junto con la arquitectura gráfica más reciente de NVIDIA (RTX 5050, familia Blackwell) en un entorno Linux moderno. El problema se dividió en tres fallas estructurales clave:

#### 1. Obligatoriedad de "Open Kernel Modules" para Blackwell
* **La Causa:** Tradicionalmente, los usuarios de Linux instalan la versión cerrada/binaria (proprietaria) de los drivers de NVIDIA. Sin embargo, a partir de la arquitectura Blackwell (Serie 5000), NVIDIA externalizó casi todo el control físico de la tarjeta al **GSP (GPU System Processor)**, un microprocesador integrado en la propia tarjeta. Los módulos cerrados clásicos del driver fallan por diseño al intentar comunicarse con este hardware. Resulta estrictamente obligatorio usar los nuevos módulos de código abierto ("Open Kernel Modules") de NVIDIA.
* **El Efecto:** Las instalaciones manuales o mediante repositorios del driver estándar se colgaban silenciosamente o generaban crashes al no lograr inicializar el propio sistema embebido (GSP) de la tarjeta.

#### 2. Conflicto de Memoria IOMMU con Ryzen AI (Strix/Kraken)
* **La Causa:** Incluso utilizando el módulo correcto, la nueva arquitectura de procesadores AMD y el puente de memoria IOMMU estaban interceptando y bloqueando los intentos de la GPU por cargar su firmware en la memoria virtual, provocando alertas letales de `IO_PAGE_FAULT` y de "Invalid state".
* **El Efecto:** La GPU intentaba arrancar su firmware GSP, la CPU lo bloqueaba por seguridad de memoria, y dejaba a la tarjeta en un estado corrupto conocido como "WPR2".

#### 3. Bugs de Versión en Driver 570 y Conflicto de Paquetes
* **La Causa:** La versión inicial instalada (570.86.16) contenía bugs conocidos de compatibilidad con esta variante de Zen 5. Además, la presencia del paquete `firmware-nvidia-gsp` de los repositorios de Debian causaba choques de versión contra el firmware incrustado en la instalación manual del driver NVIDIA.

---

### La Solución y el Procedimiento Paso a Paso

Para erradicar este bloqueo general y devolverle la vida a la GPU, se procedió a orquestar una instalación quirúrgica de los drivers siguiendo estas medidas exactas:

1. **Evadir el Bloqueo de Memoria IOMMU:**
   Se modificó permanentemente el gestor de arranque (`/etc/default/grub`), asegurando el parámetro `amd_iommu=off` (o `iommu=pt`) dentro de `GRUB_CMDLINE_LINUX_DEFAULT`. Esto le quitó las esposas a la GPU permitiéndole transaccionar con su firmware libremente durante el arranque del sistema.

2. **Purificar el Entorno y Limpiar el Estado WPR2:**
   Se borró el paquete nativo de firmware (`sudo apt purge firmware-nvidia-gsp`). Adicionalmente, fue necesario aplicarle a la laptop un **Hard-Reset (Mantenido 15 segundos en el botón físico de encendido)**. Esta es la única forma confiable de drenar la energía y limpiar el registro "sucio" de la memoria WPR2 para que la gráfica vuelva a aceptar comandos limpios en su siguiente encendido.

3. **Descarga e Instalación Forzada del Módulo Abierto (v595.58.03):**
   Conectados desde TTY / SSH como `root`, se detuvieron los procesos colgados y se descargaron los módulos defectuosos en memoria:
   ```bash
   modprobe -r nvidia_drm nvidia_modeset nvidia_uvm nvidia
   ```
   A continuación, se corrió la instalación del parche más avanzado (`v595.58.03.run`). El secreto vital de este paso fue obligar silenciosamente a DKMS a compilar estrictamente los módulos abiertos:
   ```bash
   /tmp/nvidia_new.run --silent --dkms --kernel-module-type=open --no-questions
   ```

### Conclusión
Tras ejecutar estos pasos, `nvidia-smi` iluminó la terminal reconociendo majestuosamente la **RTX 5050 Laptop GPU**. El Servidor X (`startx`) fue capaz de arrancar fluido, habilitando por fin el panel gráfico `nvidia-settings` con control total sobre los sensores y el rendimiento 3D del equipo. Este caso en particular asienta el protocolo para tratar equipos "híbridos" de novísima generación.

---

## Incidente: Congelamientos de Pantalla y Pérdida de Ventanas en HP Victus (AMD Krackan + NVIDIA RTX 5050)

### Descripción de los Síntomas
1. La pantalla se congelaba súbitamente durante el uso normal. Se perdía la visualización del contenido de las ventanas o estas parecían "desaparecer", aunque el marco del gestor de ventanas (`bspwm`) seguía siendo visible.
2. El sistema de fondo seguía operando (se podía cambiar a un TTY), pero el entorno gráfico era inoperable interactuando con ratón o teclado.
3. La única forma de "descongelar" la pantalla sin perder el entorno gráfico era realizando un ciclo de energía física del panel (cerrando y abriendo la tapa de la laptop) o recargando forzosamente el gestor de ventanas (`Super + Alt + R`), lo cual reiniciaba el compositor `picom`.
4. El problema persistía independientemente del backend del compositor (`xrender` vs `glx`) e incluso de opciones extremas de sincronización en Xorg (`TearFree`, `DRI 3`). 

### Anatomía del Problema (El Fallo de Ahorro Energético en el Kernel)
El problema real no se encontraba en el compositor de ventanas (`picom`) ni en la configuración de Xorg (el archivo `/etc/X11/xorg.conf.d/10-hibrido.conf` estaba correcto y es estrictamente necesario en esta arquitectura híbrida para dirigir el renderizado), sino en un **bug del kernel de Linux con las tecnologías modernas de gestión de energía de pantallas en las nuevas iGPUs de AMD (Arquitectura Krackan / Radeon 800M)**.

El origen de la falla es un desajuste profundo a nivel de Direct Rendering Manager (DRM) con dos funciones específicas del driver `amdgpu`:
* **Panel Self Refresh (PSR)**
* **Scatter/Gather (SG) Display**

Estas funciones ahorran batería "durmiendo" la conexión física entre la gráfica AMD y el panel de la laptop cuando la imagen en pantalla es estática. El error crítico en el kernel de Linux ocurría cuando la gráfica intentaba **"despertar" la pantalla** a tiempo para procesar el redibujado de una ventana solicitada por el compositor (`picom`) o el gestor de ventanas (`bspwm`). 
Al fallar este despertar, el búfer de imagen entraba en un *deadlock*, atascándose infinitamente esperando una señal física de sincronización que nunca llegaba, congelando visualmente el escritorio.

### La Solución Definitiva (Parche a Nivel Kernel)
Cualquier intento de forzar la sincronización a través de Xorg (añadiendo directivas estrictas en `10-hibrido.conf`) o ajustando la agresividad de repintado en `picom.conf` (como alterar `use-damage`) es inútil, ya que ataca el síntoma y no la enfermedad.

La solución quirúrgica implementada requiere desactivar estrictamente estas problemáticas rutinas de energía de la pantalla, pasándole parámetros directos de booteo al kernel a través de GRUB:

1. **Edición del Gestor de Arranque (`/etc/default/grub`):**
   Se modificó la variable `GRUB_CMDLINE_LINUX_DEFAULT` para inyectar las siguientes dos directivas clave de AMDGPU:
   * **`amdgpu.sg_display=0`**: Desactiva forzosamente el uso de Scatter/Gather Display, obligando a la GPU a usar memoria de forma directa y secuencial para los búferes de pantalla.
   * **`amdgpu.dcdebugmask=0x10`**: Instruye al Display Core (DC) de AMD a omitir el uso de Panel Self Refresh (PSR).

2. **Actualización y Limpieza:**
   Se aplicaron los cambios en el sistema con `sudo update-grub`. Para garantizar la limpieza del entorno, se removieron todas las alteraciones experimentales ("sincronizaciones extremas") hechas en archivos como `10-hibrido.conf` y `picom.conf` devolviéndolas a la configuración original estándar y segura del sistema. Al reiniciar, los congelamientos intermitentes y el *deadlock* de renderizado desaparecieron por completo.